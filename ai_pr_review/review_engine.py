from __future__ import annotations

import json
import os
from dataclasses import asdict

from openai import OpenAI

from ai_pr_review.ai_client import AIClientError, parse_ai_review_response
from ai_pr_review.context_builder import build_context_pack
from ai_pr_review.models import PRContext, ReviewReport
from ai_pr_review.risk_rules import scan_risks


class ReviewEngine:
    def __init__(
        self,
        model: str | None = None,
        language: str = "zh",
        patch_budget_per_file: int = 3500,
        total_patch_budget: int = 12000,
    ) -> None:
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        self.language = _normalise_language(language)
        self.patch_budget_per_file = patch_budget_per_file
        self.total_patch_budget = total_patch_budget

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

        try:
            ai_report = self._ai_analyze(context, risks)
        except Exception as exc:
            fallback.ai_error = f"AI analysis failed: {exc}"
            return fallback
        if ai_report.summary:
            fallback.summary = ai_report.summary
        if ai_report.suggestions:
            fallback.suggestions = ai_report.suggestions
        if ai_report.review_checklist:
            fallback.review_checklist = ai_report.review_checklist
        fallback.model_used = self.model
        return fallback

    def _ai_analyze(self, context: PRContext, risks: list) -> ReviewReport:
        client = OpenAI()
        context_pack = build_context_pack(
            context,
            risks,
            patch_budget_per_file=self.patch_budget_per_file,
            total_patch_budget=self.total_patch_budget,
        )
        payload = {
            "language": self.language,
            "pull_request": {
                "title": context.title,
                "body": context.body[:2000],
                "author": context.author,
                "url": context.html_url,
            },
            "changed_files": [asdict(file) for file in context_pack.changed_files],
            "files": [asdict(file) for file in context_pack.files],
            "omitted_files": [asdict(file) for file in context_pack.omitted_files],
            "rule_findings": [
                {
                    "severity": finding.severity.value,
                    "category": finding.category,
                    "rule_id": finding.rule_id,
                    "confidence": finding.confidence.value,
                    "file": finding.file,
                    "line_start": finding.line_start,
                    "message": finding.message,
                    "evidence": finding.evidence,
                    "recommendation": finding.recommendation,
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
                        "You are a senior code reviewer. Return a JSON object with keys "
                        "summary, risk_assessments, review_suggestions, and review_checklist. "
                        "Use the requested language. Focus on evidence-backed PR review value. "
                        "Do not invent high-risk findings without a file, line, and evidence. "
                        "Prefer concise, actionable advice."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        data = parse_ai_review_response(raw)
        return ReviewReport(
            summary=data.summary,
            suggestions=data.suggestions,
            review_checklist=data.review_checklist,
            model_used=self.model,
        )

    def _fallback_summary(self, context: PRContext) -> list[str]:
        total_additions = sum(file.additions for file in context.files)
        total_deletions = sum(file.deletions for file in context.files)
        file_kinds = sorted(
            {file.filename.rsplit(".", 1)[-1] for file in context.files if "." in file.filename}
        )
        file_type_text = ", ".join(file_kinds) if file_kinds else "unknown"
        if self.language == "zh":
            return [
                f"PR #{context.ref.number}: {context.title or '未命名 PR'}",
                f"共变更 {len(context.files)} 个文件，+{total_additions}/-{total_deletions} 行。",
                f"检测到的文件类型：{file_type_text}。",
            ]
        return [
            f"PR #{context.ref.number}: {context.title or 'Untitled PR'}",
            f"Changed {len(context.files)} files with +{total_additions}/-{total_deletions} lines.",
            f"Detected file types: {file_type_text}.",
        ]

    def _fallback_suggestions(self, context: PRContext, risks: list) -> list[str]:
        suggestions: list[str] = []
        if risks:
            if self.language == "zh":
                suggestions.append("优先检查下列风险项，因为它们包含直接 diff 证据。")
            else:
                suggestions.append(
                    "Review the listed risk findings first because they include direct diff "
                    "evidence."
                )
        if len(context.files) > 20:
            if self.language == "zh":
                suggestions.append("该 PR 较大，建议拆分或提供逐文件 Review 计划。")
            else:
                suggestions.append(
                    "Consider splitting this PR or requesting a file-by-file review plan."
                )
        if not suggestions:
            if self.language == "zh":
                suggestions.append("未发现高置信本地风险；仍需人工检查行为和测试覆盖。")
            else:
                suggestions.append(
                    "No high-confidence local risks were detected; review behavior and tests "
                    "manually."
                )
        return suggestions


def _normalise_language(language: str) -> str:
    lowered = language.lower()
    if lowered in {"zh", "en"}:
        return lowered
    raise AIClientError("language must be either 'zh' or 'en'")
