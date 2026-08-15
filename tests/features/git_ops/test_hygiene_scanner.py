from doctor_raven.features.git_ops import hygiene_scanner


def test_scan_staged_filenames_flags_pycache():
    findings = hygiene_scanner.scan_staged_filenames(["doctor_raven/__pycache__/cli.cpython-313.pyc"])
    assert len(findings) == 1
    assert findings[0].reason == "compiled Python bytecode"


def test_scan_staged_filenames_flags_pyc_extension():
    findings = hygiene_scanner.scan_staged_filenames(["module.pyc"])
    assert findings[0].reason == "compiled Python bytecode"


def test_scan_staged_filenames_flags_egg_info():
    findings = hygiene_scanner.scan_staged_filenames(["doctor_raven.egg-info/PKG-INFO"])
    assert findings[0].reason == "Python packaging metadata"


def test_scan_staged_filenames_flags_node_modules():
    findings = hygiene_scanner.scan_staged_filenames(["frontend/node_modules/lodash/index.js"])
    assert findings[0].reason == "Node.js dependencies"


def test_scan_staged_filenames_flags_ds_store():
    findings = hygiene_scanner.scan_staged_filenames([".DS_Store", "src/.DS_Store"])
    assert len(findings) == 2


def test_scan_staged_filenames_ignores_normal_source_files():
    findings = hygiene_scanner.scan_staged_filenames(["app.py", "README.md", "src/main.js"])
    assert findings == []


def test_scan_staged_filenames_only_flags_matching_files_in_a_mixed_list():
    findings = hygiene_scanner.scan_staged_filenames(["app.py", "doctor_raven/__pycache__/x.pyc", "README.md"])
    assert [f.file for f in findings] == ["doctor_raven/__pycache__/x.pyc"]


def test_gitignore_warning_when_missing(tmp_path):
    assert hygiene_scanner.gitignore_warning(tmp_path) == "No .gitignore found in this repo."


def test_gitignore_warning_when_empty(tmp_path):
    (tmp_path / ".gitignore").write_text("   \n")
    assert hygiene_scanner.gitignore_warning(tmp_path) == ".gitignore exists but is empty."


def test_gitignore_warning_none_when_populated(tmp_path):
    (tmp_path / ".gitignore").write_text("__pycache__/\n")
    assert hygiene_scanner.gitignore_warning(tmp_path) is None
