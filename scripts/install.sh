#!/usr/bin/env bash
# Sets up Doctor Raven's venv and stages systemd user units.
# Does NOT enable/start anything automatically or run sudo — you run those steps yourself, printed at the end.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/doctor-raven"
VENV_DIR="$DATA_DIR/venv"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

echo "Installing Doctor Raven from $PROJECT_DIR"

mkdir -p "$DATA_DIR"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -e "$PROJECT_DIR"

mkdir -p "$SYSTEMD_USER_DIR"
cp "$PROJECT_DIR/systemd/raven-morning.service" "$SYSTEMD_USER_DIR/"
cp "$PROJECT_DIR/systemd/raven-maintenance.service" "$SYSTEMD_USER_DIR/"
cp "$PROJECT_DIR/systemd/raven-maintenance.timer" "$SYSTEMD_USER_DIR/"
cp "$PROJECT_DIR/systemd/raven-daemon.service" "$SYSTEMD_USER_DIR/"

echo
echo "Done. Binary installed at: $VENV_DIR/bin/raven"
echo
echo "Next steps (run these yourself):"
echo "  1. Optionally set secrets/env for the systemd services:"
echo "       mkdir -p ~/.config/doctor-raven && chmod 700 ~/.config/doctor-raven"
echo "       echo 'ANTHROPIC_API_KEY=sk-...' > ~/.config/doctor-raven/env"
echo "       chmod 600 ~/.config/doctor-raven/env"
echo "  2. Check dependencies (Ollama, rkhunter, lynis, clamav):"
echo "       $VENV_DIR/bin/raven doctor"
echo "  3. Reload and enable the systemd units when you're ready:"
echo "       systemctl --user daemon-reload"
echo "       systemctl --user enable --now raven-morning.service"
echo "       systemctl --user enable --now raven-maintenance.timer"
echo "       systemctl --user enable --now raven-daemon.service   # background watcher (reminders/health/CVEs)"
echo "  4. Add $VENV_DIR/bin to your PATH to run 'raven ...' directly, e.g. in ~/.zshrc:"
echo "       export PATH=\"$VENV_DIR/bin:\$PATH\""
