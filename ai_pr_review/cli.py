from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ai_pr_review.github_client import GitHubClient, GitHubClientError, parse_pr_url
from ai_pr_review.report import render_markdown
from ai_pr_review.review_engine import ReviewEngine

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
        typer.Option("--output", "-o", help="Write the markdown report to a file."),
    ] = None,
    no_ai: Annotated[
        bool,
        typer.Option("--no-ai", help="Disable OpenAI analysis and use local heuristics only."),
    ] = False,
) -> None:
    """Fetch a GitHub PR and generate a review report."""
    try:
        ref = parse_pr_url(pr_url)
        context = GitHubClient().fetch_pr_context(ref)
        report = ReviewEngine().analyze(context, use_ai=not no_ai)
    except GitHubClientError as exc:
        raise typer.BadParameter(str(exc)) from exc

    markdown = render_markdown(context, report)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
        console.print(f"[green]Report written to {output}[/green]")
    else:
        console.print(markdown)


if __name__ == "__main__":
    app()
