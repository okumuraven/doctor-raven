"""Push-to-talk microphone recording via arecord (ALSA) — no new audio-library dependency
for capture. Nothing records until you explicitly start it, and `max_seconds` is a hard cap
on the worst case regardless of whether you remember to stop it yourself."""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class RecorderError(RuntimeError):
    pass


@dataclass
class Recording:
    process: subprocess.Popen
    wav_path: Path


def start(max_seconds: float) -> Recording:
    if not shutil.which("arecord"):
        raise RecorderError("`arecord` not found (part of alsa-utils) — needed to capture the microphone.")

    wav_path = Path(tempfile.mkstemp(suffix=".wav", prefix="raven-voice-")[1])
    process = subprocess.Popen(
        ["arecord", "-f", "cd", "-t", "wav", "-d", str(int(max_seconds)), str(wav_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return Recording(process=process, wav_path=wav_path)


def stop(recording: Recording) -> Path:
    if recording.process.poll() is None:
        recording.process.terminate()
        try:
            recording.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            recording.process.kill()

    if not recording.wav_path.exists() or recording.wav_path.stat().st_size == 0:
        raise RecorderError("No audio captured.")
    return recording.wav_path
