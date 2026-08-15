from doctor_raven.features.security import cve as cve_module
from doctor_raven.features.security.cve import DependencyFinding, scan_dependency_file


def test_dependency_finding_vulnerable_property():
    clean = DependencyFinding(ecosystem="PyPI", name="requests", version="2.34.2", vuln_ids=[])
    vulnerable = DependencyFinding(ecosystem="PyPI", name="requests", version="2.6.0", vuln_ids=["GHSA-xxxx"])
    assert clean.vulnerable is False
    assert vulnerable.vulnerable is True


def test_scan_dependency_file_batches_and_maps_results(tmp_path, monkeypatch):
    req = tmp_path / "requirements.txt"
    req.write_text("a==1.0\nb==2.0\n")

    def fake_query_batch(packages):
        assert packages == [("PyPI", "a", "1.0"), ("PyPI", "b", "2.0")]
        return [["CVE-1"], []]

    monkeypatch.setattr(cve_module.osv_client, "query_batch", fake_query_batch)

    findings = scan_dependency_file(req)
    assert findings[0].vulnerable is True
    assert findings[0].vuln_ids == ["CVE-1"]
    assert findings[1].vulnerable is False


def test_scan_dependency_file_returns_empty_for_no_deps(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("# nothing here\n")

    assert scan_dependency_file(req) == []
