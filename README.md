# Doctor Raven

A local-first intelligent assistant for daily work as a software engineer and cybersecurity specialist on Parrot OS. CLI-first; no cloud dependency required for the basics.

## What it does

- `raven morning` — daily briefing: today's tasks, due reminders (delivered as desktop notifications), an LLM brainstorm/research digest on your saved topics, and a quick package-update status check. Runs at most once per calendar day unless `--force` is passed.
- `raven task add/list/done` — a local task list.
- `raven remind add/list` — one-off reminders, delivered via `notify-send` when due.
- `raven research add/list` — topics you want Doctor Raven to brainstorm/research on each morning.
- `raven ask "<question>" [--deep]` — ask the LLM directly. Local model by default; `--deep` forces the Claude API.
- `raven maintain [--apply] [--no-scan]` — reports upgradable apt packages and runs rkhunter/lynis/clamscan. Never applies upgrades without an explicit `--apply` flag *and* an interactive confirmation.
- `raven doctor` — checks for missing dependencies (Ollama, rkhunter, lynis, clamav, notify-send, ufw) and offers to install each one individually, with your confirmation before anything is installed.
- `raven fw status/allow/deny/delete/enable/disable` — ufw-backed firewall management. Every rule change previews the exact command first and requires confirmation (`y/N`, or typing `confirm` for changes that risk locking you out of SSH) before it runs. See [Firewall.md](Firewall.md) for the full explanation.

## Architecture

- Python, Typer CLI, SQLite for local storage (`~/.local/share/doctor-raven/raven.db`).
- Feature-based modules under `doctor_raven/features/`: `schedule`, `reminders`, `research`, `maintenance`, `briefing`.
- Hybrid LLM routing (`doctor_raven/core/llm_router.py`): local Ollama by default, Claude API for `--deep` requests or as an automatic fallback if Ollama is unreachable and `ANTHROPIC_API_KEY` is set.
- No `/frontend`/`/backend` split — this is a CLI/daemon tool with no web UI. No PostgreSQL/Docker — single-user local data fits SQLite with zero infra.

## Setup

```bash
./scripts/install.sh
```

This creates a venv at `~/.local/share/doctor-raven/venv`, installs the package, and stages (but does not enable) the systemd user units. It prints the remaining manual steps — nothing is enabled, started, or `sudo`'d without you running it yourself.

### Environment variables

- `ANTHROPIC_API_KEY` — optional. Needed for `--deep` requests and as the Ollama-unreachable fallback. Put it in `~/.config/doctor-raven/env` (chmod 600) so the systemd services can read it via `EnvironmentFile`.

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
