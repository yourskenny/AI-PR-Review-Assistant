from ai_pr_review.context_builder import build_context_pack
from ai_pr_review.models import (
    Confidence,
    FindingSource,
    PRContext,
    PRFile,
    PullRequestRef,
    RiskFinding,
    Severity,
)


def test_build_context_pack_prioritizes_files_with_risk_findings() -> None:
    context = _context(
        [
            PRFile("docs/readme.md", "modified", 1, 0, "@@ -1,1 +1,1 @@\n+docs\n"),
            PRFile("src/auth.py", "modified", 1, 0, "@@ -1,1 +1,1 @@\n+eval(user)\n"),
        ]
    )
    findings = [_finding("src/auth.py")]

    pack = build_context_pack(context, findings, total_patch_budget=500, patch_budget_per_file=500)

    assert [file.filename for file in pack.files] == ["src/auth.py", "docs/readme.md"]
    assert pack.omitted_files == []


def test_build_context_pack_records_omitted_files_when_total_budget_is_exceeded() -> None:
    context = _context(
        [
            PRFile("src/a.py", "modified", 1, 0, "@@ -1,1 +1,1 @@\n+" + "a" * 40),
            PRFile("src/b.py", "modified", 1, 0, "@@ -1,1 +1,1 @@\n+" + "b" * 40),
        ]
    )

    pack = build_context_pack(context, [], total_patch_budget=35, patch_budget_per_file=100)

    assert [file.filename for file in pack.files] == ["src/a.py"]
    assert [(file.filename, file.reason) for file in pack.omitted_files] == [
        ("src/b.py", "total_patch_budget_exceeded")
    ]


def test_build_context_pack_truncates_large_patch_per_file() -> None:
    context = _context([PRFile("src/a.py", "modified", 1, 0, "0123456789" * 10)])

    pack = build_context_pack(context, [], total_patch_budget=1000, patch_budget_per_file=12)

    assert pack.files[0].patch == "012345678901"
    assert pack.files[0].truncated is True
    assert pack.files[0].truncation_reason == "patch_budget_per_file_exceeded"


def test_build_context_pack_deprioritizes_docs_lockfiles_and_vendor_files() -> None:
    context = _context(
        [
            PRFile("package-lock.json", "modified", 1, 0, "@@ -1,1 +1,1 @@\n+lock\n"),
            PRFile("vendor/generated.min.js", "modified", 1, 0, "@@ -1,1 +1,1 @@\n+min\n"),
            PRFile("docs/guide.md", "modified", 1, 0, "@@ -1,1 +1,1 @@\n+docs\n"),
            PRFile("src/app.py", "modified", 1, 0, "@@ -1,1 +1,1 @@\n+code\n"),
        ]
    )

    pack = build_context_pack(context, [], total_patch_budget=1000, patch_budget_per_file=500)

    assert [file.filename for file in pack.files] == [
        "src/app.py",
        "docs/guide.md",
        "package-lock.json",
        "vendor/generated.min.js",
    ]


def test_build_context_pack_retains_pr_metadata_and_changed_file_summary() -> None:
    context = _context([PRFile("src/app.py", "added", 2, 0, "@@ -0,0 +1,2 @@\n+a\n+b\n")])

    pack = build_context_pack(context, [], total_patch_budget=1000, patch_budget_per_file=500)

    assert pack.title == "demo"
    assert pack.author == "dev"
    assert pack.html_url == "https://github.com/owner/repo/pull/1"
    assert pack.changed_files[0].filename == "src/app.py"
    assert pack.changed_files[0].status == "added"
    assert pack.changed_files[0].additions == 2


def _context(files: list[PRFile]) -> PRContext:
    return PRContext(
        ref=PullRequestRef("owner", "repo", 1),
        title="demo",
        body="body",
        author="dev",
        html_url="https://github.com/owner/repo/pull/1",
        files=files,
    )


def _finding(filename: str) -> RiskFinding:
    return RiskFinding(
        severity=Severity.HIGH,
        category="security",
        file=filename,
        message="risk",
        evidence="eval(user)",
        rule_id="security.dynamic_code_execution",
        confidence=Confidence.HIGH,
        recommendation="Avoid dynamic execution.",
        source=FindingSource.RULE,
        line_start=1,
        line_end=1,
    )
