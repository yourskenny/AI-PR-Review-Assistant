from __future__ import annotations

import json
import os

from openai import OpenAI

from ai_pr_review.models import PRContext, ReviewReport
from ai_pr_review.risk_rules import scan_risks


class ReviewEngine:
    def __init__(self, model: str | None = None, patch_budget_per_file: int = 3500) -> None:
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        self.patch_budget_per_file = patch_budget_per_file

    def analyze(self, context: PRContext, use_ai: bool = True) -> ReviewReport:
        risks = scan_risks(context)
        fallback = ReviewReport(
            summary=self._fallback_summary(context),
            risks=risks,
            suggestions=self._fallback_suggestions(context, risks),
            model_used=None,
        )
        if not use_ai or not os.getenv("OPENAI_API_KEY"):
            return fallback

        ai_report = self._ai_analyze(context, risks)
        if ai_report.summary:
            fallback.summary = ai_report.summary
        if ai_report.suggestions:
            fallback.suggestions = ai_report.suggestions
        fallback.model_used = self.model
        return fallback

    def _ai_analyze(self, context: PRContext, risks: list) -> ReviewReport:
        client = OpenAI()
        payload = {
            "pull_request": {
                "title": context.title,
                "body": context.body[:2000],
                "author": context.author,
                "url": context.html_url,
            },
            "files": [
                {
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "patch": file.patch[: self.patch_budget_per_file],
                }
                for file in context.files
            ],
            "rule_findings": [
                {
                    "severity": finding.severity.value,
                    "category": finding.category,
                    "file": finding.file,
                    "message": finding.message,
                    "evidence": finding.evidence,
                }
                for finding in risks
            ],
        }
        response = client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior code reviewer. Produce concise JSON with keys "
                        "summary and suggestions. Focus on evidence-backed PR review value, "
                        "avoid speculative claims, and prefer actionable advice."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        return ReviewReport(
            summary=_as_string_list(data.get("summary")),
            suggestions=_as_string_list(data.get("suggestions")),
            model_used=self.model,
        )

    def _fallback_summary(self, context: PRContext) -> list[str]:
        total_additions = sum(file.additions for file in context.files)
        total_deletions = sum(file.deletions for file in context.files)
        file_kinds = sorted(
            {file.filename.rsplit(".", 1)[-1] for file in context.files if "." in file.filename}
        )
        return [
            f"PR #{context.ref.number}: {context.title or 'Untitled PR'}",
            f"Changed {len(context.files)} files with +{total_additions}/-{total_deletions} lines.",
            f"Detected file types: {', '.join(file_kinds) if file_kinds else 'unknown'}.",
        ]

    def _fallback_suggestions(self, context: PRContext, risks: list) -> list[str]:
        suggestions: list[str] = []
        if risks:
            suggestions.append(
                "Review the listed risk findings first because they include direct diff evidence."
            )
        if len(context.files) > 20:
            suggestions.append(
                "Consider splitting this PR or requesting a file-by-file review plan."
            )
        if not suggestions:
            suggestions.append(
                "No high-confidence local risks were detected; review behavior and tests manually."
            )
        return suggestions


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []
