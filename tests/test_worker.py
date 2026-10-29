from dataclasses import replace
from threading import Event, Thread
from unittest.mock import Mock

import psycopg
import pytest

import worker
from jobs import JobRepository
from settings import load_settings
from worker import Worker


@pytest.fixture
def setup_worker(monkeypatch, job_factory):
    repository = Mock(spec=JobRepository)
    job = job_factory()
    repository.claim.return_value = job
    repository.complete.return_value = True
    repository.fail.return_value = True
    processor = Mock()
    bucket = {}
    monkeypatch.setattr(worker.storage, "download_file", lambda key, path: path.write_bytes(b"audio"))
    monkeypatch.setattr(worker.storage, "upload_file", lambda key, path: bucket.update({key: path.read_bytes()}))
    monkeypatch.setattr(worker.storage, "delete_file", lambda key: bucket.pop(key, None))

    def process(input_path, format, directory, options):
        output = directory / f"transcricao.{format}"
        output.write_text("resultado", encoding="utf-8")
        return output, "text/plain"

    processor.process.side_effect = process
    instance = Worker(repository, processor, load_settings())
    return instance, repository, processor, bucket, job


def test_worker_publishes_only_attempt_specific_result(setup_worker):
    instance, repo, processor, bucket, job = setup_worker
    assert instance.run_once() is True
    key = f"{job.job_id}/results/{job.lease_token}/{job.filename}"
    assert bucket[key] == b"resultado"
    repo.complete.assert_called_once_with(job, key, instance.settings.job_ttl_seconds)
    options = processor.process.call_args.args[3]
    assert (options.model, options.language, options.diarization) == (job.model, job.language, job.diarization)
    assert not processor.process.call_args.args[2].exists()


def test_empty_queue_does_not_run_inference(setup_worker):
    instance, repo, processor, _, _ = setup_worker
    repo.claim.return_value = None
    assert instance.run_once() is False
    processor.process.assert_not_called()


def test_failure_schedules_bounded_backoff_and_cleans_files(setup_worker):
    instance, repo, processor, bucket, job = setup_worker
    processor.process.side_effect = RuntimeError("private backend failure")
    assert instance.run_once() is True
    repo.fail.assert_called_once_with(job, instance.settings.job_retry_seconds, instance.settings.job_ttl_seconds)
    assert not bucket
    assert not processor.process.call_args.args[2].exists()


def test_lost_lease_discards_result_without_publishing(setup_worker, monkeypatch):
    instance, repo, _, bucket, _ = setup_worker
    monkeypatch.setattr(instance, "_heartbeat", lambda job, done, lost: lost.set())
    assert instance.run_once() is True
    assert not bucket
    repo.complete.assert_not_called()


def test_stale_worker_cannot_leave_published_result(setup_worker):
    instance, repo, _, bucket, _ = setup_worker
    repo.complete.return_value = False
    instance.run_once()
    assert not bucket


def test_ambiguous_completion_preserves_object(setup_worker):
    instance, repo, _, bucket, _ = setup_worker
    repo.complete.side_effect = psycopg.OperationalError("commit reply lost")
    repo.fail.return_value = False
    instance.run_once()
    assert list(bucket.values()) == [b"resultado"]


@pytest.mark.parametrize("outcome", [False, psycopg.OperationalError("connection lost")])
def test_heartbeat_marks_lost_reservation(setup_worker, outcome):
    instance, repo, _, _, job = setup_worker
    instance.settings = replace(instance.settings, job_heartbeat_seconds=0.001)
    if isinstance(outcome, Exception):
        repo.heartbeat.side_effect = outcome
    else:
        repo.heartbeat.return_value = outcome
    done, lost = Event(), Event()
    thread = Thread(target=instance._heartbeat, args=(job, done, lost))
    thread.start()
    try:
        assert lost.wait(timeout=2)
    finally:
        done.set()
        thread.join(timeout=2)
