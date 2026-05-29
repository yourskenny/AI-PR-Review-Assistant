import json

from ai_pr_review.models import PRContext, PRFile, PullRequestRef
from ai_pr_review.review_engine import ReviewEngine


def test_review_engine_sends_context_pack_to_ai(monkeypatch) -> None:
    captured_payloads: list[dict] = []

    class FakeMessage:
        content = '{"summary": ["ok"], "suggestions": ["review carefully"]}'

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            payload = json.loads(kwargs["messages"][1]["content"])
            captured_payloads.append(payload)
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        chat = FakeChat()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("ai_pr_review.review_engine.OpenAI", lambda: FakeOpenAI())
    context = PRContext(
        ref=PullRequestRef("owner", "repo", 1),
        title="demo",
        body="",
        author="dev",
        html_url="https://github.com/owner/repo/pull/1",
        files=[
            PRFile("src/risky.py", "modified", 1, 0, "@@ -1,1 +1,1 @@\n+eval(user)\n"),
            PRFile("src/other.py", "modified", 1, 0, "@@ -1,1 +1,1 @@\n+" + "a" * 50),
        ],
    )

    ReviewEngine(model="test-model", patch_budget_per_file=20, total_patch_budget=30).analyze(
        context,
        use_ai=True,
    )

    payload = captured_payloads[0]
    assert [file["filename"] for file in payload["files"]] == ["src/risky.py"]
    assert payload["files"][0]["truncated"] is True
    assert payload["files"][0]["truncation_reason"] == "patch_budget_per_file_exceeded"
    assert payload["omitted_files"] == [
        {"filename": "src/other.py", "reason": "total_patch_budget_exceeded"}
    ]
    assert payload["changed_files"][0]["filename"] == "src/risky.py"
