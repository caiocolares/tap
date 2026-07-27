#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass
class Turn:
    start: float
    end: float
    speaker: str


def to_wav(input_path: Path) -> Path:
    """Converte o áudio de entrada (mp3 ou outro formato) para WAV mono 16kHz."""
    tmp = Path(tempfile.mkstemp(suffix=".wav")[1])
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-ac", "1", "-ar", "16000", str(tmp)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"Falha ao converter áudio com ffmpeg (está instalado? `brew install ffmpeg`):\n{result.stderr}"
        )
    return tmp


def load_whisper_model(model_size: str, device: str):
    """Carrega o modelo Whisper. Custoso — chame uma vez e reutilize entre transcrições.

    CTranslate2 (usado pelo faster-whisper) não suporta MPS — só cpu/cuda/auto.
    Em macOS com WHISPER_DEVICE=mps, o whisper roda em CPU; quem de fato usa o
    Metal é a diarização (pyannote/torch), via load_diarization_pipeline.
    """
    from faster_whisper import WhisperModel

    ct2_device = "cuda" if device == "cuda" else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    return WhisperModel(model_size, device=ct2_device, compute_type=compute_type)


def transcribe(model, wav_path: Path, language: str | None) -> list[Segment]:
    raw_segments, _info = model.transcribe(str(wav_path), language=language, vad_filter=True)
    return [Segment(start=s.start, end=s.end, text=s.text.strip()) for s in raw_segments]


def load_diarization_pipeline(hf_token: str, device: str):
    """Carrega o pipeline de diarização. Custoso — chame uma vez e reutilize entre transcrições."""
    import torch
    from pyannote.audio import Pipeline

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1", token=hf_token
    )
    if device in ("cuda", "mps"):
        pipeline.to(torch.device(device))
    return pipeline


def diarize(pipeline, wav_path: Path) -> list[Turn]:
    import torchaudio
    waveform, sample_rate = torchaudio.load(str(wav_path))
    audio_in_memory = {"waveform": waveform, "sample_rate": sample_rate}
    
    diarization = pipeline(audio_in_memory)
    annotation = getattr(diarization, "speaker_diarization", diarization)
    turns = [
        Turn(start=turn.start, end=turn.end, speaker=speaker)
        for turn, _, speaker in annotation.itertracks(yield_label=True)
    ]
    turns.sort(key=lambda t: t.start)
    return turns


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_speakers(segments: list[Segment], turns: list[Turn]) -> None:
    """Atribui a cada segmento transcrito o rótulo de speaker (pessoaN) com maior sobreposição."""
    if not turns:
        return

    order: list[str] = []
    for turn in turns:
        if turn.speaker not in order:
            order.append(turn.speaker)
    label_map = {raw: f"pessoa{i + 1}" for i, raw in enumerate(order)}

    for seg in segments:
        best_turn = max(turns, key=lambda t: _overlap(seg.start, seg.end, t.start, t.end))
        if _overlap(seg.start, seg.end, best_turn.start, best_turn.end) == 0:
            best_turn = min(turns, key=lambda t: abs(t.start - seg.start))
        seg.speaker = label_map[best_turn.speaker]


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def write_txt(segments: list[Segment], output_path: Path) -> None:
    lines = []
    for seg in segments:
        prefix = f"[{seg.speaker}] " if seg.speaker else ""
        lines.append(f"{prefix}{format_timestamp(seg.start)} - {format_timestamp(seg.end)}: {seg.text}")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_json(segments: list[Segment], output_path: Path) -> None:
    output_path.write_text(
        json.dumps([asdict(s) for s in segments], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcreve um arquivo de áudio e identifica speakers.")
    parser.add_argument("audio", type=Path, help="Caminho do arquivo de áudio (mp3, wav, etc.)")
    parser.add_argument("--model", default="small", help="Tamanho do modelo Whisper (tiny/base/small/medium/large-v3)")
    parser.add_argument("--language", default=None, help="Código do idioma (ex: pt). Default: detecção automática")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Dispositivo de inferência")
    parser.add_argument("--no-diarization", action="store_true", help="Pula a identificação de speakers")
    parser.add_argument("--output", type=Path, default=None, help="Caminho de saída (sem extensão). Default: nome do áudio")
    args = parser.parse_args()

    if not args.audio.exists():
        sys.exit(f"Arquivo não encontrado: {args.audio}")

    load_dotenv()

    output_base = args.output or args.audio.with_suffix("")

    print(f"Convertendo áudio: {args.audio}")
    wav_path = to_wav(args.audio)

    try:
        print(f"Transcrevendo (modelo={args.model}, device={args.device})...")
        model = load_whisper_model(args.model, args.device)
        segments = transcribe(model, wav_path, args.language)

        if not args.no_diarization:
            hf_token = os.environ.get("HF_TOKEN")
            if not hf_token:
                sys.exit(
                    "HF_TOKEN não definido. Crie um token em https://huggingface.co/settings/tokens, "
                    "aceite os termos em https://huggingface.co/pyannote/speaker-diarization-3.1, "
                    "https://huggingface.co/pyannote/segmentation-3.0 e "
                    "https://huggingface.co/pyannote/speaker-diarization-community-1, e defina HF_TOKEN no arquivo .env "
                    "(veja .env.example). Ou use --no-diarization para pular essa etapa."
                )
            print("Identificando speakers...")
            pipeline = load_diarization_pipeline(hf_token, args.device)
            turns = diarize(pipeline, wav_path)
            assign_speakers(segments, turns)
    finally:
        wav_path.unlink(missing_ok=True)

    txt_output = output_base.with_suffix(".txt")
    json_output = output_base.with_suffix(".json")
    write_txt(segments, txt_output)
    write_json(segments, json_output)

    print(f"Concluído. Saída: {txt_output} e {json_output}")


if __name__ == "__main__":
    main()
