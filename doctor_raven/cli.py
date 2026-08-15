"""Doctor Raven CLI entry point. Wires Typer subcommands to the feature modules."""

import subprocess
from pathlib import Path

import typer

from doctor_raven.config import load_config
from doctor_raven.core import llm_router
from doctor_raven.features import briefing, firewall, git_ops, launcher, maintenance, reminders, research, schedule, security, system_health, voice
from doctor_raven.features import daemon as daemon_feature
from doctor_raven.util.formatting import console, print_error, print_ok, print_section, print_warn

app = typer.Typer(help="Doctor Raven — a local-first intelligent assistant for daily engineering/security work.")
task_app = typer.Typer(help="Manage tasks")
remind_app = typer.Typer(help="Manage reminders")
research_app = typer.Typer(help="Manage research topics")
sec_app = typer.Typer(help="Security posture checks and CVE lookups")
git_app = typer.Typer(help="Git convenience commands with a hard secrets gate — never force-pushes")
git_auto_app = typer.Typer(help="Per-project opt-in for the daemon's automatic local-commit sweep")
fw_app = typer.Typer(help="Manage the local firewall (ufw-backed). Every rule change is previewed and confirmed before it runs.")
open_app = typer.Typer(help="Open apps/folders directly — no LLM involved, instant and unambiguous")
app.add_typer(task_app, name="task")
app.add_typer(remind_app, name="remind")
app.add_typer(research_app, name="research")
app.add_typer(sec_app, name="sec")
app.add_typer(git_app, name="git")
app.add_typer(fw_app, name="fw")
app.add_typer(open_app, name="open")
git_app.add_typer(git_auto_app, name="auto")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        config = load_config()
        briefing.print_banner(config)
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command()
def morning(force: bool = typer.Option(False, "--force", help="Rerun even if already run today")) -> None:
    """Run the daily morning briefing: schedule, reminders, brainstorm, maintenance status."""
    config = load_config()
    briefing.run_morning_briefing(config, force=force)


@app.command()
def status() -> None:
    """One-shot status snapshot: system health, tasks, reminders, upgrades, recent notifications."""
    config = load_config()
    briefing.run_status(config)


@app.command()
def daemon() -> None:
    """Persistent background watcher: near-real-time reminders, system-health transitions, and
    periodic dependency/CVE scanning across the workspace. Ctrl+C to exit."""
    config = load_config()
    try:
        daemon_feature.run_daemon(config)
    except daemon_feature.DaemonAlreadyRunning as exc:
        print_error(str(exc))
        raise typer.Exit(1)


@app.command()
def dashboard(
    refresh_seconds: float = typer.Option(3.0, "--refresh", help="Seconds between refreshes"),
) -> None:
    """Live-updating status panel. Suppresses redundant notify-send popups while open. Ctrl+C to exit."""
    config = load_config()
    briefing.run_dashboard(config, refresh_seconds=refresh_seconds)


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


@research_app.command("digest")
def research_digest(
    deep: bool = typer.Option(False, "--deep", help="Use the Claude API instead of the local model"),
) -> None:
    """Project activity + trending tech + newly actively-exploited CVEs, synthesized by the LLM."""
    config = load_config()
    if not _guard_or_confirm(config, "the research digest"):
        console.print("Skipped.")
        raise typer.Exit(0)

    digest = research.daily_digest(config, research.list_topics(), deep=deep)

    print_section("Recent project activity")
    if not digest.project_context:
        console.print("  No recent git activity detected in the workspace.")
    for project in digest.project_context:
        console.print(f'  {project.name} ({project.branch}): "{project.last_commit_message}" at {project.last_commit_at}', markup=False)

    print_section("Trending tech")
    if not digest.tech_stories:
        console.print("  (none fetched)")
    for story in digest.tech_stories:
        console.print(f"  {story.points:>4} pts  {story.title}", markup=False)

    print_section("Newly exploited CVEs (CISA KEV)")
    if not digest.kev_entries:
        console.print("  (none added recently)")
    for entry in digest.kev_entries:
        console.print(f"  {entry.cve_id}: {entry.name} ({entry.vendor} {entry.product}), added {entry.date_added}", markup=False)

    print_section("Synthesis")
    console.print("  " + digest.synthesis.replace("\n", "\n  "), markup=False)

    if digest.topic_brainstorms:
        print_section("Saved topics")
        for name, text in digest.topic_brainstorms.items():
            console.print(f"  [bold]{name}[/bold]:", markup=True)
            console.print("    " + text.replace("\n", "\n    "), markup=False)


def _guard_or_confirm(config, task_label: str) -> bool:
    """Warns + diagnoses the cause before a CPU-heavy task, then lets the caller decide."""
    status = system_health.read_status()
    decision = system_health.evaluate(status, config)
    if decision.level == "normal":
        return True

    diagnosis = system_health.diagnose(status)
    printer = print_warn if decision.level == "hot" else print_error
    printer(f"System is {decision.level}: {decision.reason}")
    for proc in diagnosis.top_processes[:3]:
        console.print(f"    {proc.cpu_percent:5.1f}%  {proc.name} (pid {proc.pid})", markup=False)
    console.print(f"  {diagnosis.recommendation}", markup=False)
    return typer.confirm(f"Proceed with {task_label} anyway?")


@app.command()
def health() -> None:
    """Show current CPU temperature/load and, if elevated, what's actually driving it."""
    config = load_config()
    status = system_health.read_status()
    decision = system_health.evaluate(status, config)

    temp_str = f"{status.cpu_temp_c:.0f}°C" if status.cpu_temp_c is not None else "unavailable"
    console.print(
        f"CPU temp: {temp_str}  |  load: {status.load_1m:.2f} "
        f"({status.load_per_core:.2f}/core, {status.core_count} cores)",
        markup=False,
    )

    if decision.level == "normal":
        print_ok(f"System status normal ({decision.reason})")
        return

    printer = print_warn if decision.level == "hot" else print_error
    printer(f"System status {decision.level}: {decision.reason}")

    diagnosis = system_health.diagnose(status)
    console.print("  Top processes:", markup=False)
    for proc in diagnosis.top_processes:
        console.print(f"    {proc.cpu_percent:5.1f}%  {proc.name} (pid {proc.pid})", markup=False)
    console.print(f"  Recommendation: {diagnosis.recommendation}", markup=False)


@app.command()
def ask(
    question: str,
    deep: bool = typer.Option(False, "--deep", help="Use the Claude API instead of the local model"),
) -> None:
    config = load_config()
    if not deep and not _guard_or_confirm(config, "this local model request"):
        console.print("Skipped.")
        raise typer.Exit(0)
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
    config = load_config()
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

    if scan and not _guard_or_confirm(config, "the security scan"):
        console.print("Skipped security scan.")
        scan = False

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


def _print_findings(findings) -> None:
    for finding in findings:
        loc = f"{finding.file}:{finding.line}" if finding.line else finding.file
        console.print(f"    {loc} — {finding.kind}: {finding.preview}", markup=False)


@git_app.command("commit")
def git_commit(
    message: str = typer.Option(None, "-m", "--message", help="Commit message (skips AI drafting)"),
) -> None:
    """Stages everything, hard-blocks on anything secret-shaped, drafts a message via the local
    LLM if you don't supply one, then commits. Never touches files it can't see are already there."""
    config = load_config()

    if git_ops.is_detached_head():
        print_warn("You're in detached HEAD — this commit won't be reachable from any branch unless you create one for it.")
        if not typer.confirm("Commit anyway?"):
            console.print("Commit cancelled.")
            raise typer.Exit(1)

    if not git_ops.has_changes():
        console.print("Nothing to commit.")
        return

    git_ops.stage_all()
    files = git_ops.staged_files()
    print_section("Staged")
    for f in files:
        console.print(f"  {f}", markup=False)

    findings = git_ops.scan_staged()
    if findings:
        print_error(f"{len(findings)} potential secret(s) found:")
        _print_findings(findings)
        if not typer.confirm("Commit anyway despite the above?"):
            console.print("Nothing committed. Files remain staged — fix the issue and rerun, or `git reset` to unstage.")
            raise typer.Exit(1)

    commit_message = message
    if not commit_message:
        drafted = git_ops.draft_commit_message(config)
        if drafted:
            console.print(f"\nDrafted commit message:\n  {drafted}\n", markup=False)
            if typer.confirm("Use this message?"):
                commit_message = drafted
        if not commit_message:
            commit_message = typer.prompt("Commit message")

    result = git_ops.commit(commit_message)
    if result.returncode == 0:
        print_ok(f"Committed: {commit_message.splitlines()[0]}")
    else:
        print_error(result.stderr.strip() or "git commit failed")
        raise typer.Exit(1)


@git_app.command("push")
def git_push() -> None:
    """Scans outgoing commits for secrets (hard-blocks by default), warns on main/master, then
    pushes. Never passes --force — full stop."""
    branch = git_ops.current_branch()
    if branch in ("main", "master"):
        print_warn(f"You're pushing directly to '{branch}'.")

    findings, scope_note = git_ops.scan_outgoing()
    console.print(f"Scanned: {scope_note}", markup=False)
    if findings:
        print_error(f"{len(findings)} potential secret(s) found in outgoing commits:")
        _print_findings(findings)
        if not typer.confirm("Push anyway despite the above?"):
            console.print("Push cancelled.")
            raise typer.Exit(1)

    if git_ops.has_upstream():
        result = git_ops.push()
    else:
        if not typer.confirm(f"No upstream set for '{branch}'. Push and set 'origin/{branch}' as upstream?"):
            console.print("Push cancelled.")
            raise typer.Exit(1)
        result = git_ops.push_set_upstream(branch)

    if result.returncode == 0:
        print_ok("Pushed.")
    else:
        print_error(result.stderr.strip() or "git push failed")
        raise typer.Exit(1)


def _repo_root_or_exit() -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if result.returncode != 0:
        print_error("Not inside a git repository.")
        raise typer.Exit(1)
    return Path(result.stdout.strip()).resolve()


@git_auto_app.command("enable")
def git_auto_enable() -> None:
    """Opt this project into the daemon's auto-commit sweep: idle uncommitted changes get
    committed locally with an AI-drafted message, gated by the same secrets scanner. Pushing
    is never automatic — that's always `raven git push`, on your call."""
    project_path = _repo_root_or_exit()
    git_ops.enable(project_path)
    print_ok(f"Watching over '{project_path.name}' now.")
    console.print(
        "  Once things go quiet here, I'll tidy up and commit locally — you'll still push when you're ready.",
        markup=False,
    )


@git_auto_app.command("disable")
def git_auto_disable() -> None:
    """Opt this project back out of the auto-commit sweep."""
    project_path = _repo_root_or_exit()
    if git_ops.disable(project_path):
        print_ok(f"Stepping back from '{project_path.name}' — you've got the wheel.")
    else:
        console.print(f"'{project_path.name}' wasn't on my watch list.")


@git_auto_app.command("list")
def git_auto_list() -> None:
    """Show every project currently opted into the auto-commit sweep."""
    enabled = git_ops.list_enabled()
    if not enabled:
        console.print("Nothing on my watch list yet. Run `raven git auto enable` from inside a project.")
        return
    print_section("Watching")
    for path in enabled:
        console.print(f"  {Path(path).name}  ({path})", markup=False)


@git_app.command("switch")
def git_switch(
    branch: str,
    create: bool = typer.Option(False, "--create", "-c", help="Create the branch if it doesn't exist"),
) -> None:
    """Switch branches safely: flags detached HEAD before you leave it behind, warns about
    unpushed commits on the branch you're leaving, and offers to stash uncommitted changes
    instead of losing track of them."""
    if git_ops.is_detached_head():
        print_warn("You're in detached HEAD. Any commits made here become unreachable once you switch away.")
        if typer.confirm("Create a branch here first to save this work?"):
            name = typer.prompt("Branch name")
            result = git_ops.create_branch(name)
            if result.returncode != 0:
                print_error(result.stderr.strip() or "Could not create branch")
                raise typer.Exit(1)
            print_ok(f"Created '{name}' at this commit.")
    else:
        current = git_ops.current_branch()
        unpushed = git_ops.unpushed_commit_count()
        if unpushed:
            print_warn(f"'{current}' has {unpushed} unpushed commit(s) — don't forget to push before you're done here.")

        if git_ops.has_changes():
            print_warn("You have uncommitted changes.")
            if typer.confirm("Stash them before switching?"):
                stash_result = git_ops.stash_push(f"auto-stash before switching to {branch}")
                if stash_result.returncode != 0:
                    print_error(stash_result.stderr.strip() or "Stash failed")
                    raise typer.Exit(1)
                print_ok("Stashed.")
            elif not typer.confirm("Switch anyway?"):
                console.print("Switch cancelled.")
                raise typer.Exit(1)

    if create and not git_ops.branch_exists(branch):
        result = git_ops.create_branch(branch)
    else:
        result = git_ops.switch_branch(branch)
        if result.returncode != 0 and not git_ops.branch_exists(branch):
            remote_result = git_ops.checkout_remote_tracking(branch)
            if remote_result.returncode == 0:
                print_ok(f"No local branch '{branch}' — checked out and tracking 'origin/{branch}'.")
                return
            result = remote_result

    if result.returncode == 0:
        print_ok(f"Switched to '{branch}'.")
    else:
        print_error(result.stderr.strip() or "git checkout failed")
        raise typer.Exit(1)


@git_app.command("branch")
def git_branch_new(name: str) -> None:
    """Create a new branch from HEAD and switch to it, with a name-collision check."""
    if git_ops.branch_exists(name):
        print_error(f"Branch '{name}' already exists.")
        raise typer.Exit(1)
    result = git_ops.create_branch(name)
    if result.returncode == 0:
        print_ok(f"Created and switched to '{name}'.")
    else:
        print_error(result.stderr.strip() or "git checkout -b failed")
        raise typer.Exit(1)


@git_app.command("stash")
def git_stash(message: str = typer.Option(None, "-m", "--message", help="Optional stash message")) -> None:
    """Stash uncommitted changes as a quick checkpoint you can restore with `raven git stash-pop`."""
    if not git_ops.has_changes():
        console.print("Nothing to stash.")
        return
    result = git_ops.stash_push(message)
    if result.returncode == 0:
        print_ok("Stashed.")
    else:
        print_error(result.stderr.strip() or "git stash failed")
        raise typer.Exit(1)


@git_app.command("stash-pop")
def git_stash_pop() -> None:
    """Restore the most recently stashed changes."""
    if not git_ops.stash_list():
        console.print("No stash to pop.")
        return
    result = git_ops.stash_pop()
    if result.returncode == 0:
        print_ok("Restored.")
    else:
        print_error(result.stderr.strip() or "git stash pop failed (check `git status` — likely a conflict)")
        raise typer.Exit(1)


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


def _apply_previewed_change(change) -> None:
    """Every fw mutation goes through here: show exactly what will run, and — if the change
    carries a lockout risk (SSH deny, enabling ufw with SSH not yet allowed) — require typing
    'confirm' rather than a plain y/N, so a reflexive yes can't strand a remote session."""
    console.print(change.description, markup=False)
    if change.warning:
        print_warn(change.warning)
        typed = typer.prompt("Type 'confirm' to proceed anyway, or anything else to cancel")
        if typed.strip().lower() != "confirm":
            console.print("Cancelled.")
            raise typer.Exit(0)
    elif not typer.confirm("Proceed?"):
        console.print("Cancelled.")
        raise typer.Exit(0)

    result = change.apply()
    if result.returncode == 0:
        print_ok("Done.")
    else:
        print_error((result.stderr or result.stdout or "ufw command failed").strip())
        raise typer.Exit(1)


@fw_app.command("status")
def fw_status() -> None:
    """Read-only: list current firewall rules and whether ufw is active. Requires sudo since
    ufw needs root to read live rules — you'll be prompted for your password if needed."""
    try:
        current = firewall.status()
    except firewall.UFWUnavailable as exc:
        print_error(str(exc))
        raise typer.Exit(1)

    console.print(f"Firewall: {'ACTIVE' if current.active else 'INACTIVE'}", markup=False)
    if not current.rules:
        console.print("  No rules configured.")
        return
    for rule in current.rules:
        console.print(f"  [{rule.number}] {rule.port}  {rule.action} {rule.direction.upper()}  from {rule.source}", markup=False)


@fw_app.command("allow")
def fw_allow(
    port: int,
    proto: str = typer.Option("tcp", "--proto", help="tcp or udp"),
    source: str = typer.Option(None, "--from", help="Restrict to this source IP/CIDR"),
) -> None:
    """Open a port. Always previews the exact ufw command and asks for confirmation first."""
    try:
        change = firewall.preview_allow(port, proto, source)
    except firewall.InvalidRule as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    _apply_previewed_change(change)


@fw_app.command("deny")
def fw_deny(
    port: int,
    proto: str = typer.Option("tcp", "--proto", help="tcp or udp"),
    source: str = typer.Option(None, "--from", help="Restrict to this source IP/CIDR"),
) -> None:
    """Block a port. Always previews the exact ufw command and asks for confirmation first."""
    try:
        change = firewall.preview_deny(port, proto, source)
    except firewall.InvalidRule as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    _apply_previewed_change(change)


@fw_app.command("delete")
def fw_delete(rule_number: int) -> None:
    """Remove a specific rule by the number shown in `raven fw status`."""
    _apply_previewed_change(firewall.preview_delete(rule_number))


@fw_app.command("enable")
def fw_enable() -> None:
    """Turn the firewall on. Warns loudly (and requires typing 'confirm') if SSH isn't allowed yet."""
    try:
        change = firewall.preview_enable()
    except firewall.UFWUnavailable as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    _apply_previewed_change(change)


@fw_app.command("disable")
def fw_disable() -> None:
    """Turn the firewall off entirely — drops all filtering, not just one rule."""
    _apply_previewed_change(firewall.preview_disable())


@open_app.command("code")
def open_code(path: str = typer.Argument(None, help="Folder to open (defaults to current directory)")) -> None:
    """Open VS Code at a folder."""
    try:
        print_ok(launcher.open_vscode(path))
    except launcher.SkillError as exc:
        print_error(str(exc))
        raise typer.Exit(1)


@open_app.command("terminal")
def open_terminal_cmd(path: str = typer.Argument(None, help="Directory to open the terminal in")) -> None:
    """Open a terminal (respects `[launcher] terminal_command` in config.toml, or auto-detects)."""
    config = load_config()
    try:
        print_ok(launcher.open_terminal(path, config.terminal_command))
    except launcher.SkillError as exc:
        print_error(str(exc))
        raise typer.Exit(1)


@open_app.command("browser")
def open_browser_cmd(url: str) -> None:
    """Open the browser to a URL."""
    try:
        print_ok(launcher.open_browser(url))
    except launcher.SkillError as exc:
        print_error(str(exc))
        raise typer.Exit(1)


@app.command()
def search(query: str) -> None:
    """Web search — opens the results in your browser."""
    config = load_config()
    try:
        print_ok(launcher.web_search(query, config))
    except launcher.SkillError as exc:
        print_error(str(exc))
        raise typer.Exit(1)


def _review_and_send_email(drafted) -> None:
    print_section("Drafted email")
    console.print(f"  To: {drafted.to}", markup=False)
    console.print(f"  Subject: {drafted.subject}", markup=False)
    console.print(f"\n{drafted.body}\n", markup=False)
    if not typer.confirm("Open this in your mail client to send?"):
        console.print("Discarded — nothing sent, nothing opened.")
        return
    if launcher.open_in_mail_client(drafted):
        print_ok("Opened in your mail client. Hit send there when you're ready.")
    else:
        print_warn("Couldn't open a mail client automatically — here's the draft to copy:")
        console.print(f"\nTo: {drafted.to}\nSubject: {drafted.subject}\n\n{drafted.body}\n", markup=False)


@app.command()
def email(to: str, about: str) -> None:
    """Draft an email via the local LLM and review it before it goes anywhere. Doctor Raven
    never sends mail itself — this only hands a reviewed draft to your own mail client."""
    config = load_config()
    if not _guard_or_confirm(config, "drafting this email"):
        console.print("Skipped.")
        raise typer.Exit(0)
    drafted = launcher.draft(to, about, config)
    _review_and_send_email(drafted)


@app.command()
def do(request: str) -> None:
    """Natural-language entry point: tell Doctor Raven what to do in plain English and it
    routes to one of a fixed set of known actions (open VS Code/terminal/browser, web search,
    draft an email) — never a freeform decision. Says so plainly if nothing confidently matches."""
    config = load_config()
    if not _guard_or_confirm(config, "interpreting this request"):
        console.print("Skipped.")
        raise typer.Exit(0)

    classified = launcher.interpret(request, config)
    if not classified:
        print_warn(
            "Couldn't confidently match that to something I know how to do. "
            "Try: open vscode, open terminal, open browser, search, or email."
        )
        raise typer.Exit(1)

    try:
        result = launcher.dispatch(classified["skill"], classified["params"], config)
    except launcher.SkillError as exc:
        print_error(str(exc))
        raise typer.Exit(1)

    if result.email_draft:
        _review_and_send_email(result.email_draft)
    else:
        print_ok(result.message)


def _speak_safely(text: str, config) -> None:
    try:
        voice.speak(text, config)
    except voice.SpeechError as exc:
        print_warn(f"Couldn't speak the response: {exc}")


@app.command()
def listen() -> None:
    """Push-to-talk: Enter to start speaking, Enter again to stop. Transcribes locally with
    faster-whisper, routes through the same fixed-skill dispatcher as `raven do`, and speaks
    the result back via Piper (toggle with `[voice] speak_responses` in config.toml)."""
    config = load_config()
    if not _guard_or_confirm(config, "listening and transcribing"):
        console.print("Skipped.")
        raise typer.Exit(0)

    console.print("Press Enter to start speaking...")
    input()
    try:
        recording = voice.start(config.voice_max_recording_seconds)
    except voice.RecorderError as exc:
        print_error(str(exc))
        raise typer.Exit(1)

    console.print(f"Listening (up to {config.voice_max_recording_seconds:.0f}s) — press Enter when done.")
    input()
    try:
        wav_path = voice.stop(recording)
    except voice.RecorderError as exc:
        print_error(str(exc))
        raise typer.Exit(1)

    try:
        text = voice.transcribe(wav_path, config)
    except voice.TranscriptionError as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    finally:
        wav_path.unlink(missing_ok=True)

    if not text:
        print_warn("Didn't catch anything.")
        raise typer.Exit(1)

    console.print(f'You said: "{text}"', markup=False)

    classified = launcher.interpret(text, config)
    if not classified:
        message = "Couldn't confidently match that to something I know how to do."
        print_warn(message)
        if config.voice_speak_responses:
            _speak_safely(message, config)
        raise typer.Exit(1)

    try:
        result = launcher.dispatch(classified["skill"], classified["params"], config)
    except launcher.SkillError as exc:
        print_error(str(exc))
        if config.voice_speak_responses:
            _speak_safely(str(exc), config)
        raise typer.Exit(1)

    if result.email_draft:
        _review_and_send_email(result.email_draft)
        spoken = "Drafted an email for your review."
    else:
        print_ok(result.message)
        spoken = result.message

    if config.voice_speak_responses:
        _speak_safely(spoken, config)


if __name__ == "__main__":
    app()
