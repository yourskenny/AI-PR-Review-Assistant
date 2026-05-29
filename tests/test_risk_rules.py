from ai_pr_review.models import PRContext, PRFile, PullRequestRef, Severity
from ai_pr_review.risk_rules import scan_risks


def test_scan_risks_detects_dynamic_execution() -> None:
    context = PRContext(
        ref=PullRequestRef("owner", "repo", 1),
        title="demo",
        body="",
        author="dev",
        html_url="https://github.com/owner/repo/pull/1",
        files=[
            PRFile(
                filename="app.py",
                status="modified",
                additions=1,
                deletions=0,
                patch="@@ -0,0 +1,1 @@\n+eval(user_input)\n",
            )
        ],
    )

    findings = scan_risks(context)

    assert any(finding.severity == Severity.HIGH for finding in findings)
    assert any(finding.category == "security" for finding in findings)
    assert any(finding.line_start == 1 for finding in findings)
    assert any(finding.rule_id == "security.dynamic_code_execution" for finding in findings)
    assert all(finding.recommendation for finding in findings)
    assert all(finding.source == "rule" for finding in findings)


def test_scan_risks_adds_testing_gap_for_source_only_change() -> None:
    context = PRContext(
        ref=PullRequestRef("owner", "repo", 1),
        title="demo",
        body="",
        author="dev",
        html_url="https://github.com/owner/repo/pull/1",
        files=[
            PRFile(
                filename="src/service.py",
                status="modified",
                additions=1,
                deletions=0,
                patch="@@\n+return value\n",
            )
        ],
    )

    findings = scan_risks(context)

    assert any(finding.category == "testing" for finding in findings)


def test_scan_risks_detects_unsafe_yaml_load() -> None:
    context = _context_with_file(
        filename="loader.py",
        patch="@@ -1,1 +1,1 @@\n+yaml.load(payload)\n",
    )

    findings = scan_risks(context)

    assert any(finding.rule_id == "security.unsafe_deserialization" for finding in findings)


def test_scan_risks_detects_requests_without_timeout() -> None:
    context = _context_with_file(
        filename="client.py",
        patch='@@ -1,1 +1,1 @@\n+requests.get("https://example.com")\n',
    )

    findings = scan_risks(context)

    assert any(finding.rule_id == "reliability.request_without_timeout" for finding in findings)


def test_scan_risks_detects_high_risk_path_without_tests() -> None:
    context = _context_with_file(
        filename="src/auth/session.py",
        patch="@@ -1,1 +1,1 @@\n+return refresh_token(user)\n",
    )

    findings = scan_risks(context)

    assert any(finding.rule_id == "testing.high_risk_path_without_tests" for finding in findings)


def test_scan_risks_detects_large_pr_maintainability_risk() -> None:
    context = PRContext(
        ref=PullRequestRef("owner", "repo", 1),
        title="large change",
        body="",
        author="dev",
        html_url="https://github.com/owner/repo/pull/1",
        files=[
            PRFile(
                filename=f"src/file_{index}.py",
                status="modified",
                additions=20,
                deletions=10,
                patch="@@ -1,1 +1,1 @@\n+value = 1\n",
            )
            for index in range(26)
        ],
    )

    findings = scan_risks(context)

    assert any(finding.rule_id == "maintainability.large_pr" for finding in findings)


def test_every_risk_finding_has_required_metadata() -> None:
    context = _context_with_file(
        filename="src/auth/config.py",
        patch='@@ -1,1 +1,2 @@\n+DEBUG = True\n+API_KEY = "secret"\n',
    )

    findings = scan_risks(context)

    assert findings
    assert all(finding.rule_id for finding in findings)
    assert all(finding.confidence for finding in findings)
    assert all(finding.recommendation for finding in findings)
    assert all(finding.source for finding in findings)


def test_scan_risks_respects_enabled_rules_and_min_severity() -> None:
    context = _context_with_file(
        filename="src/app.py",
        patch="@@ -1,1 +1,3 @@\n+eval(user)\n+time.sleep(1)\n+value = 1\n",
    )

    findings = scan_risks(
        context,
        enabled_rules=["reliability.fixed_sleep", "testing.source_without_tests"],
        min_severity=Severity.MEDIUM,
    )

    assert {finding.rule_id for finding in findings} == {"testing.source_without_tests"}


def _context_with_file(filename: str, patch: str) -> PRContext:
    return PRContext(
        ref=PullRequestRef("owner", "repo", 1),
        title="demo",
        body="",
        author="dev",
        html_url="https://github.com/owner/repo/pull/1",
        files=[
            PRFile(
                filename=filename,
                status="modified",
                additions=1,
                deletions=0,
                patch=patch,
            )
        ],
    )
