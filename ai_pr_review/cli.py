from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ai_pr_review.ai_client import AIClientError
from ai_pr_review.config import ConfigError, apply_file_filters, load_config
from ai_pr_review.github_client import GitHubClient, GitHubClientError, parse_pr_url
from ai_pr_review.github_commenter import GitHubCommenter, GitHubCommenterError
from ai_pr_review.report import render_json, render_markdown
from ai_pr_review.review_engine import ReviewEngine
from ai_pr_review.scanners.bandit import BanditScanner

app = typer.Typer(help="AI-assisted GitHub Pull Request review CLI.")
console = Console()


@app.callback()
def main() -> None:
    """AI-assisted GitHub Pull Request review CLI."""


@app.command()
def analyze(
    pr_url: Annotated[
        str,
        typer.Argument(
            help="GitHub PR URL, for example https://github.com/owner/repo/pull/123"
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write the report to a file."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", help="Output format: markdown or json."),
    ] = "markdown",
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to .ai-pr-review.json config file."),
    ] = None,
    comment: Annotated[
        bool,
        typer.Option("--comment", help="Create or update one GitHub PR summary comment."),
    ] = False,
    enable_scanners: Annotated[
        str,
        typer.Option("--enable-scanners", help="Comma-separated optional scanners, e.g. bandit."),
    ] = "",
    no_ai: Annotated[
        bool,
        typer.Option("--no-ai", help="Disable OpenAI analysis and use local heuristics only."),
    ] = False,
    model: Annotated[
        str | None,
        typer.Option("--model", help="OpenAI model to use when AI analysis is enabled."),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option("--language", help="Report language: zh or en."),
    ] = None,
) -> None:
    """Fetch a GitHub PR and generate a review report."""
    try:
        config = load_config(config_path)
        normalized_format = _normalise_output_format(output_format)
        ref = parse_pr_url(pr_url)
        context = apply_file_filters(GitHubClient().fetch_pr_context(ref), config)
        resolved_model = model or config.model
        resolved_language = language or config.language
        report = ReviewEngine(
            model=resolved_model,
            language=resolved_language,
            patch_budget_per_file=config.patch_budget_per_file,
            total_patch_budget=config.total_budget,
            enabled_rules=config.enabled_rules,
            min_severity=config.min_severity,
            scanners=_build_scanners(enable_scanners),
        ).analyze(context, use_ai=(not no_ai and config.enable_ai))
    except (GitHubClientError, AIClientError, ConfigError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    rendered = (
        render_json(context, report)
        if normalized_format == "json"
        else render_markdown(context, report)
    )
    if comment:
        try:
            result = GitHubCommenter().upsert_summary_comment(
                ref,
                render_markdown(context, report),
            )
        except GitHubCommenterError as exc:
            raise typer.BadParameter(str(exc)) from exc
        console.print(f"[green]GitHub comment {result}[/green]")
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        console.print(f"[green]Report written to {output}[/green]")
    else:
        console.print(rendered)


def _normalise_output_format(output_format: str) -> str:
    lowered = output_format.lower()
    if lowered in {"markdown", "json"}:
        return lowered
    raise typer.BadParameter("format must be either 'markdown' or 'json'")


def _build_scanners(scanner_names: str) -> list:
    scanners = []
    for name in [item.strip().lower() for item in scanner_names.split(",") if item.strip()]:
        if name == "bandit":
            scanners.append(BanditScanner())
            continue
        raise typer.BadParameter(f"unknown scanner '{name}'")
    return scanners


if __name__ == "__main__":
    app()
