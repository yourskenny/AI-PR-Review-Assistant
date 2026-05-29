from __future__ import annotations

from typing import Protocol

from ai_pr_review.models import PRContext, RiskFinding


class Scanner(Protocol):
    def scan(self, context: PRContext) -> list[RiskFinding]:
        """Return external scanner findings for a PR context."""
