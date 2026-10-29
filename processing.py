"""Inferência compartilhada pela rota síncrona e pelos workers."""

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from transcribe import (
    assign_speakers,
    diarize,
    load_diarization_pipeline,
    load_whisper_model,
    to_wav,
    transcribe,
    write_json,
    write_txt,
)


@dataclass(frozen=True)
class TranscriptionOptions:
    model: str
    language: str | None
    diarization: bool


class AudioProcessor:
    def __init__(self, device: str, hf_token: str | None):
        self.device = device
        self.hf_token = hf_token
        self._models: dict = {}
        self._pipeline = None
        self._lock = Lock()

    def process(
        self, input_path: Path, format: str, output_dir: Path, options: TranscriptionOptions
    ) -> tuple[Path, str]:
        wav_path = to_wav(input_path)
        try:
            with self._lock:
                if options.diarization and not self.hf_token:
                    raise RuntimeError("Worker sem HF_TOKEN para executar a diarização solicitada")
                if options.model not in self._models:
                    self._models[options.model] = load_whisper_model(options.model, self.device)
                segments = transcribe(self._models[options.model], wav_path, options.language)
                if options.diarization:
                    if self._pipeline is None:
                        self._pipeline = load_diarization_pipeline(self.hf_token, self.device)
                    assign_speakers(segments, diarize(self._pipeline, wav_path))
        finally:
            wav_path.unlink(missing_ok=True)

        output_path = output_dir / f"transcricao.{format}"
        if format == "txt":
            write_txt(segments, output_path)
            return output_path, "text/plain; charset=utf-8"
        write_json(segments, output_path)
        return output_path, "application/json"
