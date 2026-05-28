import pytest

from ai_pr_review.github_client import GitHubClientError, parse_pr_url


def test_parse_pr_url() -> None:
    ref = parse_pr_url("https://github.com/openai/openai-python/pull/123")

    assert ref.owner == "openai"
    assert ref.repo == "openai-python"
    assert ref.number == 123


def test_parse_pr_url_rejects_non_pr_url() -> None:
    with pytest.raises(GitHubClientError):
        parse_pr_url("https://github.com/openai/openai-python/issues/123")
