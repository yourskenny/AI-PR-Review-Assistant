import json

from typer.testing import CliRunner

from ai_pr_review import cli
from ai_pr_review.cli import app
from ai_pr_review.models import PRContext, PRFile, PullRequestRef, ReviewReport


def test_analyze_help_exposes_model_and_language_options() -> None:
    result = CliRunner().invoke(app, ["analyze", "--help"])

    assert result.exit_code == 0
    assert "--model" in result.output
    assert "--language" in result.output


def test_analyze_writes_json_report_when_format_json_is_requested(monkeypatch, tmp_path) -> None:
    class FakeGitHubClient:
        def fetch_pr_context(self, ref: PullRequestRef) -> PRContext:
            return PRContext(
                ref=ref,
                title="Demo PR",
                body="",
                author="dev",
                html_url="https://github.com/owner/repo/pull/7",
                files=[PRFile("app.py", "modified", 1, 0, "+print('hello')")],
            )

    class FakeReviewEngine:
        def __init__(self, model: str | None = None, language: str = "zh") -> None:
            self.model = model
            self.language = language

        def analyze(self, context: PRContext, use_ai: bool = True) -> ReviewReport:
            assert use_ai is False
            return ReviewReport(summary=["Changed one Python file."], model_used=self.model)

    monkeypatch.setattr(cli, "GitHubClient", FakeGitHubClient)
    monkeypatch.setattr(cli, "ReviewEngine", FakeReviewEngine)
    output = tmp_path / "report.json"

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "https://github.com/owner/repo/pull/7",
            "--no-ai",
            "--format",
            "json",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["pull_request"]["number"] == 7
    assert data["summary"] == ["Changed one Python file."]
