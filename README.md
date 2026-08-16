# Doctor Raven

A local-first intelligent assistant for daily work as a software engineer and cybersecurity specialist on Parrot OS. CLI-first. Task/reminder/research storage, security scans, and firewall management are fully local with no cloud dependency; LLM-backed features (`ask`, research digest) default to the Gemini API for speed, and `--local` forces the fully-offline Ollama path instead.

## What it does

- `raven morning` — daily briefing: today's tasks, due reminders (delivered as desktop notifications), an LLM brainstorm/research digest on your saved topics, and a quick package-update status check. Runs at most once per calendar day unless `--force` is passed.
- `raven task add/list/done` — a local task list.
- `raven remind add/list` — one-off reminders, delivered via `notify-send` when due.
- `raven research add/list` — topics you want Doctor Raven to brainstorm/research on each morning.
- `raven ask "<question>" [--local] [--deep]` — ask the LLM directly. Gemini by default; `--local` forces the on-device Ollama model instead (also gates on system health, since only this path burns local CPU); `--deep` forces the Claude API for a heavier answer.
- `raven maintain [--apply] [--no-scan]` — reports upgradable apt packages and runs rkhunter/lynis/clamscan. Never applies upgrades without an explicit `--apply` flag *and* an interactive confirmation.
- `raven doctor` — checks for missing dependencies (Ollama, rkhunter, lynis, clamav, notify-send, ufw) and offers to install each one individually, with your confirmation before anything is installed.
- `raven fw status/allow/deny/delete/enable/disable` — ufw-backed firewall management. Every rule change previews the exact command first and requires confirmation (`y/N`, or typing `confirm` for changes that risk locking you out of SSH) before it runs. See [Firewall.md](Firewall.md) for the full explanation.

## Architecture

- Python, Typer CLI, SQLite for local storage (`~/.local/share/doctor-raven/raven.db`).
- Feature-based modules under `doctor_raven/features/`: `schedule`, `reminders`, `research`, `maintenance`, `briefing`.
- Hybrid LLM routing (`doctor_raven/core/llm_router.py`): Gemini API by default (fast, creative), local Ollama via `--local` (or as an automatic fallback if Gemini isn't configured/unreachable), Claude API for `--deep` requests or as the final fallback if Ollama is also unreachable and `ANTHROPIC_API_KEY` is set. Two call sites always force the local Ollama path regardless of the default, since they fire unattended from the background daemon and shouldn't send data to a cloud API on their own timing: git auto-commit message drafting (`git_ops/repo_ops.py`) and desktop-notification phrasing (`notifications/voice.py`).
- Gemini key rotation: `GEMINI_API_KEYS` accepts a comma-separated list (e.g. one key per GCP project, so each gets its own quota pool). The starting key round-robins across separate `raven` invocations (persisted to a small state file in the data dir, since almost every command is a short-lived process — an in-memory counter would just reset every time), and within a single call, if the chosen key fails for any reason, the rest are tried in turn before falling through to Ollama.
- No `/frontend`/`/backend` split — this is a CLI/daemon tool with no web UI. No PostgreSQL/Docker — single-user local data fits SQLite with zero infra.

## Setup

```bash
./scripts/install.sh
```

This creates a venv at `~/.local/share/doctor-raven/venv`, installs the package, and stages (but does not enable) the systemd user units. It prints the remaining manual steps — nothing is enabled, started, or `sudo`'d without you running it yourself.

### Environment variables

- `GEMINI_API_KEY` (single key) or `GEMINI_API_KEYS` (comma-separated, enables rotation across multiple keys/projects) — needed for the default (non-`--local`, non-`--deep`) LLM path. Without either, `ask`/research digest fall straight through to Ollama, then Claude, same as before this default existed. Put it in `~/.config/doctor-raven/env` (chmod 600) so the systemd services can read it via `EnvironmentFile`.
- `ANTHROPIC_API_KEY` — optional. Needed for `--deep` requests and as the final fallback if both Gemini and Ollama are unavailable. Same `env` file as above.

### Local LLM (Ollama)

Not installed by this repo automatically. Run `raven doctor` — it detects Ollama is missing and offers to run the official install script after showing you exactly what it does and asking for confirmation. Once installed, pull a model:

```bash
ollama pull llama3.2
```

(Or set a different model in `~/.config/doctor-raven/config.toml` under `[llm] ollama_model`.)

### Automation (systemd --user)

- `raven-morning.service` — fires on login (`WantedBy=default.target`), runs `raven morning`. The morning-briefing dedup logic means logging in multiple times in a day only actually runs it once.
- `raven-maintenance.timer` — weekly (Mondays 09:00), runs `raven maintain` (report-only by default; `--apply` is not passed by the timer, so upgrades are never auto-applied unattended).

Enable when ready:
```bash
systemctl --user daemon-reload
systemctl --user enable --now raven-morning.service
systemctl --user enable --now raven-maintenance.timer
```

## Security notes

- `~/.config/doctor-raven/config.toml` holds only non-secret preferences (model names, ollama host). API keys are never written to disk by this tool — they're read from the environment only.
- `raven doctor` and `raven maintain --apply` never install packages or apply upgrades without an explicit, per-item interactive confirmation.
- Security scans run as your user (no automatic privilege escalation baked in beyond `rkhunter`/`apt-get`, which prompt for `sudo` themselves).

## Relationship to other projects in this workspace

- `okumuraven-automations` (Fastify/Postgres/BullMQ/Discord) is a separate, more heavyweight automation backend with its own Task/Reminder models. Doctor Raven intentionally does **not** integrate with it — it's a fully independent local tool with its own SQLite store.
- `RavenMind` is an unrelated content-moderation/identity-verification API product.
