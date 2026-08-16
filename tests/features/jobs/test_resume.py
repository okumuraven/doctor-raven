import pytest

from doctor_raven.features.jobs import resume


def test_ingest_raises_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(resume, "ensure_data_dir", lambda: tmp_path)
    with pytest.raises(resume.ResumeError, match="not found"):
        resume.ingest(str(tmp_path / "nope.txt"))


def test_ingest_and_load_roundtrip_plain_text(tmp_path, monkeypatch):
    monkeypatch.setattr(resume, "ensure_data_dir", lambda: tmp_path)
    source = tmp_path / "resume.txt"
    source.write_text("Jane Doe — Software Engineer\n5 years Python, React.")

    text = resume.ingest(str(source))

    assert "Software Engineer" in text
    assert resume.load() == text


def test_load_returns_none_when_nothing_ingested(tmp_path, monkeypatch):
    monkeypatch.setattr(resume, "ensure_data_dir", lambda: tmp_path)
    assert resume.load() is None


def test_ingest_raises_when_extracted_text_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(resume, "ensure_data_dir", lambda: tmp_path)
    source = tmp_path / "empty.txt"
    source.write_text("   \n\n  ")

    with pytest.raises(resume.ResumeError, match="Couldn't extract"):
        resume.ingest(str(source))


def test_ingest_expands_user_and_resolves_path(tmp_path, monkeypatch):
    monkeypatch.setattr(resume, "ensure_data_dir", lambda: tmp_path)
    source = tmp_path / "resume.txt"
    source.write_text("content")

    resume.ingest(str(source))
    assert resume.load() == "content"
