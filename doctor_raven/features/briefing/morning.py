"""Orchestrates the daily morning briefing: schedule, reminders, research, and a quick maintenance check."""

from datetime import date

from doctor_raven.config import Config
from doctor_raven.core.db import get_conn
from doctor_raven.core.llm_router import NoLLMAvailable
from doctor_raven.features import maintenance, reminders, research, schedule
from doctor_raven.util.formatting import console, print_section, print_warn
from rich.markup import escape


def _already_ran_today() -> bool:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM briefing_runs WHERE run_date = ?", (today,)).fetchone()
        return row is not None


def _record_run() -> None:
    today = date.today().isoformat()
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO briefing_runs (run_date) VALUES (?)", (today,))


def run_morning_briefing(config: Config, force: bool = False) -> None:
    if not force and _already_ran_today():
        console.print("Already ran today's briefing. Use --force to rerun.")
        return

    console.rule("[bold]Doctor Raven — Morning Briefing[/bold]")

    print_section("Today's tasks")
    due_tasks = schedule.list_due_today()
    if not due_tasks:
        console.print("  Nothing due today.")
    for task in due_tasks:
        line = f"  [{task.priority}] {task.title}" + (f" (due {task.due_date})" if task.due_date else "")
        console.print(line, markup=False)

    print_section("Reminders")
    due_reminders = reminders.list_due()
    if not due_reminders:
        console.print("  Nothing due right now.")
    for reminder in due_reminders:
        reminders.notify("Doctor Raven reminder", reminder.message)
        reminders.mark_fired(reminder.id)
        console.print(f"  Fired: {reminder.message}", markup=False)

    print_section("Brainstorm / research digest")
    topics = research.list_topics()
    if not topics:
        console.print("  No active research topics. Add one with `raven research add <topic>`.")
    else:
        try:
            digests = research.brainstorm_all(config, topics)
            for name, text in digests.items():
                console.print(f"  [bold]{escape(name)}[/bold]:")
                console.print("    " + text.replace("\n", "\n    "), markup=False)
        except NoLLMAvailable as exc:
            print_warn(str(exc))

    print_section("Maintenance status")
    try:
        status = maintenance.list_upgradable()
        console.print(f"  {status.upgradable_count} package(s) upgradable. Run `raven maintain` for details.")
    except Exception as exc:  # apt not available, sandboxed env, etc.
        print_warn(f"Could not check apt status: {exc}")

    _record_run()
    console.rule()
