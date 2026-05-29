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
