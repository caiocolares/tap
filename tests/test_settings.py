import importlib
import os

import pytest

import settings
import storage


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in (
        "WHISPER_DEVICE",
        "MINIO_ENDPOINT",
        "MINIO_BUCKET",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "MINIO_SECURE",
        "MAX_UPLOAD_BYTES",
        "MAX_PENDING_JOBS",
        "FFMPEG_TIMEOUT_SECONDS",
        "JOB_TTL_SECONDS",
        "JOB_CLEANUP_INTERVAL_SECONDS",
        "JOBS_DATABASE_URL",
        "MAX_QUEUED_JOBS",
        "JOB_MAX_ATTEMPTS",
        "JOB_LEASE_SECONDS",
        "JOB_HEARTBEAT_SECONDS",
        "JOB_RETRY_SECONDS",
        "WORKER_POLL_SECONDS",
        "API_ASYNC_ONLY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_storage_loads_dotenv_before_reading_connection_settings(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("MINIO_ENDPOINT=from-dotenv:9000\nMINIO_ACCESS_KEY=test-key\nMINIO_SECRET_KEY=test-secret\n")
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED")
    original_loader = settings.load_dotenv
    monkeypatch.setattr(settings, "load_dotenv", lambda **kwargs: original_loader(env_file))
    try:
        importlib.reload(storage)
        assert storage.STORAGE_ENABLED is True
        assert storage.MINIO_ENDPOINT == "from-dotenv:9000"
        assert storage.MINIO_ACCESS_KEY == "test-key"
        assert storage.MINIO_SECRET_KEY == "test-secret"
    finally:
        # load_dotenv altera os.environ; remover explicitamente antes do reload.
        monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
        for name in ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"):
            os.environ.pop(name, None)
        importlib.reload(storage)


def test_environment_takes_precedence_over_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("MAX_UPLOAD_BYTES=10\n")
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "20")
    assert settings.load_settings(env_file).max_upload_bytes == 20


@pytest.mark.parametrize(
    "name",
    [
        "MAX_UPLOAD_BYTES",
        "MAX_PENDING_JOBS",
        "FFMPEG_TIMEOUT_SECONDS",
        "JOB_TTL_SECONDS",
        "JOB_CLEANUP_INTERVAL_SECONDS",
        "MAX_QUEUED_JOBS",
        "JOB_MAX_ATTEMPTS",
        "JOB_LEASE_SECONDS",
        "JOB_HEARTBEAT_SECONDS",
        "JOB_RETRY_SECONDS",
        "WORKER_POLL_SECONDS",
    ],
)
@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_rejects_invalid_resource_limits(name, value, monkeypatch):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        settings.load_settings()


@pytest.mark.parametrize(
    "name,value", [("WHISPER_DEVICE", "invalid"), ("MINIO_SECURE", "yes"), ("API_ASYNC_ONLY", "yes")]
)
def test_rejects_invalid_options(name, value, monkeypatch):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        settings.load_settings()


def test_rejects_incomplete_storage_credentials(monkeypatch):
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test-key")
    with pytest.raises(ValueError, match="MINIO_SECRET_KEY"):
        settings.load_settings()


def test_heartbeat_must_fit_inside_lease(monkeypatch):
    monkeypatch.setenv("JOB_HEARTBEAT_SECONDS", "60")
    monkeypatch.setenv("JOB_LEASE_SECONDS", "60")
    with pytest.raises(ValueError, match="JOB_HEARTBEAT_SECONDS"):
        settings.load_settings()


def test_database_requires_postgres_url(monkeypatch):
    monkeypatch.setenv("JOBS_DATABASE_URL", "sqlite:///jobs.db")
    with pytest.raises(ValueError, match="JOBS_DATABASE_URL"):
        settings.load_settings()
