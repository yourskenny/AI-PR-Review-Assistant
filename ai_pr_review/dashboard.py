from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ai_pr_review.github_client import GitHubClient, parse_pr_url
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
from ai_pr_review.report import render_json, render_markdown
from ai_pr_review.review_engine import ReviewEngine
from ai_pr_review.scanners.bandit import BanditScanner

DashboardAnalyzer = Callable[..., "DashboardResult"]


@dataclass(frozen=True)
class DashboardResult:
    context: PRContext
    report: ReviewReport
    markdown: str
    json_report: dict[str, Any]
    mode: str
    scanners: str
    language: str


def create_app(analyzer: DashboardAnalyzer | None = None) -> FastAPI:
    app = FastAPI(title="AI PR Review Dashboard")
    app.state.analyzer = analyzer or analyze_pr_url

    package_dir = Path(__file__).parent
    templates = Jinja2Templates(directory=str(package_dir / "templates"))
    app.mount(
        "/static",
        StaticFiles(directory=str(package_dir / "static")),
        name="static",
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context=_view_context(request),
        )

    @app.post("/analyze", response_class=HTMLResponse)
    async def analyze(request: Request) -> HTMLResponse:
        form = _parse_form(await request.body())
        try:
            result = app.state.analyzer(
                form["pr_url"],
                language=form["language"],
                use_ai=form["mode"] == "ai",
                scanners=form["scanners"],
            )
            return templates.TemplateResponse(
                request=request,
                name="dashboard.html",
                context=_view_context(request, result=result, form=form),
            )
        except Exception as exc:
            return templates.TemplateResponse(
                request=request,
                name="dashboard.html",
                context=_view_context(request, error=str(exc), form=form),
                status_code=400,
            )

    @app.post("/demo/champion", response_class=HTMLResponse)
    async def champion_demo(request: Request) -> HTMLResponse:
        result = _champion_demo_result()
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context=_view_context(
                request,
                result=result,
                form={
                    "pr_url": result.context.html_url,
                    "mode": "no-ai",
                    "language": "zh",
                    "scanners": "demo",
                },
            ),
        )

    @app.post("/api/analyze")
    async def api_analyze(request: Request) -> JSONResponse:
        payload = await request.json()
        try:
            result = app.state.analyzer(
                str(payload.get("pr_url") or ""),
                language=str(payload.get("language") or "zh"),
                use_ai=str(payload.get("mode") or "no-ai") == "ai",
                scanners=str(payload.get("scanners") or ""),
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(result.json_report)

    return app


def analyze_pr_url(
    pr_url: str,
    *,
    language: str,
    use_ai: bool,
    scanners: str,
) -> DashboardResult:
    ref = parse_pr_url(pr_url)
    context = GitHubClient().fetch_pr_context(ref)
    scanner_instances = _build_scanners(scanners)
    report = ReviewEngine(language=language, scanners=scanner_instances).analyze(
        context,
        use_ai=use_ai,
    )
    json_text = render_json(context, report)
    return DashboardResult(
        context=context,
        report=report,
        markdown=render_markdown(context, report),
        json_report=json.loads(json_text),
        mode="ai-assisted" if use_ai else "local-only",
        scanners=scanners,
        language=language,
    )


def _parse_form(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {
        "pr_url": _first(parsed, "pr_url"),
        "mode": _first(parsed, "mode", "no-ai"),
        "language": _first(parsed, "language", "zh"),
        "scanners": _first(parsed, "scanners"),
    }


def _first(parsed: dict[str, list[str]], key: str, default: str = "") -> str:
    values = parsed.get(key)
    return values[0] if values else default


def _view_context(
    request: Request,
    *,
    result: DashboardResult | None = None,
    error: str | None = None,
    form: dict[str, str] | None = None,
) -> dict[str, Any]:
    json_report = result.json_report if result else {}
    return {
        "request": request,
        "result": result,
        "error": error,
        "form": form or {"pr_url": "", "mode": "no-ai", "language": "zh", "scanners": ""},
        "action_plan": json_report.get("reviewer_action_plan", []),
        "highest_risk": _highest_risk_label(json_report),
        "json_text": json.dumps(result.json_report, ensure_ascii=False, indent=2)
        if result
        else "",
    }


def _build_scanners(scanner_names: str) -> list:
    scanners = []
    for name in [item.strip().lower() for item in scanner_names.split(",") if item.strip()]:
        if name == "bandit":
            scanners.append(BanditScanner())
            continue
        raise ValueError(f"unknown scanner '{name}'")
    return scanners


def _highest_risk_label(json_report: dict[str, Any]) -> str:
    findings = json_report.get("findings") or []
    if not findings:
        return "none"
    first = findings[0]
    return f"{first.get('severity')}/{first.get('confidence')} {first.get('category')}"


def _champion_demo_result() -> DashboardResult:
    context = PRContext(
        ref=PullRequestRef("demo", "champion-pr", 42),
        title="Champion demo: harden auth session refresh",
        body="Tightens session refresh behavior, adds a migration, but misses rollback notes.",
        author="demo-reviewer",
        html_url="https://github.com/demo/champion-pr/pull/42",
        files=[
            PRFile(
                "src/auth/session.py",
                "modified",
                6,
                2,
                (
                    "@@ -12,6 +12,8 @@\n"
                    "+if user.is_admin or bypass_auth:\n"
                    "+    return refresh_session(user)\n"
                    "+eval(policy_expression)\n"
                ),
            ),
            PRFile(
                "src/db/users.py",
                "modified",
                3,
                1,
                '@@ -4,5 +4,6 @@\n+query = f"SELECT * FROM users WHERE id = {user_id}"\n',
            ),
            PRFile(
                "migrations/20260529_add_session_flags.sql",
                "added",
                1,
                0,
                "@@ -0,0 +1,1 @@\n+ALTER TABLE sessions ADD COLUMN flags TEXT;\n",
            ),
        ],
    )
    report = ReviewReport(
        summary=[
            "Champion demo PR changes auth refresh, user lookup, and schema behavior.",
            (
                "The highest-value review path is security first, migration safety second, "
                "tests third."
            ),
        ],
        risks=[
            RiskFinding(
                severity=Severity.HIGH,
                category="security",
                file="src/auth/session.py",
                message="Dynamic code execution appears in the changed line.",
                evidence="eval(policy_expression)",
                rule_id="security.dynamic_code_execution",
                confidence=Confidence.HIGH,
                recommendation="Replace eval with a bounded policy dispatch table.",
                source=FindingSource.RULE,
                line_start=14,
                line_end=14,
            ),
            RiskFinding(
                severity=Severity.HIGH,
                category="security",
                file="src/auth/session.py",
                message="Permission or authentication bypass logic appears in a sensitive path.",
                evidence="if user.is_admin or bypass_auth:",
                rule_id="security.permission_bypass",
                confidence=Confidence.MEDIUM,
                recommendation="Require explicit authorization checks and add negative tests.",
                source=FindingSource.RULE,
                line_start=12,
                line_end=12,
            ),
            RiskFinding(
                severity=Severity.HIGH,
                category="security",
                file="src/db/users.py",
                message="SQL is assembled with runtime values in the changed line.",
                evidence='query = f"SELECT * FROM users WHERE id = {user_id}"',
                rule_id="security.sql_injection",
                confidence=Confidence.MEDIUM,
                recommendation="Use parameterized queries instead of string interpolation.",
                source=FindingSource.RULE,
                line_start=6,
                line_end=6,
            ),
        ],
        suggestions=[
            "Review auth and SQL findings before discussing style or refactors.",
            "Request focused tests for negative permission cases and query parameter handling.",
        ],
    )
    json_text = render_json(context, report)
    return DashboardResult(
        context=context,
        report=report,
        markdown=render_markdown(context, report),
        json_report=json.loads(json_text),
        mode="champion-demo local-only",
        scanners="built-in demo",
        language="zh",
    )
