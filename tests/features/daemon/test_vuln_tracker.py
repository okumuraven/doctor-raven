from doctor_raven.features.daemon import vuln_tracker
from doctor_raven.features.security.cve import DependencyFinding


def test_filter_new_vulnerabilities_returns_all_on_first_sight(isolated_db):
    finding = DependencyFinding(ecosystem="PyPI", name="requests", version="2.6.0", vuln_ids=["CVE-1", "CVE-2"])

    new_pairs = vuln_tracker.filter_new_vulnerabilities("proj", [finding])

    assert {vuln_id for _, vuln_id in new_pairs} == {"CVE-1", "CVE-2"}


def test_record_seen_then_filter_excludes_previously_seen(isolated_db):
    finding = DependencyFinding(ecosystem="PyPI", name="requests", version="2.6.0", vuln_ids=["CVE-1", "CVE-2"])

    first_pass = vuln_tracker.filter_new_vulnerabilities("proj", [finding])
    vuln_tracker.record_seen("proj", first_pass)

    second_pass = vuln_tracker.filter_new_vulnerabilities("proj", [finding])
    assert second_pass == []


def test_new_cve_on_already_known_package_still_surfaces(isolated_db):
    finding_v1 = DependencyFinding(ecosystem="PyPI", name="requests", version="2.6.0", vuln_ids=["CVE-1"])
    vuln_tracker.record_seen("proj", vuln_tracker.filter_new_vulnerabilities("proj", [finding_v1]))

    finding_v1_new_cve = DependencyFinding(ecosystem="PyPI", name="requests", version="2.6.0", vuln_ids=["CVE-1", "CVE-2"])
    second_pass = vuln_tracker.filter_new_vulnerabilities("proj", [finding_v1_new_cve])

    assert {vuln_id for _, vuln_id in second_pass} == {"CVE-2"}


def test_same_cve_in_different_projects_are_tracked_independently(isolated_db):
    finding = DependencyFinding(ecosystem="PyPI", name="requests", version="2.6.0", vuln_ids=["CVE-1"])
    vuln_tracker.record_seen("project-a", vuln_tracker.filter_new_vulnerabilities("project-a", [finding]))

    new_pairs = vuln_tracker.filter_new_vulnerabilities("project-b", [finding])
    assert len(new_pairs) == 1
