import asyncio
import threading
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import psycopg
import pytest
from fastapi.testclient import TestClient
from starlette.requests import ClientDisconnect, Request

import auth
import server
from jobs import JobRepository, QueueFullError
from transcribe import AudioConversionError


@pytest.fixture(autouse=True)
def dependencies(monkeypatch):
    repository = Mock(spec=JobRepository)
    repository.get.return_value = None
    monkeypatch.setattr(server, "_repository", repository)
    monkeypatch.setattr(
        server,
        "_settings",
        replace(
            server._settings, hf_token=None, jwt_secret="test-only-secret-not-for-production-123456", smtp_host=None
        ),
    )
    monkeypatch.setattr(server, "_auth_limiter", auth.LocalRateLimiter())
    monkeypatch.setattr(server, "_capacity", threading.BoundedSemaphore(2))
    monkeypatch.setattr(server.storage, "STORAGE_ENABLED", True)
    monkeypatch.setattr(server.storage, "check_connection", lambda: None)
    bucket = {}

    def upload(key, path):
        bucket[key] = Path(path).read_bytes()

    def download(key, path):
        Path(path).write_bytes(bucket[key])

    monkeypatch.setattr(server.storage, "upload_file", upload)
    monkeypatch.setattr(server.storage, "download_file", download)
    monkeypatch.setattr(server.storage, "delete_file", lambda key: bucket.pop(key, None))
    processor = Mock()

    def process(input_path, format, directory, options):
        output = directory / f"transcricao.{format}"
        output.write_text("resultado" if format == "txt" else '[{"text":"resultado"}]', encoding="utf-8")
        return output, "text/plain" if format == "txt" else "application/json"

    processor.process.side_effect = process
    monkeypatch.setattr(server, "_processor", processor)
    return repository, processor, bucket


@pytest.fixture
def client():
    headers = {"Authorization": f"Bearer {auth.issue_token('alice@example.com', server._settings)}"}
    with TestClient(server.app, headers=headers) as client:
        yield client


@pytest.mark.parametrize("route", ["/transcricao", "/async/transcricao"])
@pytest.mark.parametrize("format", ["txt", "json"])
def test_accepts_valid_audio(client, dependencies, route, format):
    repo, processor, bucket = dependencies
    response = client.post(f"{route}/{format}", content=b"audio")
    assert response.status_code == 200
    if route.startswith("/async"):
        assert response.json()["status"] == "processing"
        repo.enqueue.assert_called_once()
        args = repo.enqueue.call_args.args
        assert str(args[0]) == response.json()["job_id"]
        assert args[1] == format
        assert bucket[args[2]] == b"audio"
        assert args[3:6] == (server._settings.model, server._settings.language, False)
        assert repo.enqueue.call_args.kwargs == {"owner_email": "alice@example.com", "notify": False}
        processor.process.assert_not_called()
    else:
        assert "resultado" in response.text
        processor.process.assert_called_once()


@pytest.mark.parametrize("route", ["/transcricao/txt", "/async/transcricao/txt"])
@pytest.mark.parametrize("content,status", [(b"", 400), (b"123456", 413)])
def test_invalid_upload_releases_capacity(client, route, content, status, monkeypatch):
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 5)
    assert client.post(route, content=content).status_code == status
    assert client.post(route, content=b"audio").status_code == 200


@pytest.mark.parametrize("route", ["/transcricao/txt", "/async/transcricao/txt"])
def test_chunked_upload_obeys_size_limit(client, route, monkeypatch):
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 5)
    assert client.post(route, content=iter([b"123", b"456"])).status_code == 413


@pytest.mark.parametrize("route", ["/transcricao/xml", "/async/transcricao/xml"])
def test_invalid_format(client, route):
    assert client.post(route, content=b"audio").status_code == 422


@pytest.mark.parametrize("route", ["/transcricao/txt", "/async/transcricao/txt"])
def test_full_local_capacity(client, route, monkeypatch):
    capacity = threading.BoundedSemaphore(1)
    monkeypatch.setattr(server, "_capacity", capacity)
    capacity.acquire()
    try:
        response = client.post(route, content=b"audio")
        assert response.status_code == 503
        assert response.headers["retry-after"] == "5"
    finally:
        capacity.release()


def test_missing_durable_dependencies_never_falls_back_to_memory(client, monkeypatch):
    monkeypatch.setattr(server, "_repository", None)
    assert client.post("/async/transcricao/txt", content=b"audio").status_code == 503
    assert client.get("/async/status/anything").status_code == 503
    assert client.get("/health").status_code == 200
    assert client.get("/ready").json()["async_enabled"] is False


def test_missing_object_storage_rejects_async_submission(client, monkeypatch):
    monkeypatch.setattr(server.storage, "STORAGE_ENABLED", False)
    assert client.post("/async/transcricao/txt", content=b"audio").status_code == 503


def test_light_api_explicitly_rejects_local_inference(client, monkeypatch):
    monkeypatch.setattr(server, "_settings", replace(server._settings, api_async_only=True))
    response = client.post("/transcricao/txt", content=b"audio")
    assert response.status_code == 503
    assert "/async/transcricao" in response.text


def test_full_global_queue_removes_rejected_upload(client, dependencies):
    repo, _, bucket = dependencies
    repo.enqueue.side_effect = QueueFullError
    response = client.post("/async/transcricao/txt", content=b"audio")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert not bucket


def test_ambiguous_commit_preserves_input_for_recovery(client, dependencies):
    repo, _, bucket = dependencies
    repo.enqueue.side_effect = psycopg.OperationalError("connection lost during commit")
    assert client.post("/async/transcricao/txt", content=b"audio").status_code == 503
    assert list(bucket.values()) == [b"audio"]


@pytest.mark.parametrize("state", ["queued", "processing"])
def test_pending_jobs_preserve_polling_contract(client, dependencies, job_factory, state):
    repo, _, _ = dependencies
    job = job_factory(status=state)
    repo.get.return_value = job
    assert client.get(f"/async/status/{job.job_id}").json() == {"job_id": str(job.job_id), "status": "processing"}


def test_repeated_downloads_do_not_consume_result(client, dependencies, job_factory):
    repo, _, bucket = dependencies
    job = job_factory(status="completed", result_object="result/transcricao.txt")
    repo.get.return_value = job
    bucket[job.result_object] = b"resultado duravel"
    for _ in range(2):
        response = client.get(f"/async/status/{job.job_id}")
        assert response.status_code == 200
        assert response.text == "resultado duravel"
    assert bucket[job.result_object] == b"resultado duravel"


def test_unknown_expired_failed_and_unavailable_jobs(client, dependencies, job_factory):
    repo, _, _ = dependencies
    assert client.get("/async/status/missing").status_code == 404
    repo.get.return_value = job_factory(expired=True)
    assert client.get("/async/status/expired").status_code == 410
    repo.get.return_value = job_factory(status="error", error="Falha no processamento do áudio")
    assert client.get("/async/status/error").status_code == 500
    repo.get.side_effect = psycopg.OperationalError("unavailable")
    assert client.get("/async/status/unavailable").status_code == 503


def test_readiness_reports_database_outage(client, dependencies):
    repo, _, _ = dependencies
    repo.ping.side_effect = psycopg.OperationalError("unavailable")
    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200


def test_sync_audio_conversion_failure(client, dependencies):
    _, processor, _ = dependencies
    processor.process.side_effect = AudioConversionError("invalid audio")
    assert client.post("/transcricao/txt", content=b"audio").status_code == 422


@pytest.mark.parametrize("asynchronous", [False, True])
def test_disconnect_cleans_upload_and_releases_capacity(tmp_path, monkeypatch, asynchronous):
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()
    monkeypatch.setattr(server.tempfile, "mkdtemp", lambda **kwargs: str(upload_dir))
    capacity = threading.BoundedSemaphore(1)
    monkeypatch.setattr(server, "_capacity", capacity)
    messages = iter(
        [
            {"type": "http.request", "body": b"partial", "more_body": True},
            {"type": "http.disconnect"},
        ]
    )

    async def receive():
        return next(messages)

    request = Request({"type": "http", "headers": []}, receive)
    operation = server.transcrever_async if asynchronous else server.transcrever
    with pytest.raises(ClientDisconnect):
        asyncio.run(operation("txt", request, email="alice@example.com"))
    assert not upload_dir.exists()
    assert capacity.acquire(blocking=False)
    capacity.release()


def test_failed_download_cleans_temporary_copy(client, dependencies, job_factory, tmp_path, monkeypatch):
    repo, _, _ = dependencies
    repo.get.return_value = job_factory(status="completed", result_object="missing")
    directory = tmp_path / "download"
    directory.mkdir()
    monkeypatch.setattr(server.tempfile, "mkdtemp", lambda **kwargs: str(directory))
    with pytest.raises(KeyError):
        client.get("/async/status/result")
    assert not directory.exists()


@pytest.mark.parametrize(
    "route,method",
    [
        ("/transcricao/txt", "post"),
        ("/async/transcricao/txt", "post"),
        ("/async/status/missing", "get"),
    ],
)
def test_missing_and_invalid_tokens_are_rejected(client, route, method):
    for authorization in ["", "Bearer invalid", "Basic something"]:
        response = getattr(client, method)(route, headers={"Authorization": authorization})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


def test_job_is_never_exposed_to_another_user_or_when_unowned(client, dependencies, job_factory):
    repo, _, _ = dependencies
    for owner in ["bob@example.com", None]:
        for status in ["queued", "processing", "completed", "error"]:
            repo.get.return_value = job_factory(owner_email=owner, status=status)
            assert client.get("/async/status/private").status_code == 404


def test_authentication_request_sends_token_only_by_mail(client, dependencies, monkeypatch, caplog):
    monkeypatch.setattr(server, "_settings", replace(server._settings, smtp_host="smtp.example.com"))
    sender = Mock()
    monkeypatch.setattr(server.mail, "send_auth_code_email", sender)
    response = client.post("/auth/request-code", json={"email": "alice@example.com"})
    assert response.status_code == 200
    email, token = sender.call_args.args
    assert email == "alice@example.com"
    assert auth.decode_token(token, server._settings) == email
    assert token not in response.text
    assert token not in caplog.text


def test_auth_requests_validate_email_and_do_not_claim_delivery_without_smtp(client):
    assert client.post("/auth/request-code", json={"email": "not-email"}).status_code == 422
    assert client.post("/auth/request-code", json={"email": "alice@example.com"}).status_code == 503


def test_smtp_failure_does_not_log_token_or_report_success(client, monkeypatch, caplog):
    monkeypatch.setattr(server, "_settings", replace(server._settings, smtp_host="smtp.example.com"))
    monkeypatch.setattr(server.mail, "send_auth_code_email", Mock(side_effect=RuntimeError("private-server-error")))
    response = client.post("/auth/request-code", json={"email": "alice@example.com"})
    assert response.status_code == 503
    assert "private-server-error" not in response.text + caplog.text


def test_auth_endpoint_limits_requests_without_database(client, monkeypatch):
    monkeypatch.setattr(server, "_repository", None)
    monkeypatch.setattr(
        server, "_settings", replace(server._settings, smtp_host="smtp.example.com", auth_max_requests=1)
    )
    sender = Mock()
    monkeypatch.setattr(server.mail, "send_auth_code_email", sender)
    assert client.post("/auth/request-code", json={"email": "alice@example.com"}).status_code == 200
    rejected = client.post("/auth/request-code", json={"email": "alice@example.com"})
    assert rejected.status_code == 429
    assert int(rejected.headers["retry-after"]) > 0
    sender.assert_called_once()


def test_api_startup_requires_explicit_secret(monkeypatch):
    monkeypatch.setattr(server, "_settings", replace(server._settings, jwt_secret=None))
    with pytest.raises(ValueError, match="JWT_SECRET"), TestClient(server.app):
        pass


def test_removed_legacy_internal_worker_route_is_not_exposed(client):
    assert client.post("/internal/worker", json={"job_id": "anything"}).status_code == 404
