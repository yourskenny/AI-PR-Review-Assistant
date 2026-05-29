from __future__ import annotations

import re

from ai_pr_review.models import ParsedFilePatch, PatchHunk, PatchLine, PRFile

HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?P<section>.*)$"
)


def parse_pr_file(file: PRFile) -> ParsedFilePatch:
    parsed = parse_file_patch(file.patch)
    return ParsedFilePatch(
        filename=file.filename,
        status=file.status,
        additions=file.additions,
        deletions=file.deletions,
        hunks=parsed.hunks,
    )


def parse_file_patch(patch: str) -> ParsedFilePatch:
    hunks: list[PatchHunk] = []
    current_lines: list[PatchLine] | None = None
    current_hunk: PatchHunk | None = None
    old_line_number = 0
    new_line_number = 0

    for raw_line in patch.splitlines():
        header = HUNK_HEADER_RE.match(raw_line)
        if header:
            current_lines = []
            current_hunk = PatchHunk(
                old_start=int(header.group("old_start")),
                old_count=int(header.group("old_count") or "1"),
                new_start=int(header.group("new_start")),
                new_count=int(header.group("new_count") or "1"),
                section_header=header.group("section").strip(),
                lines=current_lines,
            )
            hunks.append(current_hunk)
            old_line_number = current_hunk.old_start
            new_line_number = current_hunk.new_start
            continue

        if current_lines is None:
            continue

        if raw_line.startswith("\\"):
            continue

        prefix = raw_line[:1]
        content = raw_line[1:] if prefix in {" ", "+", "-"} else raw_line
        if prefix == "+" and not raw_line.startswith("+++"):
            current_lines.append(
                PatchLine(
                    kind="add",
                    content=content,
                    old_line_number=None,
                    new_line_number=new_line_number,
                )
            )
            new_line_number += 1
        elif prefix == "-" and not raw_line.startswith("---"):
            current_lines.append(
                PatchLine(
                    kind="delete",
                    content=content,
                    old_line_number=old_line_number,
                    new_line_number=None,
                )
            )
            old_line_number += 1
        else:
            current_lines.append(
                PatchLine(
                    kind="context",
                    content=content,
                    old_line_number=old_line_number,
                    new_line_number=new_line_number,
                )
            )
            old_line_number += 1
            new_line_number += 1

    return ParsedFilePatch(
        filename="",
        status="",
        additions=0,
        deletions=0,
        hunks=hunks,
    )
