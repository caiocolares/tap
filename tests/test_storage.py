import importlib
from pathlib import Path

import pytest

import storage


@pytest.fixture
def reload_storage(monkeypatch):
    """Recarrega storage.py com as env vars atuais e desfaz ao final do teste."""

    def _reload():
        importlib.reload(storage)
        return storage

    yield _reload
    monkeypatch.undo()
    importlib.reload(storage)


class TestStorageEnabled:
    def test_disabled_when_minio_endpoint_not_set(self, monkeypatch, reload_storage):
        monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
        mod = reload_storage()
        assert mod.STORAGE_ENABLED is False

    def test_enabled_when_minio_endpoint_set(self, monkeypatch, reload_storage):
        monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
        mod = reload_storage()
        assert mod.STORAGE_ENABLED is True

    def test_default_bucket_name(self, monkeypatch, reload_storage):
        monkeypatch.delenv("MINIO_BUCKET", raising=False)
        mod = reload_storage()
        assert mod.MINIO_BUCKET == "audio-to-text"

    def test_custom_bucket_name(self, monkeypatch, reload_storage):
        monkeypatch.setenv("MINIO_BUCKET", "meu-bucket")
        mod = reload_storage()
        assert mod.MINIO_BUCKET == "meu-bucket"


class TestGetClient:
    def test_creates_bucket_when_missing(self, monkeypatch, reload_storage):
        monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
        monkeypatch.setenv("MINIO_BUCKET", "audio-to-text")
        mod = reload_storage()

        created = {}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                created["init_args"] = (args, kwargs)

            def bucket_exists(self, bucket):
                return False

            def make_bucket(self, bucket):
                created["bucket"] = bucket

        monkeypatch.setattr(mod, "Minio", FakeClient)

        client = mod._get_client()

        assert isinstance(client, FakeClient)
        assert created["bucket"] == "audio-to-text"

    def test_does_not_recreate_existing_bucket(self, monkeypatch, reload_storage):
        monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
        mod = reload_storage()

        calls = {"make_bucket": 0}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def bucket_exists(self, bucket):
                return True

            def make_bucket(self, bucket):
                calls["make_bucket"] += 1

        monkeypatch.setattr(mod, "Minio", FakeClient)

        mod._get_client()

        assert calls["make_bucket"] == 0

    def test_client_is_cached_across_calls(self, monkeypatch, reload_storage):
        monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
        mod = reload_storage()

        instances = {"count": 0}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                instances["count"] += 1

            def bucket_exists(self, bucket):
                return True

            def make_bucket(self, bucket):
                pass

        monkeypatch.setattr(mod, "Minio", FakeClient)

        first = mod._get_client()
        second = mod._get_client()

        assert first is second
        assert instances["count"] == 1


class TestUploadDownload:
    def test_upload_file_delegates_to_client(self, monkeypatch, reload_storage, tmp_path):
        monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
        monkeypatch.setenv("MINIO_BUCKET", "meu-bucket")
        mod = reload_storage()

        calls = {}

        class FakeClient:
            def fput_object(self, bucket, object_name, file_path):
                calls["args"] = (bucket, object_name, file_path)

        monkeypatch.setattr(mod, "_get_client", lambda: FakeClient())

        file_path = tmp_path / "audio.mp3"
        file_path.write_bytes(b"conteudo")

        mod.upload_file("job-1/audio.mp3", file_path)

        assert calls["args"] == ("meu-bucket", "job-1/audio.mp3", str(file_path))

    def test_download_file_delegates_to_client(self, monkeypatch, reload_storage, tmp_path):
        monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
        monkeypatch.setenv("MINIO_BUCKET", "meu-bucket")
        mod = reload_storage()

        calls = {}

        class FakeClient:
            def fget_object(self, bucket, object_name, file_path):
                calls["args"] = (bucket, object_name, file_path)

        monkeypatch.setattr(mod, "_get_client", lambda: FakeClient())

        dest_path = tmp_path / "resultado.txt"

        mod.download_file("job-1/resultado.txt", dest_path)

        assert calls["args"] == ("meu-bucket", "job-1/resultado.txt", str(dest_path))
