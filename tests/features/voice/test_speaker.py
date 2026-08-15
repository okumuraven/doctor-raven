import sys
import types

import pytest

from doctor_raven.features.voice import speaker


class FakeConfig:
    voice_tts_voice = "en_US-lessac-medium"


class FakePiperVoice:
    loaded_from = []

    @classmethod
    def load(cls, model_path):
        cls.loaded_from.append(model_path)
        return cls()

    def synthesize_wav(self, text, wav_file):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)


@pytest.fixture(autouse=True)
def _clear_voice_cache():
    speaker._voice_cache.clear()
    FakePiperVoice.loaded_from.clear()
    yield
    speaker._voice_cache.clear()


def _install_fake_piper(monkeypatch):
    fake_piper_module = types.ModuleType("piper")
    fake_piper_module.PiperVoice = FakePiperVoice
    monkeypatch.setitem(sys.modules, "piper", fake_piper_module)


def _install_fake_download_voices(monkeypatch, side_effect=None):
    fake_module = types.ModuleType("piper.download_voices")
    calls = []

    def fake_download_voice(voice, download_dir):
        calls.append((voice, download_dir))
        if side_effect:
            side_effect(voice, download_dir)

    fake_module.download_voice = fake_download_voice
    monkeypatch.setitem(sys.modules, "piper.download_voices", fake_module)
    return calls


def test_ensure_voice_downloaded_skips_download_when_both_files_exist(monkeypatch, tmp_path):
    monkeypatch.setattr(speaker, "ensure_data_dir", lambda: tmp_path)
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    (voices_dir / "en_US-lessac-medium.onnx").write_bytes(b"fake model")
    (voices_dir / "en_US-lessac-medium.onnx.json").write_bytes(b"{}")
    calls = _install_fake_download_voices(monkeypatch)

    result = speaker._ensure_voice_downloaded("en_US-lessac-medium")

    assert calls == []
    assert result == voices_dir / "en_US-lessac-medium.onnx"


def test_ensure_voice_downloaded_redownloads_when_config_missing_after_interrupted_download(monkeypatch, tmp_path):
    """Regression test: a process killed mid-download can leave the .onnx model present with
    its .onnx.json config never written. Checking only the model file's existence would wrongly
    treat that interrupted state as already complete."""
    monkeypatch.setattr(speaker, "ensure_data_dir", lambda: tmp_path)
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    (voices_dir / "en_US-lessac-medium.onnx").write_bytes(b"partial model from interrupted download")
    calls = _install_fake_download_voices(monkeypatch)

    result = speaker._ensure_voice_downloaded("en_US-lessac-medium")

    assert calls == [("en_US-lessac-medium", voices_dir)]
    assert result == voices_dir / "en_US-lessac-medium.onnx"


def test_ensure_voice_downloaded_calls_download_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(speaker, "ensure_data_dir", lambda: tmp_path)
    calls = _install_fake_download_voices(monkeypatch)

    speaker._ensure_voice_downloaded("en_US-lessac-medium")

    assert calls == [("en_US-lessac-medium", tmp_path / "voices")]


def test_ensure_voice_downloaded_wraps_download_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(speaker, "ensure_data_dir", lambda: tmp_path)

    def boom(voice, download_dir):
        raise RuntimeError("network down")

    _install_fake_download_voices(monkeypatch, side_effect=boom)

    with pytest.raises(speaker.SpeechError, match="Couldn't download"):
        speaker._ensure_voice_downloaded("en_US-lessac-medium")


def test_speak_raises_when_aplay_missing(monkeypatch):
    monkeypatch.setattr(speaker.shutil, "which", lambda name: None)
    with pytest.raises(speaker.SpeechError, match="aplay"):
        speaker.speak("hello", FakeConfig())


def test_speak_synthesizes_and_plays_then_cleans_up_temp_file(monkeypatch, tmp_path):
    monkeypatch.setattr(speaker.shutil, "which", lambda name: "/usr/bin/aplay")
    monkeypatch.setattr(speaker, "ensure_data_dir", lambda: tmp_path)
    _install_fake_piper(monkeypatch)
    _install_fake_download_voices(
        monkeypatch, side_effect=lambda voice, download_dir: (download_dir / f"{voice}.onnx").write_bytes(b"x")
    )

    calls = []
    monkeypatch.setattr(speaker.subprocess, "run", lambda args, **kwargs: calls.append(args))

    speaker.speak("hello there", FakeConfig())

    assert calls[0][0] == "aplay"
    wav_arg = calls[0][-1]
    assert not __import__("pathlib").Path(wav_arg).exists()  # temp wav cleaned up after playback


def test_speak_reuses_cached_voice_across_calls(monkeypatch, tmp_path):
    monkeypatch.setattr(speaker.shutil, "which", lambda name: "/usr/bin/aplay")
    monkeypatch.setattr(speaker, "ensure_data_dir", lambda: tmp_path)
    _install_fake_piper(monkeypatch)
    _install_fake_download_voices(
        monkeypatch, side_effect=lambda voice, download_dir: (download_dir / f"{voice}.onnx").write_bytes(b"x")
    )
    monkeypatch.setattr(speaker.subprocess, "run", lambda args, **kwargs: None)

    speaker.speak("first", FakeConfig())
    speaker.speak("second", FakeConfig())

    assert len(FakePiperVoice.loaded_from) == 1
