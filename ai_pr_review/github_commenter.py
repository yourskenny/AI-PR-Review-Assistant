from __future__ import annotations

import os
from typing import Any, Literal

import requests

from ai_pr_review.models import PullRequestRef

COMMENT_MARKER = "<!-- ai-pr-review-assistant -->"


class GitHubCommenterError(RuntimeError):
    pass


class GitHubCommenter:
    def __init__(self, token: str | None = None, timeout: int = 20) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.timeout = timeout

    def upsert_summary_comment(
        self,
        ref: PullRequestRef,
        body: str,
    ) -> Literal["created", "updated"]:
        comment_body = f"{COMMENT_MARKER}\n{body}"
        existing = self._find_existing_comment(ref)
        if existing is None:
            self._post_json(
                f"/repos/{ref.owner}/{ref.repo}/issues/{ref.number}/comments",
                {"body": comment_body},
            )
            return "created"

        self._patch_json(
            f"/repos/{ref.owner}/{ref.repo}/issues/comments/{existing['id']}",
            {"body": comment_body},
        )
        return "updated"

    def _find_existing_comment(self, ref: PullRequestRef) -> dict[str, Any] | None:
        comments = self._get_json(
            f"/repos/{ref.owner}/{ref.repo}/issues/{ref.number}/comments"
        )
        if not isinstance(comments, list):
            raise GitHubCommenterError("GitHub comments API returned an unexpected payload.")
        for comment in comments:
            if _is_bot_marker_comment(comment):
                return comment
        return None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-pr-review-assistant",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_json(self, path: str) -> Any:
        try:
            response = requests.get(
                f"https://api.github.com{path}",
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise GitHubCommenterError(f"GitHub comment request failed: {exc}") from exc
        self._raise_for_status(response)
        return response.json()

    def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            response = requests.post(
                f"https://api.github.com{path}",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise GitHubCommenterError(f"GitHub comment request failed: {exc}") from exc
        self._raise_for_status(response)
        return response.json()

    def _patch_json(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            response = requests.patch(
                f"https://api.github.com{path}",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise GitHubCommenterError(f"GitHub comment request failed: {exc}") from exc
        self._raise_for_status(response)
        return response.json()

    def _raise_for_status(self, response: requests.Response) -> None:
        if response.status_code >= 400:
            raise GitHubCommenterError(
                f"GitHub comment API failed: {response.status_code} {response.text}"
            )


def _is_bot_marker_comment(comment: dict[str, Any]) -> bool:
    user = comment.get("user") or {}
    return user.get("type") == "Bot" and str(comment.get("body") or "").startswith(
        COMMENT_MARKER
    )
