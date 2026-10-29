"""Teste real de API + PostgreSQL + MinIO e queda abrupta de um worker.

A inferência é substituída: o teste comprova entrega, recuperação e publicação,
sem baixar pesos de modelos ou exigir GPU.
"""

import multiprocessing
import os
from dataclasses import replace
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import server
import storage
from jobs import JobRepository
from settings import load_settings
from worker import Worker

pytestmark = pytest.mark.integration


class BlockedProcessor:
    def __init__(self, started):
        self.started = started

    def process(self, input_path, format, directory, options):
        assert input_path.read_bytes() == b"original audio"
        self.started.send("processing")
        Event().wait()  # Processo encerrado pelo teste enquanto executa inferência.


def run_interrupted_worker(database_url, started):
    worker = Worker(JobRepository(database_url), BlockedProcessor(started), load_settings())
    worker.run_once()


class SuccessfulProcessor:
    def process(self, input_path, format, directory, options):
        assert input_path.read_bytes() == b"original audio"
        assert options.model == "tiny"
        assert options.language == "pt"
        output = directory / f"transcricao.{format}"
        output.write_text("áudio recuperado", encoding="utf-8")
        return output, "text/plain"


@pytest.fixture
def real_storage(monkeypatch):
    endpoint = os.environ.get("TAP_TEST_MINIO_ENDPOINT")
    if not endpoint:
        pytest.skip("TAP_TEST_MINIO_ENDPOINT não configurado")
    bucket = f"tap-test-{uuid4().hex}"
    values = {
        "MINIO_ENDPOINT": endpoint,
        "MINIO_ACCESS_KEY": os.environ.get("TAP_TEST_MINIO_ACCESS_KEY", "tap_test"),
        "MINIO_SECRET_KEY": os.environ.get("TAP_TEST_MINIO_SECRET_KEY", "tap_test_secret"),
        "MINIO_BUCKET": bucket,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
        monkeypatch.setattr(storage, key, value)
    monkeypatch.setenv("MINIO_SECURE", "false")
    monkeypatch.setattr(storage, "MINIO_SECURE", False)
    monkeypatch.setattr(storage, "STORAGE_ENABLED", True)
    monkeypatch.setattr(storage, "_client", None)
    storage.check_connection()
    yield
    client = storage._get_client()
    for obj in client.list_objects(bucket, recursive=True):
        client.remove_object(bucket, obj.object_name)
    client.remove_bucket(bucket)


def test_killed_worker_is_recovered_and_result_survives_api_restart(postgres_repo, real_storage, monkeypatch):
    configuration = replace(load_settings(), model="tiny", language="pt", hf_token=None)
    monkeypatch.setattr(server, "_settings", configuration)
    monkeypatch.setattr(server, "_repository", postgres_repo)
    with TestClient(server.app) as client:
        assert client.get("/ready").status_code == 200
        response = client.post("/async/transcricao/txt", content=b"original audio")
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        assert postgres_repo.get(job_id).status == "queued"

    context = multiprocessing.get_context("spawn")
    received, started = context.Pipe(duplex=False)
    process = context.Process(target=run_interrupted_worker, args=(postgres_repo.database_url, started))
    process.start()
    started.close()
    try:
        assert received.poll(20), "worker não iniciou o processamento"
        assert received.recv() == "processing"
        assert postgres_repo.get(job_id).status == "processing"
    finally:
        process.kill()
        process.join(timeout=5)
        received.close()
    assert not process.is_alive()

    # Avança a expiração no relógio do banco, sem esperas artificiais de 60s.
    with postgres_repo._connect() as conn:
        conn.execute(
            "UPDATE tap_jobs SET lease_until = clock_timestamp() - interval '1 second' WHERE job_id = %s",
            (job_id,),
        )
    restarted_repository = JobRepository(postgres_repo.database_url)
    assert Worker(restarted_repository, SuccessfulProcessor(), configuration).run_once()
    completed = restarted_repository.get(job_id)
    assert completed.status == "completed"
    assert completed.attempts == 2

    monkeypatch.setattr(server, "_repository", JobRepository(postgres_repo.database_url))
    with TestClient(server.app) as restarted_client:
        for _ in range(2):
            response = restarted_client.get(f"/async/status/{job_id}")
            assert response.status_code == 200
            assert response.text == "áudio recuperado"
        assert restarted_client.get("/ready").status_code == 200
