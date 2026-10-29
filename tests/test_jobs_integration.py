from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from jobs import JobRepository, QueueFullError

pytestmark = pytest.mark.integration


def test_initial_migration_is_safe_for_concurrent_startup(postgres_repo):
    with postgres_repo._connect() as conn:
        conn.execute("DROP TABLE tap_jobs")
        conn.execute("DROP TABLE tap_schema_migrations")
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: postgres_repo.initialize(), range(2)))
    assert postgres_repo.get(str(enqueue(postgres_repo))).status == "queued"


def enqueue(repository, *, max_attempts=3, max_pending=100):
    job_id = uuid4()
    repository.enqueue(job_id, "txt", f"{job_id}/audio.mp3", "tiny", "pt", False, max_attempts, max_pending)
    return job_id


def expire_lease(repository, job_id):
    with repository._connect() as conn:
        conn.execute(
            "UPDATE tap_jobs SET lease_until = clock_timestamp() - interval '1 second' WHERE job_id = %s", (job_id,)
        )


def test_queued_job_survives_new_repository(postgres_repo):
    job_id = enqueue(postgres_repo)
    reopened = JobRepository(postgres_repo.database_url)
    reopened.initialize()
    job = reopened.get(str(job_id))
    assert job.status == "queued"
    assert (job.model, job.language, job.diarization) == ("tiny", "pt", False)
    assert reopened.get("invalid-id") is None


def test_parallel_workers_never_claim_same_job(postgres_repo):
    identifiers = {enqueue(postgres_repo) for _ in range(8)}
    with ThreadPoolExecutor(max_workers=8) as pool:
        claimed = list(pool.map(lambda _: postgres_repo.claim(60, 3600), range(8)))
    assert {job.job_id for job in claimed} == identifiers
    assert all(job.attempts == 1 for job in claimed)
    assert postgres_repo.claim(60, 3600) is None


def test_global_admission_limit_is_atomic(postgres_repo):
    def submit(_):
        try:
            return enqueue(postgres_repo, max_pending=1)
        except QueueFullError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        accepted = [job for job in pool.map(submit, range(4)) if job is not None]
    assert len(accepted) == 1


def test_expired_lease_is_recovered_and_old_owner_is_fenced(postgres_repo):
    job_id = enqueue(postgres_repo)
    abandoned = postgres_repo.claim(60, 3600)
    expire_lease(postgres_repo, job_id)
    assert postgres_repo.heartbeat(abandoned, 60) is False
    assert postgres_repo.complete(abandoned, "stale", 3600) is False
    recovered = postgres_repo.claim(60, 3600)
    assert recovered.attempts == 2
    assert recovered.lease_token != abandoned.lease_token
    assert postgres_repo.fail(abandoned, 1, 3600) is False
    assert postgres_repo.complete(recovered, "winning-result", 3600) is True
    assert postgres_repo.complete(abandoned, "stale", 3600) is False
    assert postgres_repo.get(str(job_id)).result_object == "winning-result"
    assert postgres_repo.claim(60, 3600) is None


def test_retry_wait_and_terminal_error(postgres_repo):
    job_id = enqueue(postgres_repo, max_attempts=2)
    first = postgres_repo.claim(60, 3600)
    assert postgres_repo.fail(first, 60, 3600)
    assert postgres_repo.get(str(job_id)).status == "queued"
    assert postgres_repo.claim(60, 3600) is None
    with postgres_repo._connect() as conn:
        conn.execute(
            "UPDATE tap_jobs SET available_at = clock_timestamp() - interval '1 second' WHERE job_id = %s", (job_id,)
        )
    second = postgres_repo.claim(60, 3600)
    assert second.attempts == 2
    assert postgres_repo.fail(second, 1, 3600)
    failed = postgres_repo.get(str(job_id))
    assert failed.status == "error"
    assert failed.expires_at is not None
    assert failed.lease_token is None


def test_crash_during_last_attempt_becomes_terminal_error(postgres_repo):
    job_id = enqueue(postgres_repo, max_attempts=1)
    assert postgres_repo.claim(60, 3600).job_id == job_id
    expire_lease(postgres_repo, job_id)
    assert postgres_repo.claim(60, 3600) is None
    failed = postgres_repo.get(str(job_id))
    assert failed.status == "error"
    assert failed.expires_at is not None


def test_heartbeat_extends_lease_and_prune_removes_terminal_metadata(postgres_repo):
    job_id = enqueue(postgres_repo)
    job = postgres_repo.claim(60, 3600)
    assert postgres_repo.heartbeat(job, 120)
    assert postgres_repo.get(str(job_id)).lease_until > job.lease_until
    assert postgres_repo.complete(job, "result.txt", 3600)
    with postgres_repo._connect() as conn:
        conn.execute(
            "UPDATE tap_jobs SET expires_at = clock_timestamp() - interval '1 second' WHERE job_id = %s", (job_id,)
        )
    assert postgres_repo.get(str(job_id)).expired
    postgres_repo.prune()
    assert postgres_repo.get(str(job_id)) is None


def test_worker_entrypoint_starts_and_stops_gracefully(postgres_repo):
    import os
    import select
    import subprocess
    import sys

    environment = {
        **os.environ,
        "JOBS_DATABASE_URL": postgres_repo.database_url,
        "MINIO_ENDPOINT": "localhost:9000",
        "PYTHONUNBUFFERED": "1",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "worker"], env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    try:
        assert select.select([process.stdout], [], [], 10)[0], "worker não sinalizou inicialização"
        assert b"aguardando jobs" in process.stdout.readline()
        process.terminate()
        assert process.wait(timeout=5) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
