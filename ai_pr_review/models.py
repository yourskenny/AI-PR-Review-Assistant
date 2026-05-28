from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class PullRequestRef:
    owner: str
    repo: str
    number: int


@dataclass(frozen=True)
class PRFile:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str = ""


@dataclass(frozen=True)
class PRContext:
    ref: PullRequestRef
    title: str
    body: str
    author: str
    html_url: str
    files: list[PRFile]


@dataclass(frozen=True)
class RiskFinding:
    severity: Severity
    category: str
    file: str
    message: str
    evidence: str


@dataclass
class ReviewReport:
    summary: list[str] = field(default_factory=list)
    risks: list[RiskFinding] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    model_used: str | None = None
