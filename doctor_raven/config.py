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

[system_health]
temp_warn_c = 75
temp_critical_c = 90
load_warn_per_core = 0.85
load_critical_per_core = 1.5

[research]
workspace_root = "~/PROJECTS"
lookback_days = 3

[user]
name = "okumuraven"
"""


@dataclass(frozen=True)
class Config:
    ollama_host: str
    ollama_model: str
    claude_model: str
    auto_apply_updates: bool
    anthropic_api_key: str | None
    temp_warn_c: float
    temp_critical_c: float
    load_warn_per_core: float
    load_critical_per_core: float
    workspace_root: str
    lookback_days: int
    user_name: str


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
    system_health = raw.get("system_health", {})
    research = raw.get("research", {})
    user = raw.get("user", {})

    return Config(
        ollama_host=llm.get("ollama_host", "http://localhost:11434"),
        ollama_model=llm.get("ollama_model", "llama3.2"),
        claude_model=llm.get("claude_model", "claude-sonnet-5"),
        auto_apply_updates=bool(maintenance.get("auto_apply_updates", False)),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        temp_warn_c=float(system_health.get("temp_warn_c", 75)),
        temp_critical_c=float(system_health.get("temp_critical_c", 90)),
        load_warn_per_core=float(system_health.get("load_warn_per_core", 0.85)),
        load_critical_per_core=float(system_health.get("load_critical_per_core", 1.5)),
        workspace_root=research.get("workspace_root", "~/PROJECTS"),
        lookback_days=int(research.get("lookback_days", 3)),
        user_name=user.get("name", "okumuraven"),
    )


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    return DATA_DIR
