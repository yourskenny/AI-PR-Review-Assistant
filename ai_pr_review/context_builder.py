from __future__ import annotations

from ai_pr_review.models import (
    ChangedFileSummary,
    ContextFile,
    ContextPack,
    OmittedContextFile,
    PRContext,
    PRFile,
    RiskFinding,
)


def build_context_pack(
    context: PRContext,
    findings: list[RiskFinding],
    *,
    total_patch_budget: int = 12000,
    patch_budget_per_file: int = 3500,
) -> ContextPack:
    risk_files = {finding.file for finding in findings}
    ordered_files = sorted(context.files, key=lambda file: _file_priority(file, risk_files))
    included: list[ContextFile] = []
    omitted: list[OmittedContextFile] = []
    used_budget = 0

    for file in ordered_files:
        patch = file.patch or ""
        truncated = len(patch) > patch_budget_per_file
        budgeted_patch = patch[:patch_budget_per_file] if truncated else patch

        if included and used_budget + len(budgeted_patch) > total_patch_budget:
            omitted.append(
                OmittedContextFile(
                    filename=file.filename,
                    reason="total_patch_budget_exceeded",
                )
            )
            continue

        included.append(
            ContextFile(
                filename=file.filename,
                status=file.status,
                additions=file.additions,
                deletions=file.deletions,
                patch=budgeted_patch,
                truncated=truncated,
                truncation_reason="patch_budget_per_file_exceeded" if truncated else None,
            )
        )
        used_budget += len(budgeted_patch)

    return ContextPack(
        title=context.title,
        body=context.body,
        author=context.author,
        html_url=context.html_url,
        changed_files=[
            ChangedFileSummary(
                filename=file.filename,
                status=file.status,
                additions=file.additions,
                deletions=file.deletions,
            )
            for file in context.files
        ],
        files=included,
        omitted_files=omitted,
    )


def _file_priority(file: PRFile, risk_files: set[str]) -> tuple[int, int, int, str]:
    risk_rank = 0 if file.filename in risk_files else 1
    kind_rank = _kind_rank(file.filename)
    size_rank = -(file.additions + file.deletions)
    return (risk_rank, kind_rank, size_rank, file.filename)


def _kind_rank(filename: str) -> int:
    lowered = filename.lower()
    if _is_generated_or_vendor_file(lowered):
        return 3
    if _is_lockfile(lowered):
        return 2
    if lowered.startswith("docs/") or lowered.endswith((".md", ".rst", ".txt")):
        return 1
    return 0


def _is_lockfile(filename: str) -> bool:
    return filename.endswith(
        (
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "poetry.lock",
            "pipfile.lock",
        )
    )


def _is_generated_or_vendor_file(filename: str) -> bool:
    return (
        "/vendor/" in filename
        or filename.startswith("vendor/")
        or "/generated/" in filename
        or filename.endswith(".min.js")
        or filename.endswith(".min.css")
    )
