import json
from pathlib import Path


def test_final_submission_materials_exist_and_are_linked_from_readme() -> None:
    readme = Path("README.md").read_text(encoding="utf-8-sig")

    assert "Demo 视频" in readme
    assert "测试方式" in readme
    assert "第三方参考与原创声明" in readme
    assert "docs/demo_script.md" in readme
    assert "docs/evaluation.md" in readme
    assert "docs/champion_sprint_plan_2026-05-29.md" in readme
    assert "examples/sample_report.md" in readme
    assert "examples/sample_report.json" in readme
    assert "examples/sample_report.sarif" in readme
    assert "待补充" in readme


def test_champion_evaluation_materials_exist() -> None:
    readme = Path("README.md").read_text(encoding="utf-8-sig")
    evaluation = Path("docs/evaluation.md").read_text(encoding="utf-8-sig")

    assert "赛题评分点对应表" in readme
    assert "评测证据" in readme
    assert "Champion evaluation" in evaluation
    assert "no-AI" in evaluation
    assert "误报" in evaluation
    assert "漏报" in evaluation


def test_sample_json_report_is_valid_submission_artifact() -> None:
    data = json.loads(Path("examples/sample_report.json").read_text(encoding="utf-8-sig"))

    assert data["pull_request"]["url"]
    assert data["review_brief"]["lines"]
    assert "findings" in data
    assert data["copy_ready_review_comment"]


def test_sample_sarif_report_is_valid_submission_artifact() -> None:
    data = json.loads(Path("examples/sample_report.sarif").read_text(encoding="utf-8-sig"))

    assert data["version"] == "2.1.0"
    assert data["runs"][0]["tool"]["driver"]["name"] == "AI PR Review Assistant"
    assert "results" in data["runs"][0]


def test_demo_script_covers_required_video_flow() -> None:
    script = Path("docs/demo_script.md").read_text(encoding="utf-8-sig")

    for required in [
        "作品定位",
        "无 AI Key 降级",
        "JSON 报告",
        "GitHub Action",
        "设计思路",
        "测试方式",
    ]:
        assert required in script
