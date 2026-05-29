from typer.testing import CliRunner

from ai_pr_review.cli import app


def test_analyze_help_exposes_model_and_language_options() -> None:
    result = CliRunner().invoke(app, ["analyze", "--help"])

    assert result.exit_code == 0
    assert "--model" in result.output
    assert "--language" in result.output
