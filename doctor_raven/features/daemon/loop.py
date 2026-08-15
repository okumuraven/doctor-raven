"""Persistent background loop: fires reminders near-real-time, notifies on system-health
transitions, and periodically scans tracked projects' dependency files for newly-appeared CVEs."""

import os
import threading
import time

from doctor_raven.config import Config
from doctor_raven.features import notifications, reminders, security, system_health
from doctor_raven.features.daemon import pidlock, vuln_tracker
from doctor_raven.features.research.project_tracker import list_recent_projects
from doctor_raven.util.formatting import console, print_section

DEPENDENCY_FILENAMES = ("requirements.txt", "package-lock.json")


def _check_reminders(config: Config) -> None:
    for reminder in reminders.list_due():
        notifications.notify_and_log("Doctor Raven reminder", reminder.message, source="reminder", config=config)
        reminders.mark_fired(reminder.id)


def _check_system_health(config: Config, last_level: str | None) -> str:
    status = system_health.read_status()
    decision = system_health.evaluate(status, config)

    if decision.level != last_level:
        if decision.level != "normal":
            diagnosis = system_health.diagnose(status)
            notifications.notify_and_log(
                f"Doctor Raven — system now {decision.level}",
                f"{decision.reason}. {diagnosis.recommendation}",
                source="system_health",
                config=config,
            )
        elif last_level is not None:
            notifications.notify_and_log(
                "Doctor Raven — system back to normal", decision.reason, source="system_health", config=config
            )

    return decision.level


def _scan_project_dependencies(config: Config) -> None:
    for project in list_recent_projects(config.workspace_root, limit=50):
        for filename in DEPENDENCY_FILENAMES:
            dep_file = project.path / filename
            if not dep_file.exists():
                continue
            try:
                findings = security.scan_dependency_file(dep_file)
            except (ValueError, security.OSVUnavailable):
                continue

            vulnerable = [f for f in findings if f.vulnerable]
            new_pairs = vuln_tracker.filter_new_vulnerabilities(project.name, vulnerable)
            if new_pairs:
                summary = "; ".join(f"{finding.name}=={finding.version} ({vuln_id})" for finding, vuln_id in new_pairs)
                notifications.notify_and_log(
                    f"Doctor Raven — new CVE(s) in {project.name}", summary, source="dependency_watch", config=config
                )
                vuln_tracker.record_seen(project.name, new_pairs)


def run_daemon(config: Config) -> None:
    """Reminders and system health are checked on every tick and must never be delayed by the
    dependency/CVE scan — that scan does real git + OSV.dev network I/O across every tracked
    project and can easily take longer than one tick, so it always runs in a background thread,
    never inline in the loop. scan_lock skips a trigger if the previous scan is still running,
    rather than piling up overlapping scans."""
    pidlock.acquire()
    console.print(f"Doctor Raven daemon started (pid {os.getpid()}).")
    print_section("Watching")
    console.print(f"  Reminders: every {config.daemon_tick_seconds:.0f}s")
    console.print(f"  System health: every {config.daemon_tick_seconds:.0f}s (on transition only)")
    console.print(f"  Dependency/CVE scan: every {config.daemon_dependency_scan_interval_hours:.1f}h (background thread)")

    last_health_level: str | None = None
    dependency_scan_interval = config.daemon_dependency_scan_interval_hours * 3600
    scan_lock = threading.Lock()

    def _start_scan_thread() -> None:
        def _worker() -> None:
            try:
                _scan_project_dependencies(config)
            finally:
                scan_lock.release()

        threading.Thread(target=_worker, daemon=True).start()

    try:
        if scan_lock.acquire(blocking=False):
            _start_scan_thread()
        last_dependency_scan = time.monotonic()

        while True:
            time.sleep(config.daemon_tick_seconds)
            _check_reminders(config)
            last_health_level = _check_system_health(config, last_health_level)

            if time.monotonic() - last_dependency_scan >= dependency_scan_interval:
                last_dependency_scan = time.monotonic()
                if scan_lock.acquire(blocking=False):
                    _start_scan_thread()
                # else: previous scan still running — skip this cycle's trigger
    except KeyboardInterrupt:
        console.print("\nStopping daemon.")
    finally:
        pidlock.release()
