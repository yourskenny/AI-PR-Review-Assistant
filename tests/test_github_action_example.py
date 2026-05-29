from pathlib import Path


def test_github_action_example_uses_minimal_permissions_and_no_default_fork_secrets() -> None:
    workflow = Path("examples/github-action.yml").read_text(encoding="utf-8")

    assert "pull-requests: write" in workflow
    assert "issues: write" in workflow
    assert "contents: read" in workflow
    assert "pull_request_target" not in workflow
    assert "--comment" in workflow
    assert "OPENAI_API_KEY" in workflow
