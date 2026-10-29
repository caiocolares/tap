"""Isolamento de credenciais e infraestrutura de teste optativa."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

os.environ["PYTHON_DOTENV_DISABLED"] = "1"


@pytest.fixture
def job_factory():
    from jobs import Job

    def create(**overrides):
        now = datetime.now(UTC)
        values = dict(
            job_id=uuid4(),
            status="processing",
            format="txt",
            input_object="input/audio.mp3",
            model="tiny",
            language="pt",
            diarization=False,
            attempts=1,
            max_attempts=3,
            available_at=now,
            lease_token=uuid4(),
            lease_until=now,
            result_object=None,
            error=None,
            created_at=now,
            updated_at=now,
            expires_at=None,
        )
        values.update(overrides)
        return Job(**values)

    return create


@pytest.fixture
def postgres_repo():
    from jobs import JobRepository

    url = os.environ.get("TAP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("TAP_TEST_DATABASE_URL não configurado (use um banco exclusivo para testes)")
    repo = JobRepository(url)
    repo.initialize()
    with repo._connect() as conn:
        conn.execute("TRUNCATE tap_jobs")
    yield repo
    with repo._connect() as conn:
        conn.execute("TRUNCATE tap_jobs")
