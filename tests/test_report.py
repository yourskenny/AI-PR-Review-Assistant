import json

from ai_pr_review import report as report_module
from ai_pr_review.models import (
    Confidence,
    ContextFile,
    ContextPack,
    FindingSource,
    OmittedContextFile,
    PRContext,
    PRFile,
    PullRequestRef,
    ReviewReport,
    RiskFinding,
    Severity,
)
from ai_pr_review.report import render_markdown


def _context() -> PRContext:
    return PRContext(
        ref=PullRequestRef("owner", "repo", 7),
        title="Add risky helper",
        body="Implements a helper with security-sensitive behavior.",
        author="dev",
        html_url="https://github.com/owner/repo/pull/7",
        files=[
            PRFile("app.py", "modified", 12, 2, "@@ -1,1 +1,2 @@\n+eval(user_input)"),
            PRFile("tests/test_app.py", "modified", 3, 0, "@@ -1,0 +1,1 @@\n+def test_app(): pass"),
            PRFile("docs/usage.md", "modified", 1, 0, "# docs"),
        ],
    )


def _finding(
    *,
    severity: Severity = Severity.HIGH,
    confidence: Confidence = Confidence.HIGH,
    category: str = "security",
    file: str = "app.py",
    line_start: int | None = 42,
    rule_id: str = "security.dynamic_code_execution",
) -> RiskFinding:
    return RiskFinding(
        severity=severity,
        category=category,
        file=file,
        message="Dynamic code execution appears in the changed lines.",
        evidence="eval(user_input)",
        rule_id=rule_id,
        confidence=confidence,
        recommendation="Avoid dynamic execution.",
        source=FindingSource.RULE,
        line_start=line_start,
        line_end=line_start,
    )


def _context_pack() -> ContextPack:
    return ContextPack(
        title="Add risky helper",
        body="Implements a helper with security-sensitive behavior.",
        author="dev",
        html_url="https://github.com/owner/repo/pull/7",
        changed_files=[],
        files=[
            ContextFile(
                filename="app.py",
                status="modified",
                additions=12,
                deletions=2,
                patch="+eval(user_input)",
                truncated=True,
                truncation_reason="patch_budget_per_file_exceeded",
            )
        ],
        omitted_files=[
            OmittedContextFile(
                filename="docs/usage.md",
                reason="total_patch_budget_exceeded",
            )
        ],
    )


def test_render_markdown_includes_finding_line_number_when_available() -> None:
    report = ReviewReport(risks=[_finding()])

    markdown = render_markdown(_context(), report)

    assert "### HIGH security: app.py:42" in markdown
    assert "Rule: `security.dynamic_code_execution`" in markdown
    assert "Confidence: `high`" in markdown
    assert "Recommendation: Avoid dynamic execution." in markdown


def test_render_markdown_outputs_review_brief_matrix_context_and_copy_ready_comment() -> None:
    report = ReviewReport(
        summary=["Touches a security-sensitive helper."],
        risks=[
            _finding(severity=Severity.LOW, confidence=Confidence.LOW, rule_id="low.rule"),
            _finding(severity=Severity.HIGH, confidence=Confidence.HIGH),
        ],
        suggestions=["Ask the author to replace dynamic execution with a safe dispatch table."],
        review_checklist=["Verify user input cannot reach code execution."],
        model_used="local heuristic analyzer",
        ai_error="AI analysis failed: invalid JSON",
    )

    markdown = render_markdown(_context(), report, context_pack=_context_pack())

    assert "## PR 基本信息" in markdown
    assert "## Change Summary" in markdown
    assert "## Review Brief" in markdown
    assert "## Risk Matrix" in markdown
    assert "| Severity | Confidence | Count |" in markdown
    assert "## Findings with Evidence" in markdown
    assert markdown.index("### HIGH security: app.py:42") < markdown.index(
        "### LOW security: app.py:42"
    )
    assert "## Test Gaps" in markdown
    assert "tests/test_app.py" in markdown
    assert "## Omitted / Truncated Context" in markdown
    assert "docs/usage.md" in markdown
    assert "patch_budget_per_file_exceeded" in markdown
    assert "## Copy-ready Review Comment" in markdown
    assert "## Analyzer Metadata" in markdown
    assert "AI analysis failed: invalid JSON" in markdown


def test_render_markdown_no_risks_still_gives_manual_review_guidance() -> None:
    report = ReviewReport(summary=["Small documentation update."])

    markdown = render_markdown(_context(), report)

    assert "No evidence-backed risk findings detected." in markdown
    assert "人工检查" in markdown


def test_render_json_is_parseable_and_includes_report_sections() -> None:
    report = ReviewReport(
        summary=["Touches a security-sensitive helper."],
        risks=[_finding()],
        suggestions=["Replace eval with an explicit mapping."],
        review_checklist=["Check behavior and tests."],
        model_used="gpt-4.1-mini",
    )

    data = json.loads(report_module.render_json(_context(), report, context_pack=_context_pack()))

    assert data["pull_request"]["number"] == 7
    assert data["review_brief"]["top_risks"][0]["file"] == "app.py"
    assert data["risk_matrix"][0]["severity"] == "high"
    assert data["findings"][0]["rule_id"] == "security.dynamic_code_execution"
    assert data["test_gaps"]["has_test_changes"] is True
    assert data["context"]["omitted_files"][0]["filename"] == "docs/usage.md"
    assert data["metadata"]["model"] == "gpt-4.1-mini"
