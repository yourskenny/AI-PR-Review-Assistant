import pytest
import requests

from ai_pr_review.github_client import GitHubClient, GitHubClientError
from ai_pr_review.models import PullRequestRef


def test_fetch_pr_context_wraps_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_connection_error(*args: object, **kwargs: object) -> None:
        raise requests.ConnectionError("connection reset")

    monkeypatch.setattr(requests, "get", raise_connection_error)

    with pytest.raises(GitHubClientError, match="GitHub API request failed"):
        GitHubClient().fetch_pr_context(PullRequestRef("owner", "repo", 1))
