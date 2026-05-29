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
class PatchLine:
    kind: str
    content: str
    old_line_number: int | None
    new_line_number: int | None


@dataclass(frozen=True)
class PatchHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    section_header: str
    lines: list[PatchLine] = field(default_factory=list)

    def added_lines(self) -> list[PatchLine]:
        return [line for line in self.lines if line.kind == "add"]


@dataclass(frozen=True)
class ParsedFilePatch:
    filename: str
    status: str
    additions: int
    deletions: int
    hunks: list[PatchHunk] = field(default_factory=list)

    def added_lines(self) -> list[PatchLine]:
        return [line for hunk in self.hunks for line in hunk.added_lines()]


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
    line_start: int | None = None
    line_end: int | None = None


@dataclass
class ReviewReport:
    summary: list[str] = field(default_factory=list)
    risks: list[RiskFinding] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    model_used: str | None = None
