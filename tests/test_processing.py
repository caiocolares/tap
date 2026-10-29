from unittest.mock import Mock

import pytest

import processing
from processing import AudioProcessor, TranscriptionOptions
from transcribe import Segment


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    wav = tmp_path / "converted.wav"

    def convert(path):
        wav.write_bytes(b"wav")
        return wav

    monkeypatch.setattr(processing, "to_wav", convert)
    model = Mock(return_value="model")
    diarization = Mock(return_value="pipeline")
    monkeypatch.setattr(processing, "load_whisper_model", model)
    monkeypatch.setattr(processing, "load_diarization_pipeline", diarization)
    monkeypatch.setattr(processing, "transcribe", lambda *args: [Segment(0, 1, "olá")])
    monkeypatch.setattr(processing, "diarize", lambda *args: [])
    return model, diarization, wav


@pytest.mark.parametrize("format", ["txt", "json"])
def test_processing_writes_result_and_cleans_wav(pipeline, tmp_path, format):
    processor = AudioProcessor("cpu", None)
    output, media = processor.process(
        tmp_path / "input.mp3", format, tmp_path, TranscriptionOptions("tiny", "pt", False)
    )
    assert "olá" in output.read_text()
    assert ("json" in media) == (format == "json")
    assert not pipeline[2].exists()


def test_models_are_cached_by_model_name_and_pipeline_is_reused(pipeline, tmp_path):
    processor = AudioProcessor("cpu", "test-token")
    for name in ["tiny", "tiny", "small"]:
        processor.process(tmp_path / "input.mp3", "txt", tmp_path, TranscriptionOptions(name, "pt", True))
    assert pipeline[0].call_count == 2
    assert pipeline[1].call_count == 1


def test_missing_worker_token_is_not_silently_ignored(pipeline, tmp_path):
    processor = AudioProcessor("cpu", None)
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        processor.process(tmp_path / "input.mp3", "txt", tmp_path, TranscriptionOptions("tiny", None, True))
    assert not pipeline[2].exists()
    pipeline[0].assert_not_called()
