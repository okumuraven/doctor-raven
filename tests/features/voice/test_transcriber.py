import sys
import types

import pytest

from doctor_raven.features.voice import transcriber


class FakeConfig:
    voice_stt_model = "tiny.en"
    voice_cpu_threads = 0


class FakeSegment:
    def __init__(self, text):
        self.text = text


class FakeWhisperModel:
    instances = []

    def __init__(self, model_size_or_path, **kwargs):
        self.model_size_or_path = model_size_or_path
        self.init_kwargs = kwargs
        FakeWhisperModel.instances.append(self)

    def transcribe(self, audio):
        return [FakeSegment(" hello "), FakeSegment("world ")], object()


@pytest.fixture(autouse=True)
def _clear_model_cache():
    transcriber._model_cache.clear()
    FakeWhisperModel.instances.clear()
    yield
    transcriber._model_cache.clear()


def _install_fake_faster_whisper(monkeypatch):
    fake_module = types.ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)


def test_resolve_cpu_threads_uses_configured_value_when_positive():
    assert transcriber._resolve_cpu_threads(4) == 4


def test_resolve_cpu_threads_defaults_to_half_cores_when_zero(monkeypatch):
    monkeypatch.setattr(transcriber.os, "cpu_count", lambda: 8)
    assert transcriber._resolve_cpu_threads(0) == 4


def test_resolve_cpu_threads_never_zero_on_a_single_core_box(monkeypatch):
    monkeypatch.setattr(transcriber.os, "cpu_count", lambda: 1)
    assert transcriber._resolve_cpu_threads(0) == 1


def test_transcribe_joins_segment_text(monkeypatch, tmp_path):
    _install_fake_faster_whisper(monkeypatch)
    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(b"fake")

    result = transcriber.transcribe(wav_path, FakeConfig())

    assert result == "hello world"


def test_transcribe_reuses_cached_model_across_calls(monkeypatch, tmp_path):
    _install_fake_faster_whisper(monkeypatch)
    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(b"fake")

    transcriber.transcribe(wav_path, FakeConfig())
    transcriber.transcribe(wav_path, FakeConfig())

    assert len(FakeWhisperModel.instances) == 1


def test_transcribe_raises_when_faster_whisper_not_installed(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(b"fake")

    with pytest.raises(transcriber.TranscriptionError, match="isn't installed"):
        transcriber.transcribe(wav_path, FakeConfig())
