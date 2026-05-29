import importlib
import json

from ai_pr_review.models import PRContext, PRFile, PullRequestRef, Severity


def test_load_config_uses_defaults_when_no_file_exists(tmp_path) -> None:
    config_module = importlib.import_module("ai_pr_review.config")

    config = config_module.load_config(cwd=tmp_path)

    assert config.language == "zh"
    assert config.model is None
    assert config.patch_budget_per_file == 3500
    assert config.total_budget == 12000
    assert config.include_patterns == []
    assert config.ignore_patterns == []
    assert config.enabled_rules is None
    assert config.min_severity == Severity.LOW
    assert config.enable_ai is True


def test_load_config_reads_json_and_filters_context_files(tmp_path) -> None:
    config_module = importlib.import_module("ai_pr_review.config")
    config_path = tmp_path / ".ai-pr-review.json"
    config_path.write_text(
        json.dumps(
            {
                "language": "en",
                "model": "test-model",
                "max_files": 1,
                "patch_budget_per_file": 100,
                "total_budget": 200,
                "include_patterns": ["src/*.py", "tests/*.py"],
                "ignore_patterns": ["src/generated/*"],
                "enabled_rules": ["security.dynamic_code_execution"],
                "min_severity": "medium",
                "enable_ai": False,
            }
        ),
        encoding="utf-8",
    )
    context = _context(
        [
            PRFile("docs/readme.md", "modified", 1, 0, "+docs"),
            PRFile("src/generated/client.py", "modified", 1, 0, "+generated"),
            PRFile("src/app.py", "modified", 1, 0, "+eval(user)"),
            PRFile("tests/test_app.py", "modified", 1, 0, "+def test_app(): pass"),
        ]
    )

    config = config_module.load_config(config_path)
    filtered = config_module.apply_file_filters(context, config)

    assert config.language == "en"
    assert config.model == "test-model"
    assert config.max_files == 1
    assert config.enabled_rules == ["security.dynamic_code_execution"]
    assert config.min_severity == Severity.MEDIUM
    assert config.enable_ai is False
    assert [file.filename for file in filtered.files] == ["src/app.py"]


def test_load_config_accepts_utf8_bom_files(tmp_path) -> None:
    config_module = importlib.import_module("ai_pr_review.config")
    config_path = tmp_path / ".ai-pr-review.json"
    config_path.write_bytes(b"\xef\xbb\xbf" + b'{"language": "en"}')

    config = config_module.load_config(config_path)

    assert config.language == "en"


def _context(files: list[PRFile]) -> PRContext:
    return PRContext(
        ref=PullRequestRef("owner", "repo", 1),
        title="demo",
        body="",
        author="dev",
        html_url="https://github.com/owner/repo/pull/1",
        files=files,
    )
