from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ai_pr_review.models import Confidence, FindingSource, PRContext, RiskFinding, Severity
from ai_pr_review.patch_parser import parse_pr_file


class BanditScanner:
    def __init__(self, command: str = "bandit") -> None:
        self.command = command

    def scan(self, context: PRContext) -> list[RiskFinding]:
        python_files = [file for file in context.files if file.filename.endswith(".py")]
        if not python_files:
            return []

        path_map: dict[str, str] = {}
        with tempfile.TemporaryDirectory(prefix="ai-pr-review-bandit-") as temp_dir:
            root = Path(temp_dir)
            for file in python_files:
                target = root / file.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(_added_python_content(file), encoding="utf-8")
                path_map[str(target.resolve())] = file.filename

            try:
                completed = subprocess.run(
                    [self.command, "-r", str(root), "-f", "json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except FileNotFoundError:
                return []

        if not completed.stdout.strip():
            return []
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return []
        return [
            _finding_from_result(result, path_map)
            for result in payload.get("results", [])
        ]


def _added_python_content(file) -> str:
    lines = [line.content for line in parse_pr_file(file).added_lines()]
    return "\n".join(lines) + ("\n" if lines else "")


def _finding_from_result(result: dict[str, Any], path_map: dict[str, str]) -> RiskFinding:
    test_id = str(result.get("test_id") or "unknown")
    filename = _original_filename(str(result.get("filename") or ""), path_map)
    return RiskFinding(
        severity=_severity(result.get("issue_severity")),
        category="security",
        file=filename,
        message=str(result.get("issue_text") or "Bandit reported a security finding."),
        evidence=str(result.get("code") or ""),
        rule_id=f"bandit.{test_id}",
        confidence=_confidence(result.get("issue_confidence")),
        recommendation="Review the Bandit finding and apply the safer alternative.",
        source=FindingSource.SCANNER,
        line_start=_line_number(result.get("line_number")),
        line_end=_line_number(result.get("line_number")),
    )


def _original_filename(filename: str, path_map: dict[str, str]) -> str:
    try:
        resolved = str(Path(filename).resolve())
    except OSError:
        return filename
    return path_map.get(resolved, filename)


def _severity(value: Any) -> Severity:
    match str(value or "").lower():
        case "high":
            return Severity.HIGH
        case "medium":
            return Severity.MEDIUM
        case _:
            return Severity.LOW


def _confidence(value: Any) -> Confidence:
    match str(value or "").lower():
        case "high":
            return Confidence.HIGH
        case "medium":
            return Confidence.MEDIUM
        case _:
            return Confidence.LOW


def _line_number(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
