"""Local speech-to-text via faster-whisper. Model loaded lazily and cached per-process — each
`raven listen` invocation is a fresh process, so there's no persistent background model held
in memory between uses. cpu_threads defaults to half the machine's cores rather than letting
ctranslate2 grab every core for one transcription."""

import os
from pathlib import Path

from doctor_raven.config import Config

_model_cache: dict[str, object] = {}


class TranscriptionError(RuntimeError):
    pass


def _resolve_cpu_threads(cpu_threads: int) -> int:
    if cpu_threads > 0:
        return cpu_threads
    return max(1, (os.cpu_count() or 4) // 2)


def _get_model(model_name: str, cpu_threads: int):
    if model_name not in _model_cache:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscriptionError("faster-whisper isn't installed — needed for `raven listen`.") from exc
        try:
            _model_cache[model_name] = WhisperModel(
                model_name, device="cpu", compute_type="int8", cpu_threads=_resolve_cpu_threads(cpu_threads)
            )
        except Exception as exc:
            raise TranscriptionError(f"Couldn't load Whisper model '{model_name}': {exc}") from exc
    return _model_cache[model_name]


def transcribe(wav_path: Path, config: Config) -> str:
    model = _get_model(config.voice_stt_model, config.voice_cpu_threads)
    segments, _ = model.transcribe(str(wav_path))
    return " ".join(segment.text.strip() for segment in segments).strip()
