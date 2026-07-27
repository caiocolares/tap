#!/usr/bin/env python3
"""Serviço HTTP: recebe um áudio no body e devolve o arquivo com a transcrição."""
import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

import jwt
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import pika
import json

import storage
import mail
from transcribe import (
    assign_speakers,
    diarize,
    load_diarization_pipeline,
    load_whisper_model,
    to_wav,
    transcribe as run_transcription,
    write_json,
    write_txt,
)

load_dotenv()

MODEL_SIZE = os.environ.get("WHISPER_MODEL", "small")
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
LANGUAGE = os.environ.get("WHISPER_LANGUAGE") or None
HF_TOKEN = os.environ.get("HF_TOKEN")
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secreto-mudar-em-producao")

app = FastAPI(
    title="audio-to-text",
    description="Recebe um áudio (mp3) no body e devolve a transcrição, identificando a troca de speaker.",
)

# faster-whisper/pyannote não são seguros para chamadas concorrentes na mesma
# instância; o modelo/pipeline ficam em cache e as inferências são serializadas.
_lock = threading.Lock()
_cache: dict = {}

def _whisper_model():
    if "whisper" not in _cache:
        _cache["whisper"] = load_whisper_model(MODEL_SIZE, DEVICE)
    return _cache["whisper"]


def _diarization_pipeline():
    if "diarization" not in _cache:
        _cache["diarization"] = load_diarization_pipeline(HF_TOKEN, DEVICE)
    return _cache["diarization"]


@app.get("/health")
def health():
    return {"status": "ok"}

security = HTTPBearer()

def get_current_email(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Token sem e-mail")
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

class AuthRequest(BaseModel):
    email: str

@app.post("/auth/request-code")
async def request_code(req: AuthRequest, background_tasks: BackgroundTasks):
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    payload = {"sub": req.email, "exp": expire}
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    
    background_tasks.add_task(mail.send_auth_code_email, req.email, token)
    return {"message": "Um código de acesso foi gerado e enviado para o seu e-mail."}


@app.post("/transcricao/{formato}")
async def transcrever(formato: Literal["txt", "json"], request: Request, email: str = Depends(get_current_email)):
    tmp_dir = Path(tempfile.mkdtemp(prefix="audio-to-text-"))
    input_path = tmp_dir / "audio.mp3"

    try:
        bytes_written = 0
        with open(input_path, "wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
                bytes_written += len(chunk)

        if bytes_written == 0:
            raise HTTPException(400, "Corpo da requisição vazio: envie o áudio (mp3) como body.")

        if storage.STORAGE_ENABLED:
            await run_in_threadpool(storage.upload_file, f"{uuid.uuid4()}/audio.mp3", input_path)

        output_path, media_type = await run_in_threadpool(_processar, input_path, formato, tmp_dir)
        return FileResponse(
            output_path,
            media_type=media_type,
            filename=output_path.name,
            background=BackgroundTask(shutil.rmtree, tmp_dir, ignore_errors=True),
        )
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

@app.post("/async/transcricao/{formato}")
async def transcrever_async(formato: Literal["txt", "json"], request: Request, email: str = Depends(get_current_email)):
    if not storage.STORAGE_ENABLED:
        raise HTTPException(500, "O processamento assíncrono requer configuração do MinIO.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="audio-to-text-async-"))
    input_path = tmp_dir / "audio.mp3"

    try:
        bytes_written = 0
        with open(input_path, "wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
                bytes_written += len(chunk)

        if bytes_written == 0:
            raise HTTPException(400, "Corpo da requisição vazio: envie o áudio (mp3) como body.")

        job_id = str(uuid.uuid4())
        await run_in_threadpool(storage.upload_file, f"{job_id}/audio.mp3", input_path)

        def publish_message():
            url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
            connection = pika.BlockingConnection(pika.URLParameters(url))
            channel = connection.channel()
            channel.queue_declare(queue='transcription_jobs', durable=True)
            payload = {"job_id": job_id, "formato": formato, "email": email}
            channel.basic_publish(
                exchange='',
                routing_key='transcription_jobs',
                body=json.dumps(payload),
                properties=pika.BasicProperties(delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE)
            )
            connection.close()

        await run_in_threadpool(publish_message)
        return {"job_id": job_id, "status": "processing"}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/async/status/{job_id}")
async def status_transcricao(job_id: str):
    if not storage.STORAGE_ENABLED:
        raise HTTPException(500, "MinIO não configurado.")

    has_json = await run_in_threadpool(storage.file_exists, f"{job_id}/transcricao.json")
    has_txt = await run_in_threadpool(storage.file_exists, f"{job_id}/transcricao.txt")
    
    if has_json:
        formato, media_type = "json", "application/json"
    elif has_txt:
        formato, media_type = "txt", "text/plain; charset=utf-8"
    else:
        has_audio = await run_in_threadpool(storage.file_exists, f"{job_id}/audio.mp3")
        if has_audio:
            return {"job_id": job_id, "status": "processing"}
        raise HTTPException(404, "Job não encontrado")

    tmp_dir = Path(tempfile.mkdtemp(prefix="audio-to-text-download-"))
    output_path = tmp_dir / f"transcricao.{formato}"
    await run_in_threadpool(storage.download_file, f"{job_id}/transcricao.{formato}", output_path)

    return FileResponse(
        output_path,
        media_type=media_type,
        filename=output_path.name,
        background=BackgroundTask(shutil.rmtree, tmp_dir, ignore_errors=True),
    )


class WorkerPayload(BaseModel):
    job_id: str
    formato: str
    email: str | None = None

@app.post("/internal/worker")
async def process_job(payload: WorkerPayload):
    if not storage.STORAGE_ENABLED:
        raise HTTPException(500, "MinIO não configurado.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="audio-to-text-worker-"))
    input_path = tmp_dir / "audio.mp3"
    
    try:
        await run_in_threadpool(storage.download_file, f"{payload.job_id}/audio.mp3", input_path)
        output_path, media_type = await run_in_threadpool(_processar, input_path, payload.formato, tmp_dir)
        
        object_name = f"{payload.job_id}/{output_path.name}"
        await run_in_threadpool(storage.upload_file, object_name, output_path)
        
        if payload.email:
            try:
                await run_in_threadpool(mail.send_transcription_email, payload.email, output_path)
            except Exception as e:
                print(f"Erro ao enviar e-mail para {payload.email}: {e}")
                
        return {"status": "completed"}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _processar(input_path: Path, formato: str, tmp_dir: Path) -> tuple[Path, str]:
    try:
        wav_path = to_wav(input_path)
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from exc

    try:
        with _lock:
            segments = run_transcription(_whisper_model(), wav_path, LANGUAGE)
            if HF_TOKEN:
                turns = diarize(_diarization_pipeline(), wav_path)
                assign_speakers(segments, turns)
    finally:
        wav_path.unlink(missing_ok=True)

    if formato == "txt":
        output_path = tmp_dir / "transcricao.txt"
        write_txt(segments, output_path)
        media_type = "text/plain; charset=utf-8"
    else:
        output_path = tmp_dir / "transcricao.json"
        write_json(segments, output_path)
        media_type = "application/json"

    return output_path, media_type
