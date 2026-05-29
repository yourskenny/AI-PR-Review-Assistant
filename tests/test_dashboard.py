from __future__ import annotations

import json

from fastapi.testclient import TestClient

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


def test_dashboard_homepage_renders_analysis_form() -> None:
    from ai_pr_review.dashboard import create_app

    client = TestClient(create_app(analyzer=_fake_analyzer))

    response = client.get("/")

    assert response.status_code == 200
    assert "AI PR Review Console" in response.text
    assert 'name="pr_url"' in response.text
    assert "Review Brief" in response.text


def test_dashboard_post_renders_review_sections() -> None:
    from ai_pr_review.dashboard import create_app

    client = TestClient(create_app(analyzer=_fake_analyzer))

    response = client.post(
        "/analyze",
        data={
            "pr_url": "https://github.com/owner/repo/pull/7",
            "mode": "no-ai",
            "language": "zh",
            "scanners": "bandit",
        },
    )

    assert response.status_code == 200
    assert "Demo PR" in response.text
    assert "Risk Matrix" in response.text
    assert "security.dynamic_code_execution" in response.text
    assert "Copy-ready Review Comment" in response.text


def test_dashboard_api_returns_structured_json() -> None:
    from ai_pr_review.dashboard import create_app

    client = TestClient(create_app(analyzer=_fake_analyzer))

    response = client.post(
        "/api/analyze",
        json={
            "pr_url": "https://github.com/owner/repo/pull/7",
            "mode": "no-ai",
            "language": "zh",
            "scanners": "",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["pull_request"]["number"] == 7
    assert data["findings"][0]["rule_id"] == "security.dynamic_code_execution"


def _fake_analyzer(
    pr_url: str,
    *,
    language: str,
    use_ai: bool,
    scanners: str,
):
    from ai_pr_review.dashboard import DashboardResult
    from ai_pr_review.report import render_json, render_markdown

    context = PRContext(
        ref=PullRequestRef("owner", "repo", 7),
        title="Demo PR",
        body="",
        author="dev",
        html_url=pr_url,
        files=[PRFile("src/app.py", "modified", 1, 0, "+eval(user)")],
    )
    report = ReviewReport(
        summary=["Demo PR changes one risky function."],
        risks=[
            RiskFinding(
                severity=Severity.HIGH,
                category="security",
                file="src/app.py",
                message="Dynamic execution appears in the changed line.",
                evidence="eval(user)",
                rule_id="security.dynamic_code_execution",
                confidence=Confidence.HIGH,
                recommendation="Use a bounded dispatch table.",
                source=FindingSource.RULE,
                line_start=1,
                line_end=1,
            )
        ],
        suggestions=["Review the risky function first."],
    )
    json_text = render_json(context, report)
    return DashboardResult(
        context=context,
        report=report,
        markdown=render_markdown(context, report),
        json_report=json.loads(json_text),
        mode="local-only" if not use_ai else "ai-assisted",
        scanners=scanners,
        language=language,
    )
