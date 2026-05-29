from __future__ import annotations

from ai_pr_review.models import PRContext, ReviewReport


def render_markdown(context: PRContext, report: ReviewReport) -> str:
    lines = [
        "# PR Review Report",
        "",
        f"- PR: [{context.ref.owner}/{context.ref.repo}#{context.ref.number}]({context.html_url})",
        f"- Author: {context.author or 'unknown'}",
        f"- Model: {report.model_used or 'local heuristic analyzer'}",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- {item}" for item in report.summary)
    lines.extend(["", "## Risk Findings", ""])
    if report.risks:
        for finding in report.risks:
            location = finding.file
            if finding.line_start is not None:
                location = f"{location}:{finding.line_start}"
            lines.extend(
                [
                    f"### {finding.severity.value.upper()} {finding.category}: {location}",
                    "",
                    finding.message,
                    "",
                    f"- Rule: `{finding.rule_id}`",
                    f"- Confidence: `{finding.confidence.value}`",
                    f"- Recommendation: {finding.recommendation}",
                    "",
                    "```text",
                    finding.evidence,
                    "```",
                    "",
                ]
            )
    else:
        lines.extend(["No high-confidence risk findings detected.", ""])

    lines.extend(["## Review Suggestions", ""])
    lines.extend(f"- {item}" for item in report.suggestions)
    lines.append("")
    return "\n".join(lines)
