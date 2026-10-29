"""Configuração compartilhada, carregada antes de inicializar os serviços."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} deve ser um inteiro positivo") from exc
    if value <= 0:
        raise ValueError(f"{name} deve ser um inteiro positivo")
    return value


@dataclass(frozen=True)
class Settings:
    model: str
    device: str
    language: str | None
    hf_token: str | None
    minio_endpoint: str | None
    minio_access_key: str | None
    minio_secret_key: str | None
    minio_bucket: str
    minio_secure: bool
    max_upload_bytes: int
    max_pending_jobs: int
    ffmpeg_timeout_seconds: int
    job_ttl_seconds: int
    job_cleanup_interval_seconds: int
    jobs_database_url: str | None
    max_queued_jobs: int
    job_max_attempts: int
    job_lease_seconds: int
    job_heartbeat_seconds: int
    job_retry_seconds: int
    worker_poll_seconds: int
    api_async_only: bool
    jwt_secret: str | None
    jwt_ttl_seconds: int
    auth_window_seconds: int
    auth_max_requests: int
    auth_ip_max_requests: int
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    smtp_from: str
    smtp_security: str
    smtp_timeout_seconds: int


def load_settings(env_file: Path | None = None) -> Settings:
    # Variáveis injetadas pelo ambiente têm precedência sobre o arquivo .env.
    load_dotenv(dotenv_path=env_file)
    device = os.environ.get("WHISPER_DEVICE", "cpu")
    if device not in {"cpu", "cuda", "mps"}:
        raise ValueError("WHISPER_DEVICE deve ser cpu, cuda ou mps")
    secure = os.environ.get("MINIO_SECURE", "false").lower()
    if secure not in {"true", "false"}:
        raise ValueError("MINIO_SECURE deve ser true ou false")
    access_key = os.environ.get("MINIO_ACCESS_KEY") or None
    secret_key = os.environ.get("MINIO_SECRET_KEY") or None
    if bool(access_key) != bool(secret_key):
        raise ValueError("MINIO_ACCESS_KEY e MINIO_SECRET_KEY devem ser informados juntos")
    database_url = os.environ.get("JOBS_DATABASE_URL") or None
    if database_url and not database_url.startswith(("postgresql://", "postgres://")):
        raise ValueError("JOBS_DATABASE_URL deve ser uma URL PostgreSQL")
    lease_seconds = _positive_int("JOB_LEASE_SECONDS", 60)
    heartbeat_seconds = _positive_int("JOB_HEARTBEAT_SECONDS", 10)
    if heartbeat_seconds >= lease_seconds:
        raise ValueError("JOB_HEARTBEAT_SECONDS deve ser menor que JOB_LEASE_SECONDS")
    async_only = os.environ.get("API_ASYNC_ONLY", "false").lower()
    if async_only not in {"true", "false"}:
        raise ValueError("API_ASYNC_ONLY deve ser true ou false")
    smtp_security = os.environ.get("SMTP_SECURITY", "starttls").lower()
    if smtp_security not in {"starttls", "ssl", "none"}:
        raise ValueError("SMTP_SECURITY deve ser starttls, ssl ou none")
    smtp_user = os.environ.get("SMTP_USER") or None
    smtp_password = os.environ.get("SMTP_PASSWORD") or None
    if bool(smtp_user) != bool(smtp_password):
        raise ValueError("SMTP_USER e SMTP_PASSWORD devem ser informados juntos")

    return Settings(
        model=os.environ.get("WHISPER_MODEL", "small"),
        device=device,
        language=os.environ.get("WHISPER_LANGUAGE") or None,
        hf_token=os.environ.get("HF_TOKEN") or None,
        minio_endpoint=os.environ.get("MINIO_ENDPOINT") or None,
        minio_access_key=access_key,
        minio_secret_key=secret_key,
        minio_bucket=os.environ.get("MINIO_BUCKET", "audio-to-text"),
        minio_secure=secure == "true",
        max_upload_bytes=_positive_int("MAX_UPLOAD_BYTES", 100 * 1024 * 1024),
        max_pending_jobs=_positive_int("MAX_PENDING_JOBS", 8),
        ffmpeg_timeout_seconds=_positive_int("FFMPEG_TIMEOUT_SECONDS", 300),
        job_ttl_seconds=_positive_int("JOB_TTL_SECONDS", 3600),
        job_cleanup_interval_seconds=_positive_int("JOB_CLEANUP_INTERVAL_SECONDS", 60),
        jobs_database_url=database_url,
        max_queued_jobs=_positive_int("MAX_QUEUED_JOBS", 100),
        job_max_attempts=_positive_int("JOB_MAX_ATTEMPTS", 3),
        job_lease_seconds=lease_seconds,
        job_heartbeat_seconds=heartbeat_seconds,
        job_retry_seconds=_positive_int("JOB_RETRY_SECONDS", 5),
        worker_poll_seconds=_positive_int("WORKER_POLL_SECONDS", 1),
        api_async_only=async_only == "true",
        jwt_secret=os.environ.get("JWT_SECRET") or None,
        jwt_ttl_seconds=_positive_int("JWT_TTL_SECONDS", 86400),
        auth_window_seconds=_positive_int("AUTH_WINDOW_SECONDS", 900),
        auth_max_requests=_positive_int("AUTH_MAX_REQUESTS", 3),
        auth_ip_max_requests=_positive_int("AUTH_IP_MAX_REQUESTS", 20),
        smtp_host=os.environ.get("SMTP_HOST") or None,
        smtp_port=_positive_int("SMTP_PORT", 587),
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        smtp_from=os.environ.get("SMTP_FROM", "nao-responda@exemplo.com"),
        smtp_security=smtp_security,
        smtp_timeout_seconds=_positive_int("SMTP_TIMEOUT_SECONDS", 30),
    )
