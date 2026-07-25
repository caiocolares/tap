import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server
from transcribe import Segment


@pytest.fixture(autouse=True)
def _reset_server_state():
    server._jobs.clear()
    server._cache.clear()
    yield
    server._jobs.clear()
    server._cache.clear()


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Substitui as etapas de IA por stubs determinísticos e rápidos."""
    monkeypatch.setattr(server, "_whisper_model", lambda: "fake-whisper-model")
    monkeypatch.setattr(server, "_diarization_pipeline", lambda: "fake-diarization-pipeline")
    monkeypatch.setattr(server, "to_wav", lambda input_path: input_path)
    monkeypatch.setattr(
        server,
        "run_transcription",
        lambda model, wav_path, language: [Segment(start=0.0, end=1.0, text="Olá mundo")],
    )
    monkeypatch.setattr(server, "diarize", lambda pipeline, wav_path: [])
    monkeypatch.setattr(server, "assign_speakers", lambda segments, turns: None)


@pytest.fixture
def fake_bucket(monkeypatch):
    """Substitui o storage real por um dicionário em memória."""
    bucket: dict[str, bytes] = {}

    def fake_upload(object_name, file_path):
        bucket[object_name] = Path(file_path).read_bytes()

    def fake_download(object_name, dest_path):
        Path(dest_path).write_bytes(bucket[object_name])

    monkeypatch.setattr(server.storage, "STORAGE_ENABLED", True)
    monkeypatch.setattr(server.storage, "upload_file", fake_upload)
    monkeypatch.setattr(server.storage, "download_file", fake_download)
    return bucket


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestTranscricaoSincrona:
    def test_formato_invalido_retorna_422(self, client):
        resp = client.post("/transcricao/xml", content=b"algum-audio")
        assert resp.status_code == 422

    def test_corpo_vazio_retorna_400(self, client, stub_pipeline):
        resp = client.post("/transcricao/txt", content=b"")
        assert resp.status_code == 400

    def test_txt_retorna_arquivo_com_transcricao(self, client, stub_pipeline):
        resp = client.post("/transcricao/txt", content=b"fake-audio-bytes")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        assert "Olá mundo" in resp.text

    def test_json_retorna_segmentos_estruturados(self, client, stub_pipeline):
        resp = client.post("/transcricao/json", content=b"fake-audio-bytes")

        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["text"] == "Olá mundo"

    def test_falha_no_ffmpeg_retorna_422(self, client, stub_pipeline, monkeypatch):
        def boom(input_path):
            raise RuntimeError("ffmpeg explodiu")

        monkeypatch.setattr(server, "to_wav", boom)

        resp = client.post("/transcricao/txt", content=b"fake-audio-bytes")

        assert resp.status_code == 422

    def test_diarizacao_so_roda_quando_hf_token_definido(self, client, stub_pipeline, monkeypatch):
        chamadas = {"diarize": 0}

        def fake_diarize(pipeline, wav_path):
            chamadas["diarize"] += 1
            return []

        monkeypatch.setattr(server, "diarize", fake_diarize)

        monkeypatch.setattr(server, "HF_TOKEN", None)
        client.post("/transcricao/txt", content=b"fake-audio-bytes")
        assert chamadas["diarize"] == 0

        monkeypatch.setattr(server, "HF_TOKEN", "hf_fake_token")
        client.post("/transcricao/txt", content=b"fake-audio-bytes")
        assert chamadas["diarize"] == 1

    def test_upload_do_audio_original_quando_storage_habilitado(self, client, stub_pipeline, fake_bucket):
        resp = client.post("/transcricao/txt", content=b"fake-audio-bytes")

        assert resp.status_code == 200
        assert any(key.endswith("/audio.mp3") for key in fake_bucket)

    def test_nao_faz_upload_quando_storage_desabilitado(self, client, stub_pipeline, monkeypatch):
        chamadas = {"upload": 0}

        def fake_upload(*args, **kwargs):
            chamadas["upload"] += 1

        monkeypatch.setattr(server.storage, "STORAGE_ENABLED", False)
        monkeypatch.setattr(server.storage, "upload_file", fake_upload)

        client.post("/transcricao/txt", content=b"fake-audio-bytes")

        assert chamadas["upload"] == 0


class TestTranscricaoAssincrona:
    def test_dispatch_retorna_job_id_e_status_processing(self, client, stub_pipeline):
        resp = client.post("/async/transcricao/txt", content=b"fake-audio-bytes")

        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "processing"

    def test_dispatch_corpo_vazio_retorna_400(self, client, stub_pipeline):
        resp = client.post("/async/transcricao/txt", content=b"")
        assert resp.status_code == 400

    def test_status_job_inexistente_retorna_404(self, client):
        resp = client.get("/async/status/nao-existe")
        assert resp.status_code == 404

    def test_status_job_processando(self, client):
        server._jobs["job-processando"] = {"status": "processing"}

        resp = client.get("/async/status/job-processando")

        assert resp.status_code == 200
        assert resp.json() == {"job_id": "job-processando", "status": "processing"}

    def test_status_job_com_erro(self, client):
        server._jobs["job-erro"] = {"status": "error", "error": "falha simulada"}

        resp = client.get("/async/status/job-erro")

        assert resp.status_code == 500
        assert "falha simulada" in resp.text

    def test_status_job_concluido_local(self, client, tmp_path):
        output_path = tmp_path / "transcricao.txt"
        output_path.write_text("conteudo local", encoding="utf-8")
        server._jobs["job-local"] = {
            "status": "completed",
            "output_path": output_path,
            "media_type": "text/plain; charset=utf-8",
            "tmp_dir": tmp_path,
        }

        resp = client.get("/async/status/job-local")

        assert resp.status_code == 200
        assert resp.text == "conteudo local"

    def test_status_job_concluido_via_storage(self, client, fake_bucket):
        fake_bucket["job-storage/transcricao.txt"] = b"conteudo do bucket"
        server._jobs["job-storage"] = {
            "status": "completed",
            "object_name": "job-storage/transcricao.txt",
            "filename": "transcricao.txt",
            "media_type": "text/plain; charset=utf-8",
        }

        resp = client.get("/async/status/job-storage")

        assert resp.status_code == 200
        assert resp.text == "conteudo do bucket"


class TestBackgroundProcess:
    def test_persiste_audio_de_entrada_antes_de_processar(self, tmp_path, stub_pipeline, fake_bucket, monkeypatch):
        job_id = "job-persist"
        tmp_dir = tmp_path
        input_path = tmp_dir / "audio.mp3"
        input_path.write_bytes(b"audio original")

        ordem = []
        original_upload = server.storage.upload_file

        def upload_rastreado(object_name, file_path):
            ordem.append(object_name)
            original_upload(object_name, file_path)

        monkeypatch.setattr(server.storage, "upload_file", upload_rastreado)

        asyncio.run(server._background_process(job_id, input_path, "txt", tmp_dir))

        assert ordem[0] == f"{job_id}/audio.mp3"
        assert fake_bucket[f"{job_id}/audio.mp3"] == b"audio original"

        job = server._jobs[job_id]
        assert job["status"] == "completed"
        assert job["object_name"] == f"{job_id}/transcricao.txt"

    def test_processamento_local_quando_storage_desabilitado(self, tmp_path, stub_pipeline, monkeypatch):
        monkeypatch.setattr(server.storage, "STORAGE_ENABLED", False)

        job_id = "job-local-bg"
        input_path = tmp_path / "audio.mp3"
        input_path.write_bytes(b"audio original")

        asyncio.run(server._background_process(job_id, input_path, "txt", tmp_path))

        job = server._jobs[job_id]
        assert job["status"] == "completed"
        assert job["output_path"].exists()
        assert job["tmp_dir"] == tmp_path

    def test_marca_job_como_erro_quando_processamento_falha(self, tmp_path, stub_pipeline, monkeypatch):
        def boom(model, wav_path, language):
            raise RuntimeError("falha na transcrição")

        monkeypatch.setattr(server, "run_transcription", boom)

        job_id = "job-erro-bg"
        input_path = tmp_path / "audio.mp3"
        input_path.write_bytes(b"audio original")

        asyncio.run(server._background_process(job_id, input_path, "txt", tmp_path))

        job = server._jobs[job_id]
        assert job["status"] == "error"
        assert "falha na transcrição" in job["error"]
        assert not tmp_path.exists()


class TestProcessar:
    def test_gera_txt_com_media_type_correto(self, tmp_path, stub_pipeline):
        input_path = tmp_path / "audio.mp3"
        input_path.write_bytes(b"audio")

        output_path, media_type = server._processar(input_path, "txt", tmp_path)

        assert output_path.name == "transcricao.txt"
        assert media_type == "text/plain; charset=utf-8"
        assert "Olá mundo" in output_path.read_text(encoding="utf-8")

    def test_gera_json_com_media_type_correto(self, tmp_path, stub_pipeline):
        input_path = tmp_path / "audio.mp3"
        input_path.write_bytes(b"audio")

        output_path, media_type = server._processar(input_path, "json", tmp_path)

        assert output_path.name == "transcricao.json"
        assert media_type == "application/json"


class TestCacheDeModelos:
    def test_whisper_model_e_carregado_uma_unica_vez(self, monkeypatch):
        chamadas = {"count": 0}

        def fake_load(model_size, device):
            chamadas["count"] += 1
            return "modelo-fake"

        monkeypatch.setattr(server, "load_whisper_model", fake_load)

        primeira = server._whisper_model()
        segunda = server._whisper_model()

        assert primeira == segunda == "modelo-fake"
        assert chamadas["count"] == 1

    def test_diarization_pipeline_e_carregado_uma_unica_vez(self, monkeypatch):
        chamadas = {"count": 0}

        def fake_load(hf_token, device):
            chamadas["count"] += 1
            return "pipeline-fake"

        monkeypatch.setattr(server, "load_diarization_pipeline", fake_load)

        primeira = server._diarization_pipeline()
        segunda = server._diarization_pipeline()

        assert primeira == segunda == "pipeline-fake"
        assert chamadas["count"] == 1
