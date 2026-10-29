"""Cliente de Object Storage (MinIO/S3) para os resultados dos jobs assíncronos.

Áudios de entrada e resultados dos workers ficam no bucket compartilhado.
Os metadados e a fila ficam no PostgreSQL (jobs.py).
"""

from pathlib import Path
from threading import Lock

from minio import Minio
from minio.error import S3Error

from settings import load_settings

_settings = load_settings()
MINIO_ENDPOINT = _settings.minio_endpoint
MINIO_ACCESS_KEY = _settings.minio_access_key
MINIO_SECRET_KEY = _settings.minio_secret_key
MINIO_BUCKET = _settings.minio_bucket
MINIO_SECURE = _settings.minio_secure

STORAGE_ENABLED = bool(MINIO_ENDPOINT)

_client: Minio | None = None
_client_lock = Lock()


def _get_client() -> Minio:
    global _client
    with _client_lock:
        if _client is None:
            client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=MINIO_SECURE,
            )
            if not client.bucket_exists(MINIO_BUCKET):
                try:
                    client.make_bucket(MINIO_BUCKET)
                except S3Error as exc:
                    if exc.code != "BucketAlreadyOwnedByYou":
                        raise
            _client = client
    return _client


def upload_file(object_name: str, file_path: Path) -> None:
    _get_client().fput_object(MINIO_BUCKET, object_name, str(file_path))


def download_file(object_name: str, dest_path: Path) -> None:
    _get_client().fget_object(MINIO_BUCKET, object_name, str(dest_path))

<<<<<<< HEAD

def delete_file(object_name: str) -> None:
    _get_client().remove_object(MINIO_BUCKET, object_name)


def check_connection() -> None:
    if not _get_client().bucket_exists(MINIO_BUCKET):
        raise RuntimeError("Bucket indisponível")
=======
def file_exists(object_name: str) -> bool:
    from minio.error import S3Error
    try:
        _get_client().stat_object(MINIO_BUCKET, object_name)
        return True
    except S3Error as e:
        if e.code == "NoSuchKey":
            return False
        raise e
>>>>>>> origin/develop
