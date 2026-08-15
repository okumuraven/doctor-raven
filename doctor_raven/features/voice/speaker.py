"""Local text-to-speech via Piper, played back through aplay (ALSA) — no new audio-library
dependency for playback. The voice model downloads once (from Piper's public voice repo on
Hugging Face) into doctor-raven's own data dir and is cached in-process thereafter."""

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from doctor_raven.config import Config, ensure_data_dir

_voice_cache: dict[str, object] = {}


class SpeechError(RuntimeError):
    pass


def _voices_dir() -> Path:
    voices_dir = ensure_data_dir() / "voices"
    voices_dir.mkdir(exist_ok=True)
    return voices_dir


def _ensure_voice_downloaded(voice_name: str) -> Path:
    """PiperVoice.load() needs both the .onnx model AND its .onnx.json config — checking only
    the model file's existence would treat an interrupted download (e.g. killed mid-transfer,
    model file present but config never reached) as already complete."""
    voices_dir = _voices_dir()
    model_path = voices_dir / f"{voice_name}.onnx"
    config_path = voices_dir / f"{voice_name}.onnx.json"
    if not model_path.exists() or not config_path.exists():
        try:
            from piper.download_voices import download_voice
        except ImportError as exc:
            raise SpeechError("piper-tts isn't installed — needed for spoken responses.") from exc
        try:
            download_voice(voice_name, voices_dir)
        except Exception as exc:
            raise SpeechError(f"Couldn't download Piper voice '{voice_name}': {exc}") from exc
    return model_path


def _get_voice(voice_name: str):
    if voice_name not in _voice_cache:
        try:
            from piper import PiperVoice
        except ImportError as exc:
            raise SpeechError("piper-tts isn't installed — needed for spoken responses.") from exc
        model_path = _ensure_voice_downloaded(voice_name)
        try:
            _voice_cache[voice_name] = PiperVoice.load(model_path)
        except Exception as exc:
            raise SpeechError(f"Couldn't load Piper voice '{voice_name}': {exc}") from exc
    return _voice_cache[voice_name]


def speak(text: str, config: Config) -> None:
    if not shutil.which("aplay"):
        raise SpeechError("`aplay` not found (part of alsa-utils) — needed for audio playback.")

    voice = _get_voice(config.voice_tts_voice)
    wav_path = Path(tempfile.mkstemp(suffix=".wav", prefix="raven-speak-")[1])
    try:
        with wave.open(str(wav_path), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        subprocess.run(["aplay", "-q", str(wav_path)], capture_output=True)
    finally:
        wav_path.unlink(missing_ok=True)
