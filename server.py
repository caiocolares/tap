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

import jwt
import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

import auth
import mail
import storage
from jobs import JobRepository, QueueFullError
from processing import AudioProcessor, TranscriptionOptions
from settings import load_settings
from transcribe import AudioConversionError

_settings = load_settings()
MAX_UPLOAD_BYTES = _settings.max_upload_bytes
JOB_CLEANUP_INTERVAL_SECONDS = _settings.job_cleanup_interval_seconds
_capacity = threading.BoundedSemaphore(_settings.max_pending_jobs)
_repository = JobRepository(_settings.jobs_database_url) if _settings.jobs_database_url else None
_processor = AudioProcessor(_settings.device, _settings.hf_token)
logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
_auth_limiter = auth.LocalRateLimiter()


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
    auth.require_secret(_settings)
    if _repository is not None:
        await run_in_threadpool(_repository.initialize)
    cleanup_task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(
    title="audio-to-text",
    description="Transcreve áudio e identifica trocas de falante; jobs assíncronos são duráveis.",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


def get_current_email(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str:
    headers = {"WWW-Authenticate": "Bearer"}
    if credentials is None:
        raise HTTPException(401, "Token de acesso obrigatório", headers=headers)
    try:
        return auth.decode_token(credentials.credentials, _settings)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, "Token expirado", headers=headers) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, "Token inválido", headers=headers) from exc
    except ValueError as exc:
        raise HTTPException(503, "Autenticação não configurada") from exc


class AuthRequest(BaseModel):
    email: EmailStr


@app.post("/auth/request-code")
async def request_code(payload: AuthRequest, request: Request):
    if not _settings.smtp_host:
        raise HTTPException(503, "Serviço de e-mail indisponível")
    email = str(payload.email)
    keys = auth.rate_keys(email, request.client.host if request.client else "unknown", _settings)
    try:
        reserve = _repository.reserve_auth if _repository is not None else _auth_limiter.reserve
        await run_in_threadpool(reserve, keys, _settings.auth_window_seconds)
    except auth.RateLimitError as exc:
        raise HTTPException(
            429, "Limite de pedidos de acesso atingido", headers={"Retry-After": str(exc.retry_after)}
        ) from exc
    except psycopg.Error as exc:
        raise HTTPException(503, "Autenticação temporariamente indisponível") from exc
    try:
        token = auth.issue_token(email, _settings)
        await run_in_threadpool(mail.send_auth_code_email, email, token, settings=_settings)
    except Exception as exc:
        logger.warning("Não foi possível enviar o código de acesso")
        raise HTTPException(503, "Não foi possível enviar o código de acesso") from exc
    return {"message": "Um código de acesso foi gerado e enviado para o seu e-mail."}


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
async def transcrever(formato: Literal["txt", "json"], request: Request, email: str = Depends(get_current_email)):
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
async def transcrever_async(formato: Literal["txt", "json"], request: Request, email: str = Depends(get_current_email)):
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
            owner_email=email,
            notify=bool(_settings.smtp_host),
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
async def status_transcricao(job_id: str, email: str = Depends(get_current_email)):
    repository = _require_jobs()
    try:
        job = await run_in_threadpool(repository.get, job_id)
    except psycopg.Error as exc:
        raise HTTPException(503, "Consulta de jobs temporariamente indisponível") from exc
    if job is None or job.owner_email != email:
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
