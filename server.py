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

MODEL_SIZE = os.environ.get("WHISPER_MODEL", "medium")
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
LANGUAGE = os.environ.get("WHISPER_LANGUAGE") or None
HF_TOKEN = os.environ.get("HF_TOKEN")

app = FastAPI(
    title="audio-to-text",
    description="Recebe um áudio (mp3) no body e devolve a transcrição, identificando a troca de speaker.",
)

# faster-whisper/pyannote não são seguros para chamadas concorrentes na mesma
# instância; o modelo/pipeline ficam em cache e as inferências são serializadas.
_lock = threading.Lock()
_cache: dict = {}
_jobs: dict = {}


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


@app.post("/transcricao/{formato}")
async def transcrever(formato: Literal["txt", "json"], request: Request):
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
async def transcrever_async(formato: Literal["txt", "json"], request: Request, background_tasks: BackgroundTasks):
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
        _jobs[job_id] = {"status": "processing"}
        background_tasks.add_task(_background_process, job_id, input_path, formato, tmp_dir)

        return {"job_id": job_id, "status": "processing"}
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


@app.get("/async/status/{job_id}")
async def status_transcricao(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")

    if job["status"] == "processing":
        return {"job_id": job_id, "status": "processing"}
    elif job["status"] == "error":
        raise HTTPException(500, f"Erro no processamento: {job.get('error')}")
    elif job["status"] == "completed":
        output_path = job["output_path"]
        tmp_dir = job["tmp_dir"]
        media_type = job["media_type"]

        # O BackgroundTask apagará o temp_dir inteiro APÓS a resposta ser enviada
        return FileResponse(
            output_path,
            media_type=media_type,
            filename=output_path.name,
            background=BackgroundTask(shutil.rmtree, tmp_dir, ignore_errors=True),
        )


async def _background_process(job_id: str, input_path: Path, formato: str, tmp_dir: Path):
    try:
        output_path, media_type = await run_in_threadpool(_processar, input_path, formato, tmp_dir)
        _jobs[job_id] = {
            "status": "completed",
            "output_path": output_path,
            "media_type": media_type,
            "tmp_dir": tmp_dir
        }
    except Exception as e:
        _jobs[job_id] = {"status": "error", "error": str(e)}
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
