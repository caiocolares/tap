#!/usr/bin/env python3
"""API de transcrição: inferência síncrona e submissão à fila durável."""

import asyncio
import logging
import shutil
import tempfile
import threading
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal
from uuid import uuid4

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

import jwt
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import pika
import json

import storage
<<<<<<< HEAD
from jobs import JobRepository, QueueFullError
from processing import AudioProcessor, TranscriptionOptions
from settings import load_settings
from transcribe import AudioConversionError
=======
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
>>>>>>> origin/develop

_settings = load_settings()
MAX_UPLOAD_BYTES = _settings.max_upload_bytes
JOB_CLEANUP_INTERVAL_SECONDS = _settings.job_cleanup_interval_seconds
_capacity = threading.BoundedSemaphore(_settings.max_pending_jobs)
_repository = JobRepository(_settings.jobs_database_url) if _settings.jobs_database_url else None
_processor = AudioProcessor(_settings.device, _settings.hf_token)
logger = logging.getLogger(__name__)


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(JOB_CLEANUP_INTERVAL_SECONDS)
        try:
            if _repository is not None:
                await run_in_threadpool(_repository.prune)
        except Exception:
            logger.exception("Não foi possível limpar os metadados expirados")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _repository is not None:
        await run_in_threadpool(_repository.initialize)
    cleanup_task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task

<<<<<<< HEAD
=======
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "small")
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
LANGUAGE = os.environ.get("WHISPER_LANGUAGE") or None
HF_TOKEN = os.environ.get("HF_TOKEN")
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secreto-mudar-em-producao")
>>>>>>> origin/develop

app = FastAPI(
    title="audio-to-text",
    description="Transcreve áudio e identifica trocas de falante; jobs assíncronos são duráveis.",
    lifespan=lifespan,
)

<<<<<<< HEAD
=======
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

>>>>>>> origin/develop

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


<<<<<<< HEAD
@app.get("/ready")
async def ready():
    if _repository is not None:
        try:
            _require_jobs()
            await run_in_threadpool(_repository.ping)
            await run_in_threadpool(storage.check_connection)
        except Exception as exc:
            raise HTTPException(503, "Dependências da fila indisponíveis") from exc
    return {"status": "ok", "async_enabled": _repository is not None}


def _reserve_capacity() -> None:
    if not _capacity.acquire(blocking=False):
        raise HTTPException(
            503,
            "Capacidade de processamento esgotada; tente novamente mais tarde",
            headers={"Retry-After": "5"},
        )


def _require_jobs() -> JobRepository:
    if _repository is None or not storage.STORAGE_ENABLED:
        raise HTTPException(503, "A API assíncrona exige JOBS_DATABASE_URL e MINIO_ENDPOINT")
    return _repository


async def _receive_audio(request: Request, input_path: Path) -> None:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            size = int(content_length)
        except ValueError as exc:
            raise HTTPException(400, "Content-Length inválido") from exc
        if size < 0:
            raise HTTPException(400, "Content-Length inválido")
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Áudio excede o tamanho máximo permitido")

    bytes_written = 0
    with input_path.open("wb") as audio:
        async for chunk in request.stream():
            bytes_written += len(chunk)
            if bytes_written > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "Áudio excede o tamanho máximo permitido")
            await run_in_threadpool(audio.write, chunk)
    if bytes_written == 0:
        raise HTTPException(400, "Corpo da requisição vazio: envie o áudio (mp3) como body.")
=======
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
>>>>>>> origin/develop


def _processar(input_path: Path, formato: str, tmp_dir: Path) -> tuple[Path, str]:
    try:
        return _processor.process(
            input_path,
            formato,
            tmp_dir,
            TranscriptionOptions(_settings.model, _settings.language, bool(_settings.hf_token)),
        )
    except AudioConversionError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/transcricao/{formato}")
async def transcrever(formato: Literal["txt", "json"], request: Request):
    if _settings.api_async_only:
        raise HTTPException(503, "Esta instância atende apenas a API assíncrona; use /async/transcricao/{formato}")
    _reserve_capacity()
    tmp_dir = None
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="audio-to-text-"))
        input_path = tmp_dir / "audio.mp3"
        await _receive_audio(request, input_path)
        if storage.STORAGE_ENABLED:
            await run_in_threadpool(storage.upload_file, f"{uuid4()}/audio.mp3", input_path)
        output_path, media_type = await run_in_threadpool(_processar, input_path, formato, tmp_dir)
        return FileResponse(
            output_path,
            media_type=media_type,
            filename=output_path.name,
            background=BackgroundTask(shutil.rmtree, tmp_dir, ignore_errors=True),
        )
    except BaseException:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    finally:
        _capacity.release()


@app.post("/async/transcricao/{formato}")
async def transcrever_async(formato: Literal["txt", "json"], request: Request):
    repository = _require_jobs()
    _reserve_capacity()
    tmp_dir = None
    job_id = uuid4()
    input_object = f"{job_id}/audio.mp3"
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="audio-to-text-async-"))
        await _receive_audio(request, tmp_dir / "audio.mp3")
        await run_in_threadpool(storage.upload_file, input_object, tmp_dir / "audio.mp3")
        await run_in_threadpool(
            repository.enqueue,
            job_id,
            formato,
            input_object,
            _settings.model,
            _settings.language,
            bool(_settings.hf_token),
            _settings.job_max_attempts,
            _settings.max_queued_jobs,
        )
        # Mantém o contrato existente: queued e processing são apresentados como processing.
        return {"job_id": str(job_id), "status": "processing"}
    except QueueFullError as exc:
        try:
            await run_in_threadpool(storage.delete_file, input_object)
        except Exception:
            logger.exception("Não foi possível remover upload recusado %s", job_id)
        raise HTTPException(503, "Fila de processamento cheia", headers={"Retry-After": "5"}) from exc
    except (HTTPException, ClientDisconnect):
        raise
    except Exception as exc:
        # Não apague o upload se o commit tiver resposta ambígua: o job pode
        # estar confirmado e será retomado pelo worker. Lifecycle remove órfãos.
        logger.exception("Não foi possível confirmar a submissão do job %s", job_id)
        raise HTTPException(503, "Não foi possível confirmar a submissão do áudio") from exc
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        _capacity.release()


@app.get("/async/status/{job_id}")
async def status_transcricao(job_id: str):
    repository = _require_jobs()
    try:
        job = await run_in_threadpool(repository.get, job_id)
    except psycopg.Error as exc:
        raise HTTPException(503, "Consulta de jobs temporariamente indisponível") from exc
    if job is None:
        raise HTTPException(404, "Job não encontrado")
    if job.expired:
        raise HTTPException(410, "Resultado expirado")
    if job.status in {"queued", "processing"}:
        return {"job_id": job_id, "status": "processing"}
    if job.status == "error":
        raise HTTPException(500, f"Erro no processamento: {job.error}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="audio-to-text-download-"))
    try:
        await run_in_threadpool(storage.download_file, job.result_object, tmp_dir / job.filename)
    except BaseException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    return FileResponse(
        tmp_dir / job.filename,
        media_type=job.media_type,
        filename=job.filename,
        background=BackgroundTask(shutil.rmtree, tmp_dir, ignore_errors=True),
    )
