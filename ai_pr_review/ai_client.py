from __future__ import annotations

import json
from dataclasses import dataclass, field
from json import JSONDecodeError
from typing import Any


class AIClientError(RuntimeError):
    pass


@dataclass
class AIReviewResult:
    summary: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    review_checklist: list[str] = field(default_factory=list)


def parse_ai_review_response(raw: str) -> AIReviewResult:
    try:
        data = json.loads(raw or "{}")
    except JSONDecodeError as exc:
        raise AIClientError(f"Invalid AI JSON response: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise AIClientError("AI JSON response must be an object")

    return AIReviewResult(
        summary=_as_string_list(data.get("summary")),
        suggestions=_as_string_list(data.get("review_suggestions") or data.get("suggestions")),
        review_checklist=_as_string_list(data.get("review_checklist")),
    )


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []
