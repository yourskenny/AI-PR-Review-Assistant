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
from ai_pr_review.models import PRContext, ReviewReport
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
    return {
        "request": request,
        "result": result,
        "error": error,
        "form": form or {"pr_url": "", "mode": "no-ai", "language": "zh", "scanners": ""},
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
