"""Per-project opt-in registry for the automated (daemon-driven) commit layer. Presence in
the table means enabled; disabling simply removes the row. Projects are identified by their
absolute path, matching how project_tracker reports them."""

from pathlib import Path

from doctor_raven.core.db import get_conn


def enable(project_path: Path) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO auto_commit_projects (project_path) VALUES (?)", (str(project_path),)
        )


def disable(project_path: Path) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM auto_commit_projects WHERE project_path = ?", (str(project_path),))
        return cur.rowcount > 0


def is_enabled(project_path: Path) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM auto_commit_projects WHERE project_path = ?", (str(project_path),)
        ).fetchone()
        return row is not None


def list_enabled() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT project_path FROM auto_commit_projects ORDER BY project_path").fetchall()
        return [row["project_path"] for row in rows]
