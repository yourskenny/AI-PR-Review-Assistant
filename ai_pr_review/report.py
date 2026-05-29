from __future__ import annotations

import json
from collections import Counter
from typing import Any

from ai_pr_review.context_builder import build_context_pack
from ai_pr_review.models import (
    Confidence,
    ContextPack,
    PRContext,
    PRFile,
    ReviewReport,
    RiskFinding,
    Severity,
)

SEVERITY_RANK = {Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1}
CONFIDENCE_RANK = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1}


def render_markdown(
    context: PRContext,
    report: ReviewReport,
    *,
    context_pack: ContextPack | None = None,
) -> str:
    context_pack = context_pack or build_context_pack(context, report.risks)
    findings = _sorted_findings(report.risks)
    test_summary = _test_gap_summary(context)
    copy_ready_comment = _copy_ready_comment(context, report, findings, test_summary)
    lines = [
        "# AI PR Review Report",
        "",
        "## PR 基本信息",
        "",
        f"- PR: [{context.ref.owner}/{context.ref.repo}#{context.ref.number}]({context.html_url})",
        f"- Title: {context.title or 'Untitled PR'}",
        f"- Author: {context.author or 'unknown'}",
        f"- Files: {len(context.files)}",
        f"- Changes: +{_total_additions(context.files)}/-{_total_deletions(context.files)}",
        "",
        "## Change Summary",
        "",
    ]
    lines.extend(_bullet_lines(report.summary or [_fallback_summary_line(context)]))
    lines.extend(["", "## Review Brief", ""])
    lines.extend(_bullet_lines(_review_brief_lines(context, findings, test_summary)))
    lines.extend(["", "## Reviewer Action Plan", ""])
    lines.extend(_bullet_lines(_reviewer_action_plan(context, findings, test_summary)))
    lines.extend(["", "## Risk Matrix", ""])
    lines.extend(_risk_matrix_lines(findings))
    lines.extend(["", "## Findings with Evidence", ""])
    if findings:
        for finding in findings:
            lines.extend(_finding_lines(finding))
    else:
        lines.extend(
            [
                "No evidence-backed risk findings detected.",
                "",
                "- 人工检查建议：重点确认行为变更、边界条件、回滚路径和测试覆盖是否充分。",
                "",
            ]
        )

    lines.extend(["## Test Gaps", ""])
    lines.extend(_test_gap_lines(test_summary))

    lines.extend(["", "## Review Suggestions", ""])
    lines.extend(_bullet_lines(report.suggestions or _default_review_suggestions(findings)))
    if report.review_checklist:
        lines.extend(["", "## Review Checklist", ""])
        lines.extend(_bullet_lines(report.review_checklist))

    lines.extend(["", "## Omitted / Truncated Context", ""])
    lines.extend(_context_lines(context_pack))

    lines.extend(["", "## Copy-ready Review Comment", "", "```markdown"])
    lines.append(copy_ready_comment)
    lines.extend(["```", ""])

    lines.extend(
        [
            "## Analyzer Metadata",
            "",
            f"- Model: {report.model_used or 'local heuristic analyzer'}",
            "- Analyzer: rule-first evidence scanner with optional AI summary",
            f"- Mode: {'ai-assisted' if report.model_used else 'local-only'}",
        ]
    )
    if report.ai_error:
        lines.append(f"- AI fallback note: {report.ai_error}")
    lines.append("")
    return "\n".join(lines)


def render_json(
    context: PRContext,
    report: ReviewReport,
    *,
    context_pack: ContextPack | None = None,
) -> str:
    context_pack = context_pack or build_context_pack(context, report.risks)
    findings = _sorted_findings(report.risks)
    test_summary = _test_gap_summary(context)
    payload: dict[str, Any] = {
        "pull_request": {
            "owner": context.ref.owner,
            "repo": context.ref.repo,
            "number": context.ref.number,
            "title": context.title,
            "author": context.author,
            "url": context.html_url,
            "files_changed": len(context.files),
            "additions": _total_additions(context.files),
            "deletions": _total_deletions(context.files),
        },
        "summary": report.summary or [_fallback_summary_line(context)],
        "review_brief": {
            "lines": _review_brief_lines(context, findings, test_summary),
            "top_risks": [_finding_payload(finding) for finding in findings[:3]],
        },
        "reviewer_action_plan": _reviewer_action_plan(context, findings, test_summary),
        "risk_matrix": _risk_matrix_payload(findings),
        "findings": [_finding_payload(finding) for finding in findings],
        "test_gaps": test_summary,
        "suggestions": report.suggestions or _default_review_suggestions(findings),
        "review_checklist": report.review_checklist,
        "context": {
            "included_files": [
                {
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "truncated": file.truncated,
                    "truncation_reason": file.truncation_reason,
                }
                for file in context_pack.files
            ],
            "omitted_files": [
                {"filename": file.filename, "reason": file.reason}
                for file in context_pack.omitted_files
            ],
        },
        "copy_ready_review_comment": _copy_ready_comment(
            context, report, findings, test_summary
        ),
        "metadata": {
            "model": report.model_used or "local heuristic analyzer",
            "mode": "ai-assisted" if report.model_used else "local-only",
            "ai_error": report.ai_error,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_sarif(context: PRContext, report: ReviewReport) -> str:
    findings = _sorted_findings(report.risks)
    rules = []
    seen_rules: set[str] = set()
    for finding in findings:
        if finding.rule_id in seen_rules:
            continue
        seen_rules.add(finding.rule_id)
        rules.append(
            {
                "id": finding.rule_id,
                "name": finding.rule_id,
                "shortDescription": {"text": finding.message},
                "help": {"text": finding.recommendation},
                "properties": {
                    "category": finding.category,
                    "confidence": finding.confidence.value,
                },
            }
        )
    payload: dict[str, Any] = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "AI PR Review Assistant",
                        "informationUri": context.html_url,
                        "rules": rules,
                    }
                },
                "results": [_sarif_result(finding) for finding in findings],
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _sorted_findings(findings: list[RiskFinding]) -> list[RiskFinding]:
    return sorted(
        findings,
        key=lambda finding: (
            -SEVERITY_RANK[finding.severity],
            -CONFIDENCE_RANK[finding.confidence],
            finding.file,
            finding.line_start or 0,
            finding.rule_id,
        ),
    )


def _finding_lines(finding: RiskFinding) -> list[str]:
    location = _finding_location(finding)
    return [
        f"### {finding.severity.value.upper()} {finding.category}: {location}",
        "",
        finding.message,
        "",
        f"- Rule: `{finding.rule_id}`",
        f"- Source: `{finding.source.value}`",
        f"- Confidence: `{finding.confidence.value}`",
        f"- Priority reason: {_priority_reason(finding)}",
        f"- Recommendation: {finding.recommendation}",
        "",
        "```text",
        finding.evidence,
        "```",
        "",
    ]


def _risk_matrix_lines(findings: list[RiskFinding]) -> list[str]:
    lines = ["| Severity | Confidence | Count |", "| --- | --- | --- |"]
    for item in _risk_matrix_payload(findings):
        lines.append(
            f"| {item['severity']} | {item['confidence']} | {item['count']} |"
        )
    if not findings:
        lines.append("| none | none | 0 |")
    return lines


def _risk_matrix_payload(findings: list[RiskFinding]) -> list[dict[str, Any]]:
    counts = Counter((finding.severity.value, finding.confidence.value) for finding in findings)
    order = {
        severity.value: SEVERITY_RANK[severity]
        for severity in (Severity.HIGH, Severity.MEDIUM, Severity.LOW)
    }
    confidence_order = {
        confidence.value: CONFIDENCE_RANK[confidence]
        for confidence in (Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW)
    }
    return [
        {"severity": severity, "confidence": confidence, "count": count}
        for (severity, confidence), count in sorted(
            counts.items(),
            key=lambda item: (-order[item[0][0]], -confidence_order[item[0][1]]),
        )
    ]


def _finding_payload(finding: RiskFinding) -> dict[str, Any]:
    return {
        "severity": finding.severity.value,
        "category": finding.category,
        "file": finding.file,
        "line_start": finding.line_start,
        "line_end": finding.line_end,
        "message": finding.message,
        "evidence": finding.evidence,
        "rule_id": finding.rule_id,
        "confidence": finding.confidence.value,
        "recommendation": finding.recommendation,
        "source": finding.source.value,
        "priority_reason": _priority_reason(finding),
    }


def _sarif_result(finding: RiskFinding) -> dict[str, Any]:
    region: dict[str, Any] = {}
    if finding.line_start is not None:
        region["startLine"] = finding.line_start
    if finding.line_end is not None:
        region["endLine"] = finding.line_end
    return {
        "ruleId": finding.rule_id,
        "level": _sarif_level(finding.severity),
        "message": {"text": f"{finding.message} Recommendation: {finding.recommendation}"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": finding.file or "PR"},
                    "region": region,
                }
            }
        ],
        "properties": {
            "severity": finding.severity.value,
            "confidence": finding.confidence.value,
            "source": finding.source.value,
            "evidence": finding.evidence,
            "priority_reason": _priority_reason(finding),
        },
    }


def _sarif_level(severity: Severity) -> str:
    if severity == Severity.HIGH:
        return "error"
    if severity == Severity.MEDIUM:
        return "warning"
    return "note"


def _finding_location(finding: RiskFinding) -> str:
    if finding.line_start is None:
        return finding.file
    if finding.line_end and finding.line_end != finding.line_start:
        return f"{finding.file}:{finding.line_start}-{finding.line_end}"
    return f"{finding.file}:{finding.line_start}"


def _review_brief_lines(
    context: PRContext,
    findings: list[RiskFinding],
    test_summary: dict[str, Any],
) -> list[str]:
    change_size = (
        f"变更规模：{len(context.files)} 个文件，"
        f"+{_total_additions(context.files)}/-{_total_deletions(context.files)} 行。"
    )
    lines = [
        change_size,
        f"最高风险：{_highest_risk_text(findings)}",
        f"测试覆盖信号：{_test_signal_text(test_summary)}",
    ]
    if findings:
        top = findings[0]
        lines.append(f"建议优先查看：{_finding_location(top)}，原因是 {top.message}")
    else:
        lines.append("未发现带证据的高置信风险，仍建议人工检查行为影响和测试边界。")
    return lines


def _reviewer_action_plan(
    context: PRContext,
    findings: list[RiskFinding],
    test_summary: dict[str, Any],
) -> list[str]:
    if not findings:
        return [
            "Confirm the intended behavior change with the PR author.",
            "Review boundary conditions, compatibility, and rollback expectations manually.",
            "Run the relevant test suite before merge.",
        ]
    plan = []
    for index, finding in enumerate(findings[:3], start=1):
        plan.append(
            f"{index}. Inspect {_finding_location(finding)} first. "
            f"{_priority_reason(finding)} Verify by checking: {finding.recommendation}"
        )
    if test_summary["source_without_tests"]:
        plan.append(
            "Add or request focused tests before merge because source files changed without "
            "detected test file changes."
        )
    else:
        plan.append("Use the changed tests as the first regression signal, then review edge cases.")
    if len(context.files) > 10:
        plan.append("Ask for a file-by-file review map if the change mixes unrelated concerns.")
    return plan


def _priority_reason(finding: RiskFinding) -> str:
    parts = [
        f"{finding.severity.value} severity",
        f"{finding.confidence.value} confidence",
    ]
    if finding.line_start is not None:
        parts.append("new-line evidence")
    if finding.source.value != "rule":
        parts.append(f"{finding.source.value} source")
    if finding.category in {"security", "testing", "review-readiness"}:
        parts.append(f"{finding.category} impact")
    return "; ".join(parts) + "."


def _highest_risk_text(findings: list[RiskFinding]) -> str:
    if not findings:
        return "未发现 evidence-backed finding"
    highest = findings[0]
    return (
        f"{highest.severity.value}/{highest.confidence.value} "
        f"{highest.category} at {_finding_location(highest)}"
    )


def _test_signal_text(test_summary: dict[str, Any]) -> str:
    if test_summary["has_test_changes"]:
        return f"检测到测试相关变更：{', '.join(test_summary['test_files'])}"
    return "未检测到测试相关文件变更，需人工确认测试覆盖。"


def _test_gap_lines(test_summary: dict[str, Any]) -> list[str]:
    lines = [
        f"- Source files changed: {', '.join(test_summary['source_files']) or 'none'}",
        f"- Test files changed: {', '.join(test_summary['test_files']) or 'none'}",
    ]
    if test_summary["source_without_tests"]:
        lines.append("- 人工检查：源代码有变更但未检测到测试文件变更。")
    else:
        lines.append("- 测试信号：检测到测试文件变更或本次变更不包含源代码。")
    return lines


def _context_lines(context_pack: ContextPack) -> list[str]:
    lines: list[str] = []
    truncated = [file for file in context_pack.files if file.truncated]
    if not context_pack.omitted_files and not truncated:
        return ["- No omitted or truncated context."]
    for file in truncated:
        lines.append(f"- Truncated `{file.filename}`: {file.truncation_reason}")
    for file in context_pack.omitted_files:
        lines.append(f"- Omitted `{file.filename}`: {file.reason}")
    return lines


def _copy_ready_comment(
    context: PRContext,
    report: ReviewReport,
    findings: list[RiskFinding],
    test_summary: dict[str, Any],
) -> str:
    lines = [
        f"AI PR Review brief for #{context.ref.number}: {context.title or 'Untitled PR'}",
        "",
    ]
    lines.extend(f"- {item}" for item in (report.summary or [_fallback_summary_line(context)]))
    if findings:
        lines.append("")
        lines.append("Top risks:")
        for finding in findings[:3]:
            lines.append(
                f"- {finding.severity.value}/{finding.confidence.value} "
                f"{_finding_location(finding)}: {finding.message}"
            )
    else:
        lines.extend(
            [
                "",
                "No evidence-backed risk findings detected. Please still check behavior, "
                "edge cases, and tests manually.",
            ]
        )
    if test_summary["source_without_tests"]:
        lines.append("- Test note: source changed without detected test file changes.")
    return "\n".join(lines)


def _default_review_suggestions(findings: list[RiskFinding]) -> list[str]:
    if findings:
        return ["优先处理带行号和证据的风险项，再检查相关测试是否覆盖。"]
    return ["未发现高置信风险时，仍建议人工检查行为变更、测试覆盖和兼容性。"]


def _test_gap_summary(context: PRContext) -> dict[str, Any]:
    source_files = [file.filename for file in context.files if _is_source_file(file.filename)]
    test_files = [file.filename for file in context.files if _is_test_file(file.filename)]
    return {
        "source_files": source_files,
        "test_files": test_files,
        "has_source_changes": bool(source_files),
        "has_test_changes": bool(test_files),
        "source_without_tests": bool(source_files and not test_files),
    }


def _is_test_file(filename: str) -> bool:
    lowered = filename.lower()
    return (
        lowered.startswith("tests/")
        or "/tests/" in lowered
        or lowered.startswith("test/")
        or lowered.endswith(("_test.py", "_test.js", "_test.ts"))
        or lowered.endswith((".test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"))
        or lowered.startswith("test_")
    )


def _is_source_file(filename: str) -> bool:
    lowered = filename.lower()
    if _is_test_file(lowered):
        return False
    if lowered.startswith("docs/") or lowered.endswith((".md", ".rst", ".txt")):
        return False
    return lowered.endswith(
        (
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".go",
            ".java",
            ".rb",
            ".php",
            ".cs",
            ".rs",
            ".cpp",
            ".c",
            ".h",
        )
    )


def _fallback_summary_line(context: PRContext) -> str:
    return (
        f"PR #{context.ref.number} changes {len(context.files)} files "
        f"(+{_total_additions(context.files)}/-{_total_deletions(context.files)})."
    )


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _total_additions(files: list[PRFile]) -> int:
    return sum(file.additions for file in files)


def _total_deletions(files: list[PRFile]) -> int:
    return sum(file.deletions for file in files)
