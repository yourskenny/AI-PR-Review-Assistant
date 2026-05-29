from __future__ import annotations

import os
import re
from typing import Any

import requests

from ai_pr_review.models import PRContext, PRFile, PullRequestRef

PR_URL_RE = re.compile(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)/?$")


class GitHubClientError(RuntimeError):
    pass


def parse_pr_url(url: str) -> PullRequestRef:
    match = PR_URL_RE.match(url.strip())
    if not match:
        raise GitHubClientError(
            "Expected a GitHub PR URL like https://github.com/owner/repo/pull/123"
        )
    return PullRequestRef(
        owner=match.group("owner"),
        repo=match.group("repo"),
        number=int(match.group("number")),
    )


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: int = 20) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.timeout = timeout

    def fetch_pr_context(self, ref: PullRequestRef) -> PRContext:
        pr = self._get_json(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}")
        files = self._get_paginated(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/files")
        return PRContext(
            ref=ref,
            title=pr.get("title") or "",
            body=pr.get("body") or "",
            author=(pr.get("user") or {}).get("login") or "",
            html_url=pr.get("html_url") or "",
            files=[
                PRFile(
                    filename=item.get("filename") or "",
                    status=item.get("status") or "",
                    additions=int(item.get("additions") or 0),
                    deletions=int(item.get("deletions") or 0),
                    patch=item.get("patch") or "",
                )
                for item in files
            ],
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-pr-review-assistant",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_json(self, path: str) -> dict[str, Any]:
        try:
            response = requests.get(
                f"https://api.github.com{path}",
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise GitHubClientError(f"GitHub API request failed: {exc}") from exc
        if response.status_code >= 400:
            raise GitHubClientError(f"GitHub API failed: {response.status_code} {response.text}")
        return response.json()

    def _get_paginated(self, path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            try:
                response = requests.get(
                    f"https://api.github.com{path}",
                    params={"per_page": 100, "page": page},
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                raise GitHubClientError(f"GitHub API request failed: {exc}") from exc
            if response.status_code >= 400:
                raise GitHubClientError(
                    f"GitHub API failed: {response.status_code} {response.text}"
                )
            batch = response.json()
            if not batch:
                return items
            items.extend(batch)
            page += 1
