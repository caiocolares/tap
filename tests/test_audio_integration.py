"""Smoke test opcional da conversão real; não depende dos modelos de IA."""

import shutil
import wave

import pytest

from transcribe import to_wav


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg não está instalado")
def test_real_conversion_produces_mono_audio_at_16khz(tmp_path):
    source = tmp_path / "stereo.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(22050)
        audio.writeframes(b"\x00\x00\x00\x00" * 2205)

    output = to_wav(source)
    try:
        with wave.open(str(output), "rb") as audio:
            assert audio.getnchannels() == 1
            assert audio.getframerate() == 16000
            assert audio.getnframes() > 0
    finally:
        output.unlink(missing_ok=True)
