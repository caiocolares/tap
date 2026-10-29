import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import transcribe
from transcribe import Segment, Turn


class TestFormatTimestamp:
    @pytest.mark.parametrize(
        "seconds, expected",
        [
            (0, "00:00:00"),
            (5, "00:00:05"),
            (65, "00:01:05"),
            (3661, "01:01:01"),
            (59.9, "00:00:59"),
        ],
    )
    def test_formats_seconds_as_hh_mm_ss(self, seconds, expected):
        assert transcribe.format_timestamp(seconds) == expected


class TestWriteTxt:
    def test_writes_one_line_per_segment_with_speaker_prefix(self, tmp_path):
        segments = [
            Segment(start=0.0, end=4.0, text="Olá, tudo bem?", speaker="pessoa1"),
            Segment(start=5.0, end=8.0, text="Tudo ótimo!", speaker="pessoa2"),
        ]
        output_path = tmp_path / "out.txt"

        transcribe.write_txt(segments, output_path)

        content = output_path.read_text(encoding="utf-8")
        assert content == ("[pessoa1] 00:00:00 - 00:00:04: Olá, tudo bem?\n[pessoa2] 00:00:05 - 00:00:08: Tudo ótimo!")

    def test_omits_prefix_when_speaker_is_none(self, tmp_path):
        segments = [Segment(start=0.0, end=1.0, text="Sem diarização")]
        output_path = tmp_path / "out.txt"

        transcribe.write_txt(segments, output_path)

        assert output_path.read_text(encoding="utf-8") == "00:00:00 - 00:00:01: Sem diarização"


class TestWriteJson:
    def test_writes_segments_as_json_list(self, tmp_path):
        segments = [Segment(start=0.0, end=4.0, text="Olá", speaker="pessoa1")]
        output_path = tmp_path / "out.json"

        transcribe.write_json(segments, output_path)

        import json

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data == [{"start": 0.0, "end": 4.0, "text": "Olá", "speaker": "pessoa1"}]


class TestAssignSpeakers:
    def test_does_nothing_when_no_turns(self):
        segments = [Segment(start=0.0, end=1.0, text="oi")]
        transcribe.assign_speakers(segments, [])
        assert segments[0].speaker is None

    def test_labels_are_generic_and_ordered_by_first_appearance(self):
        segments = [
            Segment(start=0.0, end=1.0, text="a"),
            Segment(start=2.0, end=3.0, text="b"),
        ]
        turns = [
            Turn(start=0.0, end=1.0, speaker="SPEAKER_02"),
            Turn(start=2.0, end=3.0, speaker="SPEAKER_00"),
        ]

        transcribe.assign_speakers(segments, turns)

        assert segments[0].speaker == "pessoa1"
        assert segments[1].speaker == "pessoa2"

    def test_assigns_turn_with_greatest_overlap(self):
        segments = [Segment(start=0.5, end=3.5, text="fala longa")]
        turns = [
            Turn(start=0.0, end=1.0, speaker="SPEAKER_00"),
            Turn(start=1.0, end=4.0, speaker="SPEAKER_01"),
        ]

        transcribe.assign_speakers(segments, turns)

        # overlap com o segundo turno (2.5s) é maior que com o primeiro (0.5s)
        assert segments[0].speaker == "pessoa2"

    def test_falls_back_to_nearest_turn_when_no_overlap(self):
        segments = [Segment(start=18.0, end=19.0, text="fala isolada")]
        turns = [
            Turn(start=0.0, end=1.0, speaker="SPEAKER_00"),
            Turn(start=20.0, end=21.0, speaker="SPEAKER_01"),
        ]

        transcribe.assign_speakers(segments, turns)

        # sem overlap com nenhum turno; o turno em start=20 (distância 1) é
        # mais próximo do segmento que o turno em start=0 (distância 18)
        assert segments[0].speaker == "pessoa2"


class TestToWav:
    def test_converts_successfully(self, monkeypatch):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        input_path = Path("/tmp/entrada.mp3")
        wav_path = transcribe.to_wav(input_path)

        try:
            assert wav_path.suffix == ".wav"
            assert captured["cmd"][0] == "ffmpeg"
            assert str(input_path) in captured["cmd"]
        finally:
            wav_path.unlink(missing_ok=True)

    def test_raises_runtime_error_and_cleans_up_on_ffmpeg_failure(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="erro do ffmpeg")

        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(RuntimeError, match="erro do ffmpeg"):
            transcribe.to_wav(Path("/tmp/entrada.mp3"))

    def test_closes_descriptor_before_invoking_ffmpeg(self, monkeypatch):
        created = {}
        original_mkstemp = transcribe.tempfile.mkstemp

        def tracked_mkstemp(**kwargs):
            fd, name = original_mkstemp(**kwargs)
            created["fd"] = fd
            return fd, name

        def fake_run(cmd, **kwargs):
            with pytest.raises(OSError):
                os.fstat(created["fd"])
            return subprocess.CompletedProcess(cmd, returncode=0)

        monkeypatch.setattr(transcribe.tempfile, "mkstemp", tracked_mkstemp)
        monkeypatch.setattr(subprocess, "run", fake_run)
        output = transcribe.to_wav(Path("audio.mp3"))
        output.unlink()

    @pytest.mark.parametrize("failure", [FileNotFoundError(), subprocess.TimeoutExpired("ffmpeg", 300)])
    def test_cleans_partial_output_when_ffmpeg_cannot_finish(self, failure, tmp_path, monkeypatch):
        original_mkstemp = transcribe.tempfile.mkstemp
        monkeypatch.setattr(transcribe.tempfile, "mkstemp", lambda **kwargs: original_mkstemp(dir=tmp_path, **kwargs))

        def fail(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(b"partial wav")
            raise failure

        monkeypatch.setattr(subprocess, "run", fail)
        with pytest.raises(RuntimeError):
            transcribe.to_wav(Path("audio.mp3"))
        assert list(tmp_path.iterdir()) == []

    def test_applies_configured_ffmpeg_timeout(self, monkeypatch):
        monkeypatch.setenv("FFMPEG_TIMEOUT_SECONDS", "7")

        def fake_run(cmd, **kwargs):
            assert kwargs["timeout"] == 7
            return subprocess.CompletedProcess(cmd, returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        transcribe.to_wav(Path("audio.mp3")).unlink()


class TestTranscribeFn:
    def test_maps_raw_segments_and_strips_text(self):
        class FakeRawSegment:
            def __init__(self, start, end, text):
                self.start = start
                self.end = end
                self.text = text

        class FakeModel:
            def transcribe(self, path, language, vad_filter):
                raw = [FakeRawSegment(0.0, 1.0, "  olá  "), FakeRawSegment(1.0, 2.0, "mundo")]
                return raw, object()

        segments = transcribe.transcribe(FakeModel(), Path("audio.wav"), "pt")

        assert [s.text for s in segments] == ["olá", "mundo"]
        assert all(s.speaker is None for s in segments)


class TestDiarize:
    @pytest.fixture(autouse=True)
    def stub_audio_reader(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "torchaudio", SimpleNamespace(load=lambda path: ("waveform", 16000)))

    def test_returns_turns_sorted_by_start(self):
        class FakeTrack:
            def __init__(self, start, end):
                self.start = start
                self.end = end

        class FakeAnnotation:
            def itertracks(self, yield_label):
                return [
                    (FakeTrack(5.0, 6.0), None, "SPEAKER_01"),
                    (FakeTrack(0.0, 1.0), None, "SPEAKER_00"),
                ]

        class FakePipeline:
            def __call__(self, path):
                return FakeAnnotation()

        turns = transcribe.diarize(FakePipeline(), Path("audio.wav"))

        assert [t.speaker for t in turns] == ["SPEAKER_00", "SPEAKER_01"]

    def test_unwraps_speaker_diarization_attribute(self):
        class FakeTrack:
            start, end = 0.0, 1.0

        class FakeAnnotation:
            def itertracks(self, yield_label):
                return [(FakeTrack(), None, "SPEAKER_00")]

        class FakeDiarizationResult:
            speaker_diarization = FakeAnnotation()

        class FakePipeline:
            def __call__(self, path):
                return FakeDiarizationResult()

        turns = transcribe.diarize(FakePipeline(), Path("audio.wav"))

        assert len(turns) == 1
        assert turns[0].speaker == "SPEAKER_00"


class TestLoadWhisperModel:
    def test_uses_float16_on_cuda_and_int8_on_cpu(self, monkeypatch):
        captured = {}

        class FakeWhisperModel:
            def __init__(self, model_size, device, compute_type):
                captured["args"] = (model_size, device, compute_type)

        fake_module = type("module", (), {"WhisperModel": FakeWhisperModel})
        monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

        transcribe.load_whisper_model("medium", "cuda")
        assert captured["args"] == ("medium", "cuda", "float16")

        transcribe.load_whisper_model("small", "cpu")
        assert captured["args"] == ("small", "cpu", "int8")


class TestLoadDiarizationPipeline:
    @pytest.fixture(autouse=True)
    def stub_torch(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(device=lambda name: name))

    def test_loads_pipeline_and_moves_to_cuda_when_requested(self, monkeypatch):
        calls = {"to_device": None}

        class FakePipeline:
            @classmethod
            def from_pretrained(cls, name, token):
                calls["from_pretrained"] = (name, token)
                return cls()

            def to(self, device):
                calls["to_device"] = device
                return self

        fake_module = type("module", (), {"Pipeline": FakePipeline})
        monkeypatch.setitem(sys.modules, "pyannote.audio", fake_module)

        pipeline = transcribe.load_diarization_pipeline("hf_token", "cuda")

        assert calls["from_pretrained"] == ("pyannote/speaker-diarization-3.1", "hf_token")
        assert calls["to_device"] is not None
        assert pipeline is not None

    def test_does_not_move_to_device_on_cpu(self, monkeypatch):
        calls = {}

        class FakePipeline:
            @classmethod
            def from_pretrained(cls, name, token):
                return cls()

            def to(self, device):
                calls["to"] = device
                return self

        fake_module = type("module", (), {"Pipeline": FakePipeline})
        monkeypatch.setitem(sys.modules, "pyannote.audio", fake_module)

        transcribe.load_diarization_pipeline("hf_token", "cpu")

        assert "to" not in calls


class TestMain:
    def _stub_transcricao(self, monkeypatch, tmp_path):
        wav_path = tmp_path / "convertido.wav"
        wav_path.write_bytes(b"wav")

        # Evita que o .env real do repositório (com HF_TOKEN de verdade)
        # vaze para o teste — main() chama load_dotenv() internamente.
        monkeypatch.setattr(transcribe, "load_dotenv", lambda: None)
        monkeypatch.setattr(transcribe, "to_wav", lambda input_path: wav_path)
        monkeypatch.setattr(transcribe, "load_whisper_model", lambda model_size, device: "fake-model")
        monkeypatch.setattr(
            transcribe,
            "transcribe",
            lambda model, wav_path, language: [Segment(start=0.0, end=1.0, text="olá")],
        )
        return wav_path

    def test_sai_com_erro_quando_audio_nao_existe(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["transcribe.py", str(tmp_path / "nao-existe.mp3")])

        with pytest.raises(SystemExit, match="Arquivo não encontrado"):
            transcribe.main()

    def test_no_diarization_gera_txt_e_json_sem_chamar_diarizacao(self, tmp_path, monkeypatch):
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_bytes(b"audio")
        self._stub_transcricao(monkeypatch, tmp_path)

        chamadas = {"diarize": 0}

        def fake_diarize(pipeline, wav_path):
            chamadas["diarize"] += 1
            return []

        monkeypatch.setattr(transcribe, "diarize", fake_diarize)
        monkeypatch.setattr(sys, "argv", ["transcribe.py", str(audio_path), "--no-diarization"])

        transcribe.main()

        assert chamadas["diarize"] == 0
        assert (tmp_path / "audio.txt").exists()
        assert (tmp_path / "audio.json").exists()
        assert "olá" in (tmp_path / "audio.txt").read_text(encoding="utf-8")

    def test_sai_com_erro_quando_falta_hf_token(self, tmp_path, monkeypatch):
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_bytes(b"audio")
        self._stub_transcricao(monkeypatch, tmp_path)

        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.setattr(sys, "argv", ["transcribe.py", str(audio_path)])

        with pytest.raises(SystemExit, match="HF_TOKEN não definido"):
            transcribe.main()

    def test_com_hf_token_roda_diarizacao_e_atribui_speakers(self, tmp_path, monkeypatch):
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_bytes(b"audio")
        self._stub_transcricao(monkeypatch, tmp_path)

        monkeypatch.setenv("HF_TOKEN", "hf_fake")
        monkeypatch.setattr(transcribe, "load_diarization_pipeline", lambda hf_token, device: "fake-pipeline")
        monkeypatch.setattr(
            transcribe,
            "diarize",
            lambda pipeline, wav_path: [Turn(start=0.0, end=1.0, speaker="SPEAKER_00")],
        )
        monkeypatch.setattr(sys, "argv", ["transcribe.py", str(audio_path)])

        transcribe.main()

        content = (tmp_path / "audio.txt").read_text(encoding="utf-8")
        assert "[pessoa1]" in content

    def test_respeita_output_customizado(self, tmp_path, monkeypatch):
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_bytes(b"audio")
        self._stub_transcricao(monkeypatch, tmp_path)

        output_base = tmp_path / "resultado"
        monkeypatch.setattr(
            sys,
            "argv",
            ["transcribe.py", str(audio_path), "--no-diarization", "--output", str(output_base)],
        )

        transcribe.main()

        assert (tmp_path / "resultado.txt").exists()
        assert (tmp_path / "resultado.json").exists()
