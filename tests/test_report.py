from ai_pr_review.models import (
    Confidence,
    FindingSource,
    PRContext,
    PRFile,
    PullRequestRef,
    ReviewReport,
    RiskFinding,
    Severity,
)
from ai_pr_review.report import render_markdown


def test_render_markdown_includes_finding_line_number_when_available() -> None:
    context = PRContext(
        ref=PullRequestRef("owner", "repo", 7),
        title="demo",
        body="",
        author="dev",
        html_url="https://github.com/owner/repo/pull/7",
        files=[PRFile("app.py", "modified", 1, 0, "")],
    )
    report = ReviewReport(
        risks=[
            RiskFinding(
                severity=Severity.HIGH,
                category="security",
                file="app.py",
                message="Dynamic code execution appears in the changed lines.",
                evidence="eval(user_input)",
                rule_id="security.dynamic_code_execution",
                confidence=Confidence.HIGH,
                recommendation="Avoid dynamic execution.",
                source=FindingSource.RULE,
                line_start=42,
                line_end=42,
            )
        ]
    )

    markdown = render_markdown(context, report)

    assert "### HIGH security: app.py:42" in markdown
    assert "Rule: `security.dynamic_code_execution`" in markdown
    assert "Confidence: `high`" in markdown
    assert "Recommendation: Avoid dynamic execution." in markdown
