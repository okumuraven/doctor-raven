from pathlib import Path

from doctor_raven.features.research.brainstorm import (
    _flag_unverified_cves,
    _format_kev,
    _format_projects,
    _format_stories,
)
from doctor_raven.features.research.cyber_feed import KevEntry
from doctor_raven.features.research.project_tracker import ProjectActivity
from doctor_raven.features.research.tech_feed import TechStory


def test_flag_unverified_cves_passes_through_when_real():
    real = [KevEntry(cve_id="CVE-2026-1111", vendor="Acme", product="Widget", name="RCE", date_added="2026-08-14")]
    text = "Watch CVE-2026-1111 closely."
    assert _flag_unverified_cves(text, real) == text


def test_flag_unverified_cves_flags_fabricated_id():
    result = _flag_unverified_cves("Watch CVE-2026-9999, which is critical.", [])
    assert "WARNING" in result
    assert "CVE-2026-9999" in result


def test_flag_unverified_cves_is_case_insensitive():
    real = [KevEntry(cve_id="cve-2026-1111", vendor="Acme", product="Widget", name="RCE", date_added="2026-08-14")]
    text = "See CVE-2026-1111."
    assert _flag_unverified_cves(text, real) == text


def test_flag_unverified_cves_no_mentions_is_untouched():
    assert _flag_unverified_cves("Nothing to see here.", []) == "Nothing to see here."


def test_format_projects_empty_says_so():
    assert "no recent git activity" in _format_projects([])


def test_format_projects_includes_branch_and_message():
    project = ProjectActivity(
        name="doctor-raven", path=Path("/x"), last_commit_at="2026-08-15T00:00:00", last_commit_message="fix bug", branch="main"
    )
    formatted = _format_projects([project])
    assert "doctor-raven" in formatted
    assert "fix bug" in formatted
    assert "main" in formatted


def test_format_stories_empty_says_so():
    assert "none fetched" in _format_stories([])


def test_format_stories_includes_title():
    story = TechStory(title="New CLI framework", url=None, points=42, created_at="2026-08-14T00:00:00Z")
    assert "New CLI framework" in _format_stories([story])


def test_format_kev_empty_says_so():
    assert "none added recently" in _format_kev([])


def test_format_kev_includes_cve_id():
    entry = KevEntry(cve_id="CVE-2026-1111", vendor="Acme", product="Widget", name="RCE", date_added="2026-08-14")
    assert "CVE-2026-1111" in _format_kev([entry])
