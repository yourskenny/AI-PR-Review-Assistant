import requests

from ai_pr_review.models import (
    Confidence,
    FindingSource,
    PullRequestRef,
    RiskFinding,
    Severity,
)

COMMENT_MARKER = "<!-- ai-pr-review-assistant -->"


def test_upsert_summary_comment_updates_existing_bot_comment(monkeypatch) -> None:
    from ai_pr_review.github_commenter import GitHubCommenter

    calls: list[tuple[str, str, str | None]] = []

    class FakeResponse:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        calls.append(("GET", url, None))
        return FakeResponse(
            [
                {"id": 100, "body": "human note", "user": {"type": "User"}},
                {"id": 200, "body": f"{COMMENT_MARKER}\nold", "user": {"type": "Bot"}},
            ]
        )

    def fake_patch(url, **kwargs):
        calls.append(("PATCH", url, kwargs["json"]["body"]))
        return FakeResponse({"id": 200})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "patch", fake_patch)

    result = GitHubCommenter(token="token").upsert_summary_comment(
        PullRequestRef("owner", "repo", 7),
        "new report",
    )

    assert result == "updated"
    assert calls[-1] == (
        "PATCH",
        "https://api.github.com/repos/owner/repo/issues/comments/200",
        f"{COMMENT_MARKER}\nnew report",
    )


def test_upsert_summary_comment_creates_comment_when_marker_is_missing(monkeypatch) -> None:
    from ai_pr_review.github_commenter import GitHubCommenter

    calls: list[tuple[str, str, str | None]] = []

    class FakeResponse:
        status_code = 201
        text = ""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        calls.append(("GET", url, None))
        return FakeResponse([])

    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs["json"]["body"]))
        return FakeResponse({"id": 300})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    result = GitHubCommenter(token="token").upsert_summary_comment(
        PullRequestRef("owner", "repo", 7),
        "new report",
    )

    assert result == "created"
    assert calls[-1] == (
        "POST",
        "https://api.github.com/repos/owner/repo/issues/7/comments",
        f"{COMMENT_MARKER}\nnew report",
    )


def test_upsert_summary_comment_wraps_network_errors(monkeypatch) -> None:
    from ai_pr_review.github_commenter import GitHubCommenter, GitHubCommenterError

    def fake_get(*args, **kwargs):
        raise requests.ConnectionError("connection reset")

    monkeypatch.setattr(requests, "get", fake_get)

    try:
        GitHubCommenter(token="token").upsert_summary_comment(
            PullRequestRef("owner", "repo", 7),
            "new report",
        )
    except GitHubCommenterError as exc:
        assert "GitHub comment request failed" in str(exc)
    else:
        raise AssertionError("expected GitHubCommenterError")


def test_create_inline_review_posts_evidence_bound_comments(monkeypatch) -> None:
    from ai_pr_review.github_commenter import GitHubCommenter

    calls: list[tuple[str, str, object]] = []

    class FakeResponse:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        calls.append(("GET", url, None))
        return FakeResponse({"head": {"sha": "abc123"}})

    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs["json"]))
        return FakeResponse({"id": 400})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    result = GitHubCommenter(token="token").create_inline_review(
        PullRequestRef("owner", "repo", 7),
        [
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
                line_start=42,
                line_end=42,
            )
        ],
    )

    assert result == "created"
    assert calls[0] == (
        "GET",
        "https://api.github.com/repos/owner/repo/pulls/7",
        None,
    )
    assert calls[-1] == (
        "POST",
        "https://api.github.com/repos/owner/repo/pulls/7/reviews",
        {
            "commit_id": "abc123",
            "event": "COMMENT",
            "body": "<!-- ai-pr-review-assistant-inline -->\nAI PR Review inline findings: 1",
            "comments": [
                {
                    "path": "src/app.py",
                    "line": 42,
                    "side": "RIGHT",
                    "body": (
                        "**HIGH security** `security.dynamic_code_execution`\n\n"
                        "Dynamic execution appears in the changed line.\n\n"
                        "Evidence:\n```text\neval(user)\n```\n\n"
                        "Recommendation: Use a bounded dispatch table.\n\n"
                        "Confidence: high; Source: rule"
                    ),
                }
            ],
        },
    )


def test_create_inline_review_skips_findings_without_line_numbers(monkeypatch) -> None:
    from ai_pr_review.github_commenter import GitHubCommenter

    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("post should not be called")

    monkeypatch.setattr(requests, "post", fake_post)

    result = GitHubCommenter(token="token").create_inline_review(
        PullRequestRef("owner", "repo", 7),
        [
            RiskFinding(
                severity=Severity.MEDIUM,
                category="testing",
                file="",
                message="Source changed without tests.",
                evidence="no tests",
                rule_id="testing.source_without_tests",
                confidence=Confidence.MEDIUM,
                recommendation="Add focused tests.",
                source=FindingSource.RULE,
            )
        ],
    )

    assert result == "skipped"
    assert called is False
