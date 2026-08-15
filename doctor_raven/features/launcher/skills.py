"""A fixed, small set of app-launching actions — deliberately not generic 'control any app'
automation. Each skill is a specific, safe subprocess call; nothing here clicks around a GUI
or takes actions inside another app once it's open."""

import shutil
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import quote

from doctor_raven.config import Config

TERMINAL_FALLBACKS = ("x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm")


class SkillError(RuntimeError):
    pass


def _resolve_path(path: str | None) -> Path:
    resolved = Path(path).expanduser().resolve() if path else Path.cwd()
    if not resolved.exists():
        raise SkillError(f"Path does not exist: {resolved}")
    return resolved


def open_vscode(path: str | None = None) -> str:
    if not shutil.which("code"):
        raise SkillError("VS Code's `code` command isn't on PATH. Install it or add it to PATH.")
    resolved = _resolve_path(path)
    subprocess.Popen(["code", str(resolved)])
    return f"Opened VS Code at {resolved}"


def open_terminal(path: str | None = None, terminal_command: str = "") -> str:
    resolved = _resolve_path(path)
    binary = terminal_command or next((b for b in TERMINAL_FALLBACKS if shutil.which(b)), None)
    if not binary:
        raise SkillError("No terminal emulator found. Set `[launcher] terminal_command` in config.toml.")
    subprocess.Popen([binary], cwd=resolved)
    return f"Opened a terminal in {resolved}"


def open_browser(url: str) -> str:
    if not (url.startswith("http://") or url.startswith("https://")):
        url = f"https://{url}"
    if not webbrowser.open(url):
        raise SkillError(f"Couldn't find a way to open a browser for: {url}")
    return f"Opened {url}"


def web_search(query: str, config: Config) -> str:
    url = f"{config.search_engine_url}{quote(query)}"
    if not webbrowser.open(url):
        raise SkillError(f"Couldn't find a way to open a browser for the search: {query}")
    return f"Searched: {query}"
