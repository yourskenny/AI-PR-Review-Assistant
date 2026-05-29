from __future__ import annotations

import re

from ai_pr_review.models import PRContext, RiskFinding, Severity
from ai_pr_review.patch_parser import parse_pr_file

RulePattern = tuple[re.Pattern[str], Severity, str, str]

RULES: list[RulePattern] = [
    (
        re.compile(r"\b(eval|exec)\s*\("),
        Severity.HIGH,
        "security",
        "Dynamic code execution appears in the changed lines.",
    ),
    (
        re.compile(r"subprocess\.(Popen|run|call)\(.*shell\s*=\s*True"),
        Severity.HIGH,
        "security",
        "Shell execution with shell=True can enable command injection.",
    ),
    (
        re.compile(r"except\s+Exception\s*:\s*(pass)?\s*$"),
        Severity.MEDIUM,
        "reliability",
        "Broad exception handling can hide production failures.",
    ),
    (
        re.compile(r"\b(password|secret|api[_-]?key|token)\b\s*=\s*['\"][^'\"]+['\"]", re.I),
        Severity.HIGH,
        "security",
        "A credential-like value appears to be hard-coded.",
    ),
    (
        re.compile(r"\btime\.sleep\(\s*\d+"),
        Severity.LOW,
        "performance",
        "Fixed sleeps can slow CI and introduce flaky behavior.",
    ),
]


def scan_risks(context: PRContext) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    changed_test_files = [file for file in context.files if _is_test_file(file.filename)]
    changed_source_files = [file for file in context.files if not _is_test_file(file.filename)]

    for file in context.files:
        for line in parse_pr_file(file).added_lines():
            for pattern, severity, category, message in RULES:
                if pattern.search(line.content):
                    findings.append(
                        RiskFinding(
                            severity=severity,
                            category=category,
                            file=file.filename,
                            message=message,
                            evidence=line.content.strip(),
                            line_start=line.new_line_number,
                            line_end=line.new_line_number,
                        )
                    )

    if changed_source_files and not changed_test_files:
        touched = ", ".join(file.filename for file in changed_source_files[:3])
        findings.append(
            RiskFinding(
                severity=Severity.MEDIUM,
                category="testing",
                file=touched,
                message="Source files changed without an accompanying test file in this PR.",
                evidence="No changed file matched common test naming conventions.",
            )
        )

    return findings

def _is_test_file(filename: str) -> bool:
    lowered = filename.lower()
    return (
        "/test" in lowered
        or "\\test" in lowered
        or lowered.startswith("test_")
        or "_test." in lowered
        or ".test." in lowered
        or ".spec." in lowered
    )
