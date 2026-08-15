"""Consolidated status view — one-shot (`raven status`) or live-refreshing (`raven dashboard`) —
so a notify-send popup always has a glanceable 'what's going on' to check against."""

import time
from datetime import datetime

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from doctor_raven.config import Config
from doctor_raven.features import maintenance, notifications, reminders, schedule, system_health
from doctor_raven.util.formatting import console

PACKAGE_REFRESH_INTERVAL_SECONDS = 60.0
HEALTH_MARKERS = {"normal": "✓", "hot": "!", "critical": "✗"}


def _safe_upgradable_count() -> int | None:
    try:
        return maintenance.list_upgradable().upgradable_count
    except Exception:
        return None


def _health_line(config: Config) -> str:
    status = system_health.read_status()
    decision = system_health.evaluate(status, config)
    temp_str = f"{status.cpu_temp_c:.0f}°C" if status.cpu_temp_c is not None else "n/a"
    marker = HEALTH_MARKERS[decision.level]
    return f"{marker} {decision.level}: {temp_str}, load {status.load_per_core:.2f}/core — {decision.reason}"


def _tasks_table() -> Table:
    table = Table(title="Tasks due today", expand=True)
    table.add_column("Priority")
    table.add_column("Title")
    due = schedule.list_due_today()
    if not due:
        table.add_row("-", "Nothing due today")
    for task in due:
        table.add_row(task.priority, task.title)
    return table


def _reminders_table() -> Table:
    table = Table(title="Pending reminders", expand=True)
    table.add_column("When")
    table.add_column("Message")
    pending = reminders.list_reminders()
    if not pending:
        table.add_row("-", "Nothing pending")
    for reminder in pending:
        table.add_row(reminder.remind_at, reminder.message)
    return table


def _notifications_table() -> Table:
    table = Table(title="Recent notifications", expand=True)
    table.add_column("When")
    table.add_column("Source")
    table.add_column("Message")
    recent = notifications.list_recent(limit=10)
    if not recent:
        table.add_row("-", "-", "Nothing logged yet")
    for entry in recent:
        table.add_row(entry.created_at, entry.source, entry.message)
    return table


def build_status_panel(config: Config, upgradable_count: int | None) -> Panel:
    package_line = f"{upgradable_count} package(s) upgradable" if upgradable_count is not None else "unavailable"
    body = Group(
        f"[bold]System health:[/bold] {_health_line(config)}",
        f"[bold]Maintenance:[/bold] {package_line}",
        "",
        _tasks_table(),
        _reminders_table(),
        _notifications_table(),
    )
    return Panel(body, title="Doctor Raven", subtitle=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def run_status(config: Config) -> None:
    console.print(build_status_panel(config, _safe_upgradable_count()))


def run_dashboard(config: Config, refresh_seconds: float = 3.0) -> None:
    notifications.mark_dashboard_running()
    upgradable_count = _safe_upgradable_count()
    last_package_check = time.monotonic()
    try:
        with Live(build_status_panel(config, upgradable_count), console=console, refresh_per_second=1) as live:
            while True:
                time.sleep(refresh_seconds)
                if time.monotonic() - last_package_check >= PACKAGE_REFRESH_INTERVAL_SECONDS:
                    upgradable_count = _safe_upgradable_count()
                    last_package_check = time.monotonic()
                live.update(build_status_panel(config, upgradable_count))
    except KeyboardInterrupt:
        console.print("\nExiting dashboard.")
    finally:
        notifications.clear_dashboard_running()
