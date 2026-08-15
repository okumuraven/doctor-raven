import pytest

from doctor_raven.features.voice import recorder


class FakeProcess:
    def __init__(self):
        self.terminated = False
        self._poll_value = None

    def poll(self):
        return self._poll_value

    def terminate(self):
        self.terminated = True
        self._poll_value = 0

    def wait(self, timeout=None):
        pass

    def kill(self):
        pass


def test_start_raises_when_arecord_missing(monkeypatch):
    monkeypatch.setattr(recorder.shutil, "which", lambda name: None)
    with pytest.raises(recorder.RecorderError, match="arecord"):
        recorder.start(30)


def test_start_launches_arecord_with_max_seconds_cap(monkeypatch):
    monkeypatch.setattr(recorder.shutil, "which", lambda name: "/usr/bin/arecord")
    calls = []
    monkeypatch.setattr(recorder.subprocess, "Popen", lambda args, **kwargs: calls.append(args) or FakeProcess())

    result = recorder.start(45)

    assert calls[0][:2] == ["arecord", "-f"]
    assert "45" in calls[0]
    assert result.wav_path.suffix == ".wav"


def test_stop_terminates_still_running_process_and_returns_path(monkeypatch, tmp_path):
    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(b"fake audio data")
    process = FakeProcess()

    result = recorder.stop(recorder.Recording(process=process, wav_path=wav_path))

    assert process.terminated is True
    assert result == wav_path


def test_stop_does_not_terminate_already_finished_process(tmp_path):
    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(b"fake audio data")
    process = FakeProcess()
    process._poll_value = 0  # already finished on its own (hit max_seconds)

    recorder.stop(recorder.Recording(process=process, wav_path=wav_path))

    assert process.terminated is False


def test_stop_raises_when_no_audio_captured(tmp_path):
    wav_path = tmp_path / "empty.wav"
    wav_path.write_bytes(b"")
    process = FakeProcess()
    process._poll_value = 0

    with pytest.raises(recorder.RecorderError, match="No audio"):
        recorder.stop(recorder.Recording(process=process, wav_path=wav_path))


def test_stop_raises_when_wav_file_missing(tmp_path):
    process = FakeProcess()
    process._poll_value = 0

    with pytest.raises(recorder.RecorderError, match="No audio"):
        recorder.stop(recorder.Recording(process=process, wav_path=tmp_path / "never-existed.wav"))
