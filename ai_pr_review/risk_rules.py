from __future__ import annotations

import re
from dataclasses import dataclass

from ai_pr_review.models import Confidence, FindingSource, PRContext, RiskFinding, Severity
from ai_pr_review.patch_parser import parse_pr_file


@dataclass(frozen=True)
class RiskRule:
    rule_id: str
    pattern: re.Pattern[str]
    severity: Severity
    confidence: Confidence
    category: str
    message: str
    recommendation: str


RULES: list[RiskRule] = [
    RiskRule(
        "security.dynamic_code_execution",
        re.compile(r"\b(eval|exec)\s*\("),
        Severity.HIGH,
        Confidence.HIGH,
        "security",
        "Dynamic code execution appears in the changed lines.",
        "Avoid dynamic execution; replace it with explicit parsing or a bounded dispatch table.",
    ),
    RiskRule(
        "security.subprocess_shell_true",
        re.compile(r"subprocess\.(Popen|run|call)\(.*shell\s*=\s*True"),
        Severity.HIGH,
        Confidence.HIGH,
        "security",
        "Shell execution with shell=True can enable command injection.",
        (
            "Pass arguments as a list and keep shell=False unless shell expansion is "
            "strictly required."
        ),
    ),
    RiskRule(
        "security.hardcoded_secret",
        re.compile(r"\b(password|secret|api[_-]?key|token)\b\s*=\s*['\"][^'\"]+['\"]", re.I),
        Severity.HIGH,
        Confidence.HIGH,
        "security",
        "A credential-like value appears to be hard-coded.",
        "Move secrets to environment variables or a secret manager and rotate exposed values.",
    ),
    RiskRule(
        "security.unsafe_deserialization",
        re.compile(r"\b(pickle\.loads?|yaml\.load)\s*\("),
        Severity.HIGH,
        Confidence.MEDIUM,
        "security",
        "Unsafe deserialization can execute attacker-controlled payloads.",
        "Use a safe parser such as yaml.safe_load, or validate trusted input before deserializing.",
    ),
    RiskRule(
        "security.requests_verify_false",
        re.compile(r"\brequests\.\w+\([^)]*verify\s*=\s*False"),
        Severity.HIGH,
        Confidence.HIGH,
        "security",
        "TLS certificate verification is disabled in an HTTP request.",
        "Keep certificate verification enabled and fix the trust chain instead of disabling it.",
    ),
    RiskRule(
        "security.weak_hash",
        re.compile(r"\bhashlib\.(md5|sha1)\s*\("),
        Severity.MEDIUM,
        Confidence.MEDIUM,
        "security",
        "Weak hash algorithms are risky for security-sensitive use.",
        "Use SHA-256 or a purpose-built password hashing function for security-sensitive hashing.",
    ),
    RiskRule(
        "security.debug_enabled",
        re.compile(r"\b(DEBUG|debug)\s*=\s*True\b"),
        Severity.MEDIUM,
        Confidence.MEDIUM,
        "security",
        "Debug mode appears to be enabled in changed code.",
        (
            "Ensure debug mode is disabled outside local development and guarded by "
            "environment config."
        ),
    ),
    RiskRule(
        "security.permissive_cors",
        re.compile(r"(Access-Control-Allow-Origin.*\*|CORS_ALLOW_ALL_ORIGINS\s*=\s*True)"),
        Severity.MEDIUM,
        Confidence.MEDIUM,
        "security",
        "Permissive CORS settings can expose APIs to unintended origins.",
        "Restrict allowed origins to the minimum set required by the application.",
    ),
    RiskRule(
        "reliability.bare_except",
        re.compile(r"except\s*:\s*(pass)?\s*$"),
        Severity.MEDIUM,
        Confidence.HIGH,
        "reliability",
        "Bare exception handling can hide interrupts and production failures.",
        "Catch specific exception types and log or re-raise unexpected failures.",
    ),
    RiskRule(
        "reliability.broad_exception_pass",
        re.compile(r"except\s+Exception\s*:\s*(pass)?\s*$"),
        Severity.MEDIUM,
        Confidence.HIGH,
        "reliability",
        "Broad exception handling can hide production failures.",
        "Handle expected exceptions explicitly and log enough context for unexpected failures.",
    ),
    RiskRule(
        "reliability.request_without_timeout",
        re.compile(r"\brequests\.(get|post|put|patch|delete|request)\([^)]*\)"),
        Severity.MEDIUM,
        Confidence.MEDIUM,
        "reliability",
        "HTTP request appears to run without an explicit timeout.",
        "Set a timeout so external network stalls cannot hang the process indefinitely.",
    ),
    RiskRule(
        "reliability.fixed_sleep",
        re.compile(r"\btime\.sleep\(\s*\d+"),
        Severity.LOW,
        Confidence.MEDIUM,
        "reliability",
        "Fixed sleeps can slow CI and introduce flaky behavior.",
        "Prefer waiting on a concrete condition or use bounded retry with backoff.",
    ),
]


def scan_risks(context: PRContext) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    changed_test_files = [file for file in context.files if _is_test_file(file.filename)]
    changed_source_files = [file for file in context.files if not _is_test_file(file.filename)]

    for file in context.files:
        for line in parse_pr_file(file).added_lines():
            for rule in RULES:
                if (
                    rule.rule_id == "reliability.request_without_timeout"
                    and "timeout" in line.content
                ):
                    continue
                if rule.pattern.search(line.content):
                    findings.append(
                        RiskFinding(
                            severity=rule.severity,
                            category=rule.category,
                            file=file.filename,
                            message=rule.message,
                            evidence=line.content.strip(),
                            rule_id=rule.rule_id,
                            confidence=rule.confidence,
                            recommendation=rule.recommendation,
                            source=FindingSource.RULE,
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
                rule_id="testing.source_without_tests",
                confidence=Confidence.MEDIUM,
                recommendation="Add or update tests that exercise the changed source behavior.",
                source=FindingSource.RULE,
            )
        )

    high_risk_files = [file for file in changed_source_files if _is_high_risk_path(file.filename)]
    if high_risk_files and not changed_test_files:
        touched = ", ".join(file.filename for file in high_risk_files[:3])
        findings.append(
            RiskFinding(
                severity=Severity.HIGH,
                category="testing",
                file=touched,
                message="High-risk paths changed without an accompanying test file in this PR.",
                evidence=(
                    "Changed path matched auth, permission, payment, security, "
                    "or config keywords."
                ),
                rule_id="testing.high_risk_path_without_tests",
                confidence=Confidence.MEDIUM,
                recommendation="Add focused tests around the high-risk behavior before merging.",
                source=FindingSource.RULE,
            )
        )

    total_additions = sum(file.additions for file in context.files)
    total_deletions = sum(file.deletions for file in context.files)
    if len(context.files) > 20 or total_additions + total_deletions > 600:
        findings.append(
            RiskFinding(
                severity=Severity.MEDIUM,
                category="maintainability",
                file="PR",
                message="Large PRs are harder to review thoroughly and increase regression risk.",
                evidence=(
                    f"Changed {len(context.files)} files with "
                    f"+{total_additions}/-{total_deletions} lines."
                ),
                rule_id="maintainability.large_pr",
                confidence=Confidence.HIGH,
                recommendation="Split unrelated changes or provide a file-by-file review plan.",
                source=FindingSource.RULE,
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


def _is_high_risk_path(filename: str) -> bool:
    lowered = filename.lower()
    keywords = (
        "auth",
        "permission",
        "session",
        "token",
        "payment",
        "billing",
        "security",
        "config",
        "secret",
    )
    return any(keyword in lowered for keyword in keywords)
