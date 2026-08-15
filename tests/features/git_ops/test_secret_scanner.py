from doctor_raven.features.git_ops import secret_scanner


def test_scan_diff_flags_private_key_header():
    diff = (
        "diff --git a/id_rsa b/id_rsa\n"
        "--- /dev/null\n"
        "+++ b/id_rsa\n"
        "@@ -0,0 +1,2 @@\n"
        "+-----BEGIN RSA PRIVATE KEY-----\n"
        "+MIIEpAIBAAKCAQEA1234567890abcdef\n"
    )
    findings = secret_scanner.scan_diff(diff)
    assert any(f.kind == "private key header" for f in findings)


def test_scan_diff_flags_aws_access_key():
    diff = "+++ b/config.py\n@@ -0,0 +1 @@\n+AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n"
    findings = secret_scanner.scan_diff(diff)
    assert any(f.kind == "AWS access key" for f in findings)


def test_scan_diff_flags_generic_secret_assignment():
    diff = "+++ b/settings.py\n@@ -0,0 +1 @@\n+api_key = \"sk-1234567890abcdef\"\n"
    findings = secret_scanner.scan_diff(diff)
    assert any(f.kind == "generic secret assignment" for f in findings)


def test_scan_diff_ignores_removed_lines():
    diff = "+++ b/config.py\n@@ -1,1 +0,0 @@\n-AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n"
    assert secret_scanner.scan_diff(diff) == []


def test_scan_diff_clean_code_produces_no_findings():
    diff = "+++ b/app.py\n@@ -0,0 +1,2 @@\n+def add(a, b):\n+    return a + b\n"
    assert secret_scanner.scan_diff(diff) == []


def test_scan_diff_never_prints_full_secret():
    diff = "+++ b/settings.py\n@@ -0,0 +1 @@\n+token = \"ghp_1234567890abcdefghijklmnopqrstuvwxyz\"\n"
    findings = secret_scanner.scan_diff(diff)
    assert findings
    assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in findings[0].preview


def test_is_sensitive_filename_flags_env_file():
    assert secret_scanner.is_sensitive_filename(".env")
    assert secret_scanner.is_sensitive_filename("config/.env.local")


def test_is_sensitive_filename_allows_env_example():
    assert not secret_scanner.is_sensitive_filename(".env.example")
    assert not secret_scanner.is_sensitive_filename(".env.sample")


def test_is_sensitive_filename_flags_ssh_keys_and_pem():
    assert secret_scanner.is_sensitive_filename("id_rsa")
    assert secret_scanner.is_sensitive_filename("secrets/id_ed25519")
    assert secret_scanner.is_sensitive_filename("certs/server.pem")


def test_is_sensitive_filename_allows_normal_files():
    assert not secret_scanner.is_sensitive_filename("app.py")
    assert not secret_scanner.is_sensitive_filename("README.md")


def test_scan_filenames_only_flags_sensitive_ones():
    findings = secret_scanner.scan_filenames(["app.py", ".env", "README.md"])
    assert [f.file for f in findings] == [".env"]


def test_scan_diff_exempts_content_in_test_files():
    diff = "+++ b/tests/test_secret_scanner.py\n@@ -0,0 +1 @@\n+AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n"
    assert secret_scanner.scan_diff(diff) == []


def test_scan_diff_exempts_content_in_tests_directory_generally():
    diff = "+++ b/tests/features/git_ops/test_repo_ops.py\n@@ -0,0 +1 @@\n+api_key = \"sk-1234567890abcdef\"\n"
    assert secret_scanner.scan_diff(diff) == []


def test_scan_diff_still_flags_content_outside_test_paths():
    diff = "+++ b/app/settings.py\n@@ -0,0 +1 @@\n+AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n"
    findings = secret_scanner.scan_diff(diff)
    assert any(f.kind == "AWS access key" for f in findings)


def test_is_test_path_matches_common_layouts():
    assert secret_scanner.is_test_path("tests/features/git_ops/test_repo_ops.py")
    assert secret_scanner.is_test_path("test_something.py")
    assert secret_scanner.is_test_path("something_test.py")
    assert secret_scanner.is_test_path("__tests__/foo.js")
    assert not secret_scanner.is_test_path("doctor_raven/features/git_ops/repo_ops.py")


def test_sensitive_filename_still_flagged_even_inside_a_test_directory():
    # filename-based checks are cheap/low-noise enough to stay on regardless of path
    assert secret_scanner.is_sensitive_filename("tests/fixtures/.env")
