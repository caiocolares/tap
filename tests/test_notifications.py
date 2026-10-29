from dataclasses import replace
from threading import Event
from unittest.mock import Mock

import pytest

import notifications
from jobs import JobRepository
from notifications import NotificationDispatcher
from settings import load_settings


@pytest.fixture
def dispatcher(monkeypatch, job_factory):
    repo = Mock(spec=JobRepository)
    job = job_factory(status="completed", result_object="result.txt", notification_attempts=1)
    repo.claim_notification.return_value = job
    settings = replace(load_settings(), smtp_host="smtp.example.com")
    sender = Mock()
    monkeypatch.setattr(notifications.mail, "send_transcription_email", sender)
    monkeypatch.setattr(notifications.storage, "download_file", lambda key, path: path.write_text("resultado"))
    return NotificationDispatcher(repo, settings), repo, sender, job


def test_sends_completed_result_without_running_inference(dispatcher):
    service, repo, sender, job = dispatcher
    assert service.run_once()
    assert sender.call_args.args[0] == job.owner_email
    assert sender.call_args.kwargs["message_id"] == f"<transcription-{job.job_id}@tap.local>"
    assert not sender.call_args.args[1].exists()
    repo.finish_notification.assert_called_once_with(job, sent=True, max_attempts=service.settings.job_max_attempts)
    repo.claim.assert_not_called()
    repo.fail.assert_not_called()


def test_smtp_failure_retries_only_the_notification(dispatcher, caplog):
    service, repo, sender, job = dispatcher
    sender.side_effect = RuntimeError("sensitive smtp error")
    assert service.run_once()
    repo.finish_notification.assert_called_once_with(
        job,
        sent=False,
        max_attempts=service.settings.job_max_attempts,
        retry_seconds=service.settings.job_retry_seconds,
    )
    repo.fail.assert_not_called()
    repo.claim.assert_not_called()
    assert "sensitive smtp error" not in caplog.text


def test_missing_smtp_does_not_consume_notifications(dispatcher):
    service, repo, sender, _ = dispatcher
    service.settings = replace(service.settings, smtp_host=None)
    assert service.run_once() is False
    repo.claim_notification.assert_not_called()
    sender.assert_not_called()


def test_lost_notification_lease_does_not_send(dispatcher, monkeypatch):
    service, repo, sender, _ = dispatcher
    started = Event()

    def lose_lease(job, done, lost):
        lost.set()
        started.set()

    monkeypatch.setattr(service, "_heartbeat", lose_lease)

    def download(key, path):
        assert started.wait(2)
        path.write_text("resultado")

    monkeypatch.setattr(notifications.storage, "download_file", download)
    service.run_once()
    sender.assert_not_called()
    repo.finish_notification.assert_not_called()
