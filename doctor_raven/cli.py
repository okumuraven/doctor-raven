"""Doctor Raven CLI entry point. Wires Typer subcommands to the feature modules."""

from pathlib import Path

import typer

from doctor_raven.config import load_config
from doctor_raven.core import llm_router
from doctor_raven.features import briefing, maintenance, reminders, research, schedule, security
from doctor_raven.util.formatting import console, print_error, print_ok, print_section, print_warn

app = typer.Typer(help="Doctor Raven — a local-first intelligent assistant for daily engineering/security work.")
task_app = typer.Typer(help="Manage tasks")
remind_app = typer.Typer(help="Manage reminders")
research_app = typer.Typer(help="Manage research topics")
sec_app = typer.Typer(help="Security posture checks and CVE lookups")
app.add_typer(task_app, name="task")
app.add_typer(remind_app, name="remind")
app.add_typer(research_app, name="research")
app.add_typer(sec_app, name="sec")


@app.command()
def morning(force: bool = typer.Option(False, "--force", help="Rerun even if already run today")) -> None:
    """Run the daily morning briefing: schedule, reminders, brainstorm, maintenance status."""
    config = load_config()
    briefing.run_morning_briefing(config, force=force)


@task_app.command("add")
def task_add(
    title: str,
    due: str | None = typer.Option(None, "--due", help="ISO date, e.g. 2026-08-20"),
    priority: str = typer.Option("medium", "--priority", help="low, medium, or high"),
    notes: str | None = typer.Option(None, "--notes"),
) -> None:
    task = schedule.add_task(title, notes=notes, due_date=due, priority=priority)
    print_ok(f"Added task #{task.id}: {task.title}")


@task_app.command("list")
def task_list(all_: bool = typer.Option(False, "--all", help="Include completed tasks")) -> None:
    tasks = schedule.list_tasks(include_done=all_)
    if not tasks:
        console.print("No tasks.")
        return
    for task in tasks:
        due = f" (due {task.due_date})" if task.due_date else ""
        console.print(f"#{task.id} [{task.priority}] {task.status} {task.title}{due}", markup=False)


@task_app.command("done")
def task_done(task_id: int) -> None:
    if schedule.complete_task(task_id):
        print_ok(f"Marked task #{task_id} done")
    else:
        print_error(f"Task #{task_id} not found")
        raise typer.Exit(1)


@remind_app.command("add")
def remind_add(
    message: str,
    at: str = typer.Option(..., "--at", help="ISO datetime, e.g. 2026-08-16T09:00"),
    task_id: int | None = typer.Option(None, "--task-id"),
) -> None:
    reminder = reminders.add_reminder(message, at, task_id=task_id)
    print_ok(f"Added reminder #{reminder.id} at {reminder.remind_at}")


@remind_app.command("list")
def remind_list(all_: bool = typer.Option(False, "--all", help="Include already-fired reminders")) -> None:
    items = reminders.list_reminders(include_fired=all_)
    if not items:
        console.print("No reminders.")
        return
    for reminder in items:
        fired = " [fired]" if reminder.fired else ""
        console.print(f"#{reminder.id} {reminder.remind_at} — {reminder.message}{fired}", markup=False)


@research_app.command("add")
def research_add(name: str, description: str | None = typer.Option(None, "--description")) -> None:
    topic = research.add_topic(name, description=description)
    print_ok(f"Added topic #{topic.id}: {topic.name}")


@research_app.command("list")
def research_list() -> None:
    topics = research.list_topics()
    if not topics:
        console.print("No active topics.")
        return
    for topic in topics:
        desc = f" — {topic.description}" if topic.description else ""
        console.print(f"#{topic.id} {topic.name}{desc}", markup=False)


@app.command()
def ask(
    question: str,
    deep: bool = typer.Option(False, "--deep", help="Use the Claude API instead of the local model"),
) -> None:
    config = load_config()
    try:
        console.print(llm_router.complete(config, question, deep=deep), markup=False)
    except llm_router.NoLLMAvailable as exc:
        print_error(str(exc))
        raise typer.Exit(1)


@app.command()
def maintain(
    apply_updates: bool = typer.Option(
        False, "--apply", help="Actually apply available upgrades, after an interactive confirmation"
    ),
    scan: bool = typer.Option(True, "--scan/--no-scan", help="Run security scans (rkhunter/lynis/clamscan)"),
) -> None:
    print_section("Package updates")
    status = maintenance.list_upgradable()
    console.print(f"  {status.upgradable_count} package(s) upgradable")
    for pkg in status.packages[:20]:
        console.print(f"    - {pkg}", markup=False)

    if status.upgradable_count and apply_updates:
        if typer.confirm(f"Apply {status.upgradable_count} upgrade(s) now via sudo apt-get upgrade?"):
            refreshed_ok, refresh_output = maintenance.refresh_index()
            if not refreshed_ok:
                print_error(f"apt-get update failed, aborting upgrade: {refresh_output[-500:]}")
            else:
                applied_ok, apply_output = maintenance.apply_upgrades()
                if applied_ok:
                    print_ok("Upgrades applied.")
                else:
                    print_error(f"Upgrade failed: {apply_output[-500:]}")
        else:
            console.print("  Skipped applying upgrades.")

    if scan:
        print_section("Security scan")
        for result in maintenance.run_security_scans():
            if result.ok:
                print_ok(f"{result.tool}: {result.summary}")
            elif result.installed:
                print_warn(f"{result.tool}: {result.summary}")
            else:
                print_error(f"{result.tool}: {result.summary}")


@app.command()
def doctor() -> None:
    """Check for missing dependencies (Ollama, rkhunter, lynis, clamav, notify-send) and offer to install them."""
    config = load_config()
    maintenance.run_doctor(config)


@sec_app.command("posture")
def sec_posture() -> None:
    """Read-only local security posture snapshot: listening ports, firewall, failed logins, recent logins."""
    print_section("Security posture")
    for check in security.run_posture_checks():
        if check.ok is True:
            print_ok(f"{check.name}: {check.summary}")
        elif check.ok is False:
            print_error(f"{check.name}: {check.summary}")
        else:
            print_warn(f"{check.name}: {check.summary}")


@sec_app.command("cve")
def sec_cve(ecosystem: str, name: str, version: str) -> None:
    """Check a single package for known CVEs via OSV.dev. Ecosystem examples: PyPI, npm, Go, crates.io."""
    try:
        vulns = security.check_package(ecosystem, name, version)
    except security.OSVUnavailable as exc:
        print_error(str(exc))
        raise typer.Exit(1)

    if not vulns:
        print_ok(f"No known vulnerabilities for {name}=={version} ({ecosystem})")
        return

    print_warn(f"{len(vulns)} known vulnerabilit{'y' if len(vulns) == 1 else 'ies'} for {name}=={version}:")
    for vuln in vulns:
        summary = vuln.get("summary") or (vuln.get("details") or "")[:200]
        console.print(f"    {vuln.get('id', '?')}: {summary}", markup=False)


@sec_app.command("scan-deps")
def sec_scan_deps(path: str) -> None:
    """Scan a requirements.txt or package-lock.json for dependencies with known CVEs (via OSV.dev)."""
    file_path = Path(path)
    if not file_path.exists():
        print_error(f"File not found: {path}")
        raise typer.Exit(1)

    try:
        findings = security.scan_dependency_file(file_path)
    except (ValueError, security.OSVUnavailable) as exc:
        print_error(str(exc))
        raise typer.Exit(1)

    if not findings:
        console.print("No dependencies found to check.")
        return

    vulnerable = [f for f in findings if f.vulnerable]
    print_section(f"Dependency scan: {len(findings)} package(s) checked")
    if not vulnerable:
        print_ok("No known vulnerabilities found.")
        return

    print_warn(f"{len(vulnerable)} package(s) with known vulnerabilities:")
    for finding in vulnerable:
        console.print(f"    {finding.name}=={finding.version}: {', '.join(finding.vuln_ids)}", markup=False)


if __name__ == "__main__":
    app()
