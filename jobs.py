"""Fila e estado duráveis na mesma transação PostgreSQL."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row


class QueueFullError(Exception):
    """O limite global de jobs pendentes foi atingido."""


@dataclass(frozen=True)
class Job:
    job_id: UUID
    status: Literal["queued", "processing", "completed", "error"]
    format: Literal["txt", "json"]
    input_object: str
    model: str
    language: str | None
    diarization: bool
    attempts: int
    max_attempts: int
    available_at: datetime
    lease_token: UUID | None
    lease_until: datetime | None
    result_object: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    expired: bool = False

    @property
    def filename(self) -> str:
        return f"transcricao.{self.format}"

    @property
    def media_type(self) -> str:
        return "application/json" if self.format == "json" else "text/plain; charset=utf-8"


class JobRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=5,
            options="-c statement_timeout=10000",
        )

    def initialize(self) -> None:
        """Migrações serializadas também permitem inicialização por várias réplicas."""
        with self._connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(17080001)")
            conn.execute("CREATE TABLE IF NOT EXISTS tap_schema_migrations (version TEXT PRIMARY KEY)")
            for path in sorted(Path(__file__).with_name("migrations").glob("*.sql")):
                if not conn.execute("SELECT 1 FROM tap_schema_migrations WHERE version = %s", (path.name,)).fetchone():
                    conn.execute(path.read_text())
                    conn.execute("INSERT INTO tap_schema_migrations (version) VALUES (%s)", (path.name,))

    def ping(self) -> None:
        with self._connect() as conn:
            conn.execute("SELECT 1 FROM tap_jobs LIMIT 1")

    def enqueue(
        self,
        job_id: UUID,
        format: str,
        input_object: str,
        model: str,
        language: str | None,
        diarization: bool,
        max_attempts: int,
        max_pending: int,
    ) -> None:
        with self._connect() as conn:
            # Serializa somente a admissão; o limite é global, não por réplica.
            conn.execute("SELECT pg_advisory_xact_lock(17080002)")
            pending = conn.execute(
                "SELECT count(*) AS total FROM tap_jobs WHERE status IN ('queued', 'processing')"
            ).fetchone()["total"]
            if pending >= max_pending:
                raise QueueFullError
            conn.execute(
                """INSERT INTO tap_jobs
                   (job_id, format, input_object, model, language, diarization, max_attempts)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (job_id, format, input_object, model, language, diarization, max_attempts),
            )

    def get(self, job_id: str) -> Job | None:
        try:
            identifier = UUID(job_id)
        except ValueError:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """SELECT *, COALESCE(expires_at <= clock_timestamp(), false) AS expired
                   FROM tap_jobs WHERE job_id = %s""",
                (identifier,),
            ).fetchone()
        return Job(**row) if row else None

    def claim(self, lease_seconds: int, ttl_seconds: int) -> Job | None:
        with self._connect() as conn:
            # Inclui a queda abrupta durante a última tentativa: não deixa jobs presos.
            conn.execute(
                """UPDATE tap_jobs SET status = 'error', error = 'Limite de tentativas atingido',
                       lease_token = NULL, lease_until = NULL, updated_at = clock_timestamp(),
                       expires_at = clock_timestamp() + %s * interval '1 second'
                   WHERE status = 'processing' AND lease_until <= clock_timestamp()
                       AND attempts >= max_attempts""",
                (ttl_seconds,),
            )
            row = conn.execute(
                """WITH candidate AS (
                       SELECT job_id FROM tap_jobs
                       WHERE attempts < max_attempts AND (
                           (status = 'queued' AND available_at <= clock_timestamp()) OR
                           (status = 'processing' AND lease_until <= clock_timestamp())
                       )
                       ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
                   )
                   UPDATE tap_jobs AS job SET status = 'processing', attempts = attempts + 1,
                       lease_token = %s, lease_until = clock_timestamp() + %s * interval '1 second',
                       updated_at = clock_timestamp()
                   FROM candidate WHERE job.job_id = candidate.job_id RETURNING job.*""",
                (uuid4(), lease_seconds),
            ).fetchone()
        return Job(**row) if row else None

    def heartbeat(self, job: Job, lease_seconds: int) -> bool:
        with self._connect() as conn:
            return (
                conn.execute(
                    """UPDATE tap_jobs SET lease_until = clock_timestamp() + %s * interval '1 second',
                       updated_at = clock_timestamp()
                   WHERE job_id = %s AND lease_token = %s AND status = 'processing'
                       AND lease_until > clock_timestamp()""",
                    (lease_seconds, job.job_id, job.lease_token),
                ).rowcount
                == 1
            )

    def complete(self, job: Job, result_object: str, ttl_seconds: int) -> bool:
        with self._connect() as conn:
            return (
                conn.execute(
                    """UPDATE tap_jobs SET status = 'completed', result_object = %s, error = NULL,
                       lease_token = NULL, lease_until = NULL, updated_at = clock_timestamp(),
                       expires_at = clock_timestamp() + %s * interval '1 second'
                   WHERE job_id = %s AND lease_token = %s AND status = 'processing'
                       AND lease_until > clock_timestamp()""",
                    (result_object, ttl_seconds, job.job_id, job.lease_token),
                ).rowcount
                == 1
            )

    def fail(self, job: Job, retry_seconds: int, ttl_seconds: int) -> bool:
        with self._connect() as conn:
            return (
                conn.execute(
                    """UPDATE tap_jobs SET
                       status = CASE WHEN attempts >= max_attempts THEN 'error' ELSE 'queued' END,
                       error = 'Falha no processamento do áudio',
                       available_at = clock_timestamp() + %s * interval '1 second',
                       expires_at = CASE WHEN attempts >= max_attempts
                           THEN clock_timestamp() + %s * interval '1 second' ELSE NULL END,
                       lease_token = NULL, lease_until = NULL, updated_at = clock_timestamp()
                   WHERE job_id = %s AND lease_token = %s AND status = 'processing'
                       AND lease_until > clock_timestamp()""",
                    (retry_seconds, ttl_seconds, job.job_id, job.lease_token),
                ).rowcount
                == 1
            )

    def prune(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM tap_jobs WHERE expires_at <= clock_timestamp()")
