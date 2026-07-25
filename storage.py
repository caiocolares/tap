"""Cliente de Object Storage (MinIO/S3) para os resultados dos jobs assíncronos.

Sem isso, o resultado de um job fica preso ao disco/memória do Pod que o
processou (ver TODO.md, Nível 3). Com o MINIO_ENDPOINT configurado, o
resultado passa a ser gravado no bucket e pode ser lido por qualquer Pod que
atenda o polling.
"""
import os
from pathlib import Path

from minio import Minio

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "audio-to-text")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"

STORAGE_ENABLED = bool(MINIO_ENDPOINT)

_client: Minio | None = None


def _get_client() -> Minio:
    global _client
    if _client is None:
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        if not client.bucket_exists(MINIO_BUCKET):
            client.make_bucket(MINIO_BUCKET)
        _client = client
    return _client


def upload_file(object_name: str, file_path: Path) -> None:
    _get_client().fput_object(MINIO_BUCKET, object_name, str(file_path))


def download_file(object_name: str, dest_path: Path) -> None:
    _get_client().fget_object(MINIO_BUCKET, object_name, str(dest_path))
