import json
import subprocess
from pathlib import Path

from ai_pr_review.models import (
    Confidence,
    FindingSource,
    PRContext,
    PRFile,
    PullRequestRef,
    Severity,
)


def test_bandit_scanner_maps_json_results_to_risk_findings(monkeypatch) -> None:
    from ai_pr_review.scanners.bandit import BanditScanner

    def fake_run(*args, **kwargs):
        scan_root = Path(args[0][2])
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout=json.dumps(
                {
                    "results": [
                        {
                            "filename": str(scan_root / "src/app.py"),
                            "line_number": 12,
                            "test_id": "B307",
                            "issue_severity": "HIGH",
                            "issue_confidence": "HIGH",
                            "issue_text": "Use of possibly insecure function.",
                            "code": "12 eval(user)",
                            "more_info": "https://bandit.readthedocs.io/",
                        }
                    ]
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    findings = BanditScanner().scan(_context())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "bandit.B307"
    assert finding.severity == Severity.HIGH
    assert finding.confidence == Confidence.HIGH
    assert finding.source == FindingSource.SCANNER
    assert finding.file == "src/app.py"
    assert finding.line_start == 12
    assert finding.recommendation == "Review the Bandit finding and apply the safer alternative."


def test_bandit_scanner_skips_when_command_is_missing(monkeypatch) -> None:
    from ai_pr_review.scanners.bandit import BanditScanner

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("bandit")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert BanditScanner().scan(_context()) == []


def test_review_engine_merges_scanner_findings() -> None:
    from ai_pr_review.review_engine import ReviewEngine

    class FakeScanner:
        def scan(self, context: PRContext):
            return [
                _scanner_finding(
                    rule_id="scanner.demo",
                    file="src/app.py",
                )
            ]

    report = ReviewEngine(scanners=[FakeScanner()]).analyze(_context(), use_ai=False)

    assert any(finding.rule_id == "scanner.demo" for finding in report.risks)


def _context() -> PRContext:
    return PRContext(
        ref=PullRequestRef("owner", "repo", 1),
        title="demo",
        body="",
        author="dev",
        html_url="https://github.com/owner/repo/pull/1",
        files=[
            PRFile(
                filename="src/app.py",
                status="modified",
                additions=1,
                deletions=0,
                patch="@@ -1,1 +1,1 @@\n+eval(user)\n",
            )
        ],
    )


def _scanner_finding(rule_id: str, file: str):
    from ai_pr_review.models import RiskFinding

    return RiskFinding(
        severity=Severity.MEDIUM,
        category="scanner",
        file=file,
        message="scanner finding",
        evidence="scanner evidence",
        rule_id=rule_id,
        confidence=Confidence.MEDIUM,
        recommendation="Review scanner output.",
        source=FindingSource.SCANNER,
        line_start=1,
        line_end=1,
    )
