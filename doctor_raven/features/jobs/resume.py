"""Resume ingestion: extracts text from a PDF or plain-text file and stores it locally for
matching against job listings. Stays on disk under Doctor Raven's own data dir — never
uploaded anywhere; the only thing that leaves the machine is whatever LLM backend is in use
when `raven jobs search` actually scores listings against it."""

from pathlib import Path

from doctor_raven.config import ensure_data_dir


class ResumeError(RuntimeError):
    pass


def _resume_path() -> Path:
    return ensure_data_dir() / "resume.txt"


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ResumeError("pypdf isn't installed — needed to read PDF resumes.") from exc
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def ingest(source_path: str) -> str:
    path = Path(source_path).expanduser().resolve()
    if not path.exists():
        raise ResumeError(f"File not found: {path}")

    text = _extract_pdf_text(path) if path.suffix.lower() == ".pdf" else path.read_text(errors="ignore")
    text = text.strip()
    if not text:
        raise ResumeError(f"Couldn't extract any text from {path}")

    _resume_path().write_text(text)
    return text


def load() -> str | None:
    path = _resume_path()
    return path.read_text() if path.exists() else None
