<<<<<<< HEAD
"""Worker durável: python -m worker. Cada processo executa uma inferência por vez."""

import logging
import signal
import tempfile
from pathlib import Path
from threading import Event, Thread

import storage
from jobs import Job, JobRepository
from processing import AudioProcessor, TranscriptionOptions
from settings import Settings, load_settings

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, repository: JobRepository, processor: AudioProcessor, settings: Settings):
        self.repository = repository
        self.processor = processor
        self.settings = settings
        self.stop = Event()

    def _heartbeat(self, job: Job, done: Event, lost: Event) -> None:
        while not done.wait(self.settings.job_heartbeat_seconds):
            try:
                if not self.repository.heartbeat(job, self.settings.job_lease_seconds):
                    lost.set()
                    return
            except Exception:
                logger.exception("Não foi possível renovar a reserva do job %s", job.job_id)
                lost.set()
                return

    def run_once(self) -> bool:
        job = self.repository.claim(self.settings.job_lease_seconds, self.settings.job_ttl_seconds)
        if job is None:
            return False
        logger.info("Processando job %s, tentativa %s/%s", job.job_id, job.attempts, job.max_attempts)
        done, lost = Event(), Event()
        heartbeat = Thread(target=self._heartbeat, args=(job, done, lost), daemon=True)
        heartbeat.start()
        result_object = None
        try:
            with tempfile.TemporaryDirectory(prefix="tap-worker-") as directory:
                tmp_dir = Path(directory)
                input_path = tmp_dir / "audio.mp3"
                storage.download_file(job.input_object, input_path)
                output, _ = self.processor.process(
                    input_path,
                    job.format,
                    tmp_dir,
                    TranscriptionOptions(job.model, job.language, job.diarization),
                )
                if lost.is_set():
                    logger.warning("Reserva perdida; resultado do job %s foi descartado", job.job_id)
                    return True
                # Cada tentativa publica em chave própria. Um worker antigo nunca
                # sobrescreve o resultado de uma tentativa mais recente.
                result_object = f"{job.job_id}/results/{job.lease_token}/{job.filename}"
                storage.upload_file(result_object, output)
                if not self.repository.complete(job, result_object, self.settings.job_ttl_seconds):
                    self._discard_result(result_object)
                else:
                    logger.info("Job %s concluído", job.job_id)
        except Exception:
            logger.exception("Falha na tentativa %s do job %s", job.attempts, job.job_id)
            # Se o commit de complete teve resposta ambígua, preserve o objeto:
            # ele pode já estar referenciado por um job concluído no banco.
            retry = min(self.settings.job_retry_seconds * 2 ** (job.attempts - 1), 300)
            self.repository.fail(job, retry, self.settings.job_ttl_seconds)
        finally:
            done.set()
            heartbeat.join(timeout=12)
        return True

    @staticmethod
    def _discard_result(object_name: str) -> None:
        try:
            storage.delete_file(object_name)
        except Exception:
            logger.exception("Não foi possível remover resultado abandonado %s", object_name)

    def run(self) -> None:
        self.repository.initialize()
        logger.info("Worker iniciado; aguardando jobs")
        while not self.stop.is_set():
            try:
                processed = self.run_once()
            except Exception:
                logger.exception("Fila indisponível; o worker tentará novamente")
                processed = False
            if not processed:
                self.stop.wait(self.settings.worker_poll_seconds)


def main() -> None:
    settings = load_settings()
    if not settings.jobs_database_url or not settings.minio_endpoint:
        raise SystemExit("O worker exige JOBS_DATABASE_URL e MINIO_ENDPOINT")
    logging.basicConfig(level=logging.INFO)
    worker = Worker(
        JobRepository(settings.jobs_database_url),
        AudioProcessor(settings.device, settings.hf_token),
        settings,
    )
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda signum, frame: worker.stop.set())
    worker.run()


if __name__ == "__main__":
    main()
=======
import os
import pika
import json
import urllib.request
import urllib.error
import time

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
APP_URL = os.environ.get("APP_URL", "http://app:8000/internal/worker")

def callback(ch, method, properties, body):
    payload = body.decode('utf-8')
    print(f"[*] Recebido: {payload}")
    
    # Faz uma requisição POST para a API interna simulando o Knative Eventing
    req = urllib.request.Request(APP_URL, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print(f"[+] Processado com sucesso: {payload}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                print(f"[-] Erro da API: Status {response.status}")
                # Na prática, requisições que não dão 200 deveriam ir para DLQ
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except urllib.error.URLError as e:
        print(f"[-] Falha ao contactar a API: {e}")
        # A API pode estar fora, então colocamos de volta na fila
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    # Aguarda o RabbitMQ estar pronto
    connection = None
    for i in range(10):
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            break
        except pika.exceptions.AMQPConnectionError:
            print("RabbitMQ não disponível. Tentando novamente em 3 segundos...")
            time.sleep(3)
            
    if not connection:
        print("Erro: Não foi possível conectar ao RabbitMQ.")
        return

    channel = connection.channel()
    channel.queue_declare(queue='transcription_jobs', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='transcription_jobs', on_message_callback=callback)

    print('[*] Worker iniciado. Aguardando mensagens. Para sair pressione CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrompido')
>>>>>>> origin/develop
