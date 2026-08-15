"""Non-secret configuration. Secrets (ANTHROPIC_API_KEY) come from the environment only."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "doctor-raven"
CONFIG_PATH = CONFIG_DIR / "config.toml"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "doctor-raven"
DB_PATH = DATA_DIR / "raven.db"

DEFAULT_CONFIG = """\
[llm]
ollama_host = "http://localhost:11434"
ollama_model = "llama3.2"
claude_model = "claude-sonnet-5"

[maintenance]
auto_apply_updates = false
"""


@dataclass(frozen=True)
class Config:
    ollama_host: str
    ollama_model: str
    claude_model: str
    auto_apply_updates: bool
    anthropic_api_key: str | None


def _ensure_config_file() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(DEFAULT_CONFIG)
        CONFIG_PATH.chmod(0o600)


def load_config() -> Config:
    _ensure_config_file()
    with CONFIG_PATH.open("rb") as f:
        raw = tomllib.load(f)

    llm = raw.get("llm", {})
    maintenance = raw.get("maintenance", {})

    return Config(
        ollama_host=llm.get("ollama_host", "http://localhost:11434"),
        ollama_model=llm.get("ollama_model", "llama3.2"),
        claude_model=llm.get("claude_model", "claude-sonnet-5"),
        auto_apply_updates=bool(maintenance.get("auto_apply_updates", False)),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    return DATA_DIR
