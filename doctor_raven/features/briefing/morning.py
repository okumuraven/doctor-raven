"""Orchestrates the daily morning briefing: schedule, reminders, research, and a quick maintenance check."""

from datetime import date

from doctor_raven.config import Config
from doctor_raven.core.db import get_conn
from doctor_raven.core.llm_router import NoLLMAvailable
from doctor_raven.features import maintenance, notifications, reminders, research, schedule, system_health
from doctor_raven.features.briefing.banner import print_banner
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

    print_banner(config)
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
        notifications.notify_and_log("Doctor Raven reminder", reminder.message, source="reminder", config=config)
        reminders.mark_fired(reminder.id)
        console.print(f"  Fired: {reminder.message}", markup=False)

    print_section("Brainstorm / research digest")
    topics = research.list_topics()
    health_status = system_health.read_status()
    decision = system_health.evaluate(health_status, config)
    if decision.level in ("hot", "critical"):
        diagnosis = system_health.diagnose(health_status)
        notifications.notify_and_log(
            "Doctor Raven — heavy task deferred",
            f"Skipped research digest ({decision.reason}). {diagnosis.recommendation}",
            source="system_health",
            config=config,
        )
        print_warn(f"Skipped research digest — system {decision.level}: {decision.reason}")
        console.print(f"    {diagnosis.recommendation}", markup=False)
    else:
        try:
            digest = research.daily_digest(config, topics)
        except NoLLMAvailable as exc:
            print_warn(str(exc))
        else:
            if digest.project_context:
                top = digest.project_context[0]
                console.print(f"  [bold]Currently on:[/bold] {escape(top.name)} ({escape(top.branch)})")
            console.print("  " + digest.synthesis.replace("\n", "\n  "), markup=False)
            if not topics:
                console.print("  No active research topics. Add one with `raven research add <topic>`.")
            for name, text in digest.topic_brainstorms.items():
                console.print(f"  [bold]{escape(name)}[/bold]:")
                console.print("    " + text.replace("\n", "\n    "), markup=False)
            notifications.send_discord(config, research.format_digest_for_discord(digest))

    print_section("Maintenance status")
    try:
        status = maintenance.list_upgradable()
        console.print(f"  {status.upgradable_count} package(s) upgradable. Run `raven maintain` for details.")
    except Exception as exc:  # apt not available, sandboxed env, etc.
        print_warn(f"Could not check apt status: {exc}")

    _record_run()
    console.rule()
