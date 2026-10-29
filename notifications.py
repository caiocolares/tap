"""Entrega durável de transcrições, independente da inferência: python -m notifications."""

import logging
import signal
import tempfile
from pathlib import Path
from threading import Event, Thread

import mail
import storage
from jobs import Job, JobRepository
from settings import Settings, load_settings

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(self, repository: JobRepository, settings: Settings):
        self.repository = repository
        self.settings = settings
        self.stop = Event()

    def _heartbeat(self, job: Job, done: Event, lost: Event) -> None:
        while not done.wait(self.settings.job_heartbeat_seconds):
            try:
                if not self.repository.renew_notification(job, self.settings.job_lease_seconds):
                    lost.set()
                    return
            except Exception:
                lost.set()
                logger.warning("Reserva da notificação %s não pôde ser renovada", job.job_id)
                return

    def run_once(self) -> bool:
        if not self.settings.smtp_host:
            return False
        job = self.repository.claim_notification(self.settings.job_lease_seconds, self.settings.job_max_attempts)
        if job is None:
            return False
        done, lost = Event(), Event()
        heartbeat = Thread(target=self._heartbeat, args=(job, done, lost), daemon=True)
        heartbeat.start()
        try:
            with tempfile.TemporaryDirectory(prefix="tap-notification-") as directory:
                output = Path(directory) / job.filename
                storage.download_file(job.result_object, output)
                if lost.is_set():
                    return True
                mail.send_transcription_email(
                    job.owner_email,
                    output,
                    message_id=f"<transcription-{job.job_id}@tap.local>",
                    settings=self.settings,
                )
                self.repository.finish_notification(job, sent=True, max_attempts=self.settings.job_max_attempts)
        except Exception:
            # Não registre a exceção SMTP: sua mensagem pode conter destinatários
            # ou conteúdo do servidor. O identificador permite localizar a tentativa.
            logger.warning("Falha na notificação do job %s, tentativa %s", job.job_id, job.notification_attempts)
            retry = min(self.settings.job_retry_seconds * 2 ** (job.notification_attempts - 1), 300)
            self.repository.finish_notification(
                job, sent=False, max_attempts=self.settings.job_max_attempts, retry_seconds=retry
            )
        finally:
            done.set()
            heartbeat.join(timeout=12)
        return True

    def run(self) -> None:
        self.repository.initialize()
        logger.info("Notificador iniciado")
        while not self.stop.is_set():
            try:
                processed = self.run_once()
            except Exception:
                logger.warning("Fila de notificações indisponível; nova tentativa será feita")
                processed = False
            if not processed:
                self.stop.wait(self.settings.worker_poll_seconds)


def main() -> None:
    settings = load_settings()
    if not settings.jobs_database_url or not settings.minio_endpoint:
        raise SystemExit("O notificador exige JOBS_DATABASE_URL e MINIO_ENDPOINT")
    logging.basicConfig(level=logging.INFO)
    dispatcher = NotificationDispatcher(JobRepository(settings.jobs_database_url), settings)
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda signum, frame: dispatcher.stop.set())
    dispatcher.run()


if __name__ == "__main__":
    main()
