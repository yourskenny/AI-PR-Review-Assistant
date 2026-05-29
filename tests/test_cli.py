import json

from typer.testing import CliRunner

from ai_pr_review import cli
from ai_pr_review.cli import app
from ai_pr_review.models import PRContext, PRFile, PullRequestRef, ReviewReport, Severity


def test_analyze_help_exposes_model_and_language_options() -> None:
    result = CliRunner().invoke(app, ["analyze", "--help"])

    assert result.exit_code == 0
    assert "--model" in result.output
    assert "--language" in result.output


def test_dashboard_help_is_available() -> None:
    result = CliRunner().invoke(app, ["dashboard", "--help"])

    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output


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
        def __init__(
            self,
            model: str | None = None,
            language: str = "zh",
            **kwargs: object,
        ) -> None:
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


def test_analyze_applies_config_file_to_filters_and_engine(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    class FakeGitHubClient:
        def fetch_pr_context(self, ref: PullRequestRef) -> PRContext:
            return PRContext(
                ref=ref,
                title="Demo PR",
                body="",
                author="dev",
                html_url="https://github.com/owner/repo/pull/7",
                files=[
                    PRFile("src/app.py", "modified", 1, 0, "+eval(user)"),
                    PRFile("src/skip.py", "modified", 1, 0, "+eval(user)"),
                    PRFile("docs/readme.md", "modified", 1, 0, "+docs"),
                ],
            )

    class FakeReviewEngine:
        def __init__(
            self,
            model: str | None = None,
            language: str = "zh",
            patch_budget_per_file: int = 3500,
            total_patch_budget: int = 12000,
            enabled_rules: list[str] | None = None,
            min_severity: Severity = Severity.LOW,
            **kwargs: object,
        ) -> None:
            captured["model"] = model
            captured["language"] = language
            captured["patch_budget_per_file"] = patch_budget_per_file
            captured["total_patch_budget"] = total_patch_budget
            captured["enabled_rules"] = enabled_rules
            captured["min_severity"] = min_severity

        def analyze(self, context: PRContext, use_ai: bool = True) -> ReviewReport:
            captured["use_ai"] = use_ai
            captured["files"] = [file.filename for file in context.files]
            return ReviewReport(summary=["configured"])

    config_path = tmp_path / "ai-pr-review.json"
    config_path.write_text(
        json.dumps(
            {
                "language": "en",
                "model": "config-model",
                "enable_ai": False,
                "include_patterns": ["src/*.py"],
                "ignore_patterns": ["src/skip.py"],
                "patch_budget_per_file": 17,
                "total_budget": 33,
                "enabled_rules": ["security.dynamic_code_execution"],
                "min_severity": "medium",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "GitHubClient", FakeGitHubClient)
    monkeypatch.setattr(cli, "ReviewEngine", FakeReviewEngine)

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "https://github.com/owner/repo/pull/7",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "model": "config-model",
        "language": "en",
        "patch_budget_per_file": 17,
        "total_patch_budget": 33,
        "enabled_rules": ["security.dynamic_code_execution"],
        "min_severity": Severity.MEDIUM,
        "use_ai": False,
        "files": ["src/app.py"],
    }


def test_analyze_posts_summary_comment_when_comment_flag_is_set(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeGitHubClient:
        def fetch_pr_context(self, ref: PullRequestRef) -> PRContext:
            return PRContext(
                ref=ref,
                title="Demo PR",
                body="",
                author="dev",
                html_url="https://github.com/owner/repo/pull/7",
                files=[PRFile("src/app.py", "modified", 1, 0, "+print('hello')")],
            )

    class FakeReviewEngine:
        def __init__(self, **kwargs: object) -> None:
            pass

        def analyze(self, context: PRContext, use_ai: bool = True) -> ReviewReport:
            return ReviewReport(summary=["comment me"])

    class FakeCommenter:
        def upsert_summary_comment(self, ref: PullRequestRef, body: str) -> str:
            captured["ref"] = ref
            captured["body"] = body
            return "created"

    monkeypatch.setattr(cli, "GitHubClient", FakeGitHubClient)
    monkeypatch.setattr(cli, "ReviewEngine", FakeReviewEngine)
    monkeypatch.setattr(cli, "GitHubCommenter", lambda: FakeCommenter())

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "https://github.com/owner/repo/pull/7",
            "--no-ai",
            "--comment",
        ],
    )

    assert result.exit_code == 0
    assert captured["ref"] == PullRequestRef("owner", "repo", 7)
    assert "comment me" in str(captured["body"])
    assert "GitHub comment created" in result.output


def test_analyze_posts_inline_review_when_inline_comment_flag_is_set(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeGitHubClient:
        def fetch_pr_context(self, ref: PullRequestRef) -> PRContext:
            return PRContext(
                ref=ref,
                title="Demo PR",
                body="",
                author="dev",
                html_url="https://github.com/owner/repo/pull/7",
                files=[PRFile("src/app.py", "modified", 1, 0, "+eval(user)")],
            )

    class FakeReviewEngine:
        def __init__(self, **kwargs: object) -> None:
            pass

        def analyze(self, context: PRContext, use_ai: bool = True) -> ReviewReport:
            from ai_pr_review.models import Confidence, FindingSource, RiskFinding

            return ReviewReport(
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
                ]
            )

    class FakeCommenter:
        def create_inline_review(self, ref: PullRequestRef, findings: object) -> str:
            captured["ref"] = ref
            captured["findings"] = findings
            return "created"

    monkeypatch.setattr(cli, "GitHubClient", FakeGitHubClient)
    monkeypatch.setattr(cli, "ReviewEngine", FakeReviewEngine)
    monkeypatch.setattr(cli, "GitHubCommenter", lambda: FakeCommenter())

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "https://github.com/owner/repo/pull/7",
            "--no-ai",
            "--inline-comments",
        ],
    )

    assert result.exit_code == 0
    assert captured["ref"] == PullRequestRef("owner", "repo", 7)
    assert "security.dynamic_code_execution" in str(captured["findings"])
    assert "GitHub inline review created" in result.output


def test_analyze_enables_bandit_scanner_from_cli(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeGitHubClient:
        def fetch_pr_context(self, ref: PullRequestRef) -> PRContext:
            return PRContext(
                ref=ref,
                title="Demo PR",
                body="",
                author="dev",
                html_url="https://github.com/owner/repo/pull/7",
                files=[PRFile("src/app.py", "modified", 1, 0, "+eval(user)")],
            )

    class FakeReviewEngine:
        def __init__(self, scanners: list[object] | None = None, **kwargs: object) -> None:
            captured["scanner_types"] = [type(scanner).__name__ for scanner in scanners or []]

        def analyze(self, context: PRContext, use_ai: bool = True) -> ReviewReport:
            return ReviewReport(summary=["scanned"])

    monkeypatch.setattr(cli, "GitHubClient", FakeGitHubClient)
    monkeypatch.setattr(cli, "ReviewEngine", FakeReviewEngine)

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "https://github.com/owner/repo/pull/7",
            "--no-ai",
            "--enable-scanners",
            "bandit",
        ],
    )

    assert result.exit_code == 0
    assert captured["scanner_types"] == ["BanditScanner"]
