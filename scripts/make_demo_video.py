from __future__ import annotations

import asyncio
import io
import json
import math
import re
import shutil
import subprocess
import unicodedata
import wave
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    import edge_tts
except ImportError as exc:  # pragma: no cover - user-facing script guard
    raise SystemExit("edge-tts is required. Run: python -m pip install edge-tts pillow") from exc


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "demo_video"
FRAMES = OUT / "frames"
AUDIO = OUT / "audio"
CLIPS = OUT / "clips"
WIDTH = 1920
HEIGHT = 1080
FPS = 30
ANIM_FPS = 15
VOICE = "zh-CN-YunxiNeural"
VOICE_RATE = "+8%"
SCENE_LEAD_IN = 0.18
SCENE_HOLD_AFTER = 0.18
CAPTION_GAP = 0.06
CAPTION_TAIL = 0.0


@dataclass(frozen=True)
class Scene:
    slug: str
    title: str
    subtitle: str
    narration: str
    bullets: list[str]
    visual: str
    duration: float


@dataclass
class CaptionCue:
    text: str
    audio_path: Path
    duration: float
    local_start: float = 0.0
    local_end: float = 0.0


@dataclass
class SceneTimeline:
    index: int
    scene: Scene
    start: float
    duration: float
    captions: list[CaptionCue] = field(default_factory=list)

    @property
    def end(self) -> float:
        return self.start + self.duration


SCENES = [
    Scene(
        "opening",
        "AI PR Review Assistant",
        "证据优先 · 低噪声 · 可离线降级",
        (
            "这是 AI PR Review Assistant，一个面向真实代码评审场景的 Reviewer Copilot。"
            "它不是把 diff 直接丢给大模型，而是先解析 Pull Request，绑定新增行证据，"
            "再生成可执行的评审简报。"
        ),
        ["GitHub PR 输入", "结构化 diff", "证据化 Review Brief"],
        "hero",
        24,
    ),
    Scene(
        "workflow",
        "从 PR URL 到证据链",
        "GitHub API → Patch Parser → Risk Rules → Review Brief",
        (
            "用户只需要指定 GitHub PR。系统通过 GitHub API 获取元数据和 patch，"
            "解析 hunk 和新增行号，再由规则和可选 scanner 输出带证据的 finding。"
        ),
        ["不 clone 整仓", "不执行 PR 代码", "每条风险保留文件、行号和证据"],
        "flow",
        28,
    ),
    Scene(
        "local_fallback",
        "无 AI Key 也能完整运行",
        "no-AI 模式证明核心链路不是 API Key 绑定 demo",
        (
            "即使没有模型密钥，本地规则仍然能生成 Markdown、JSON 和 SARIF 报告。"
            "模型只负责总结、解释和表达增强，核心证据链始终可以复现。"
        ),
        ["Markdown 报告", "JSON 结构化输出", "SARIF 生态集成"],
        "terminal",
        30,
    ),
    Scene(
        "risk_rules",
        "高信号风险识别",
        "安全、测试缺口、Review readiness 同一套 finding schema",
        (
            "系统覆盖动态执行、SQL 拼接、权限绕过、secret、migration 回滚说明、"
            "源码变更缺测试等高价值信号。每个 finding 都有严重级别、置信度、来源和修复建议。"
        ),
        ["security.sql_injection", "security.permission_bypass", "testing.source_without_tests"],
        "risk",
        32,
    ),
    Scene(
        "dashboard",
        "Dashboard 冠军演示",
        "一键加载 Champion Demo Case，现场不依赖 GitHub token",
        (
            "Dashboard 提供内置冠军样例。点击 Load demo case 后，可以看到 PR 摘要、"
            "最高风险、风险矩阵、Reviewer Action Plan，以及每条 finding 的 priority reason。"
        ),
        ["Champion Demo Case", "Reviewer Action Plan", "Finding priority reason"],
        "dashboard",
        38,
    ),
    Scene(
        "comments",
        "进入真实 PR 工作流",
        "Summary comment 默认低噪声，inline review 显式开启",
        (
            "在 GitHub 工作流中，默认只创建或更新一条 summary comment，避免刷屏。"
            "当需要行级证据时，手动开启 inline comments，只评论有文件路径和新增行号的 finding。"
        ),
        ["GitHub Action 示例", "Summary comment", "Optional inline review"],
        "github",
        28,
    ),
    Scene(
        "evaluation",
        "评测证据而不是口号",
        "命中、误报、漏报、响应速度和边界都写进 evaluation",
        (
            "项目包含冠军评测文档，固定场景覆盖命中、误报、漏报、no AI 与 AI assisted 分工。"
            "这让准确性、低噪声和响应速度都有可检查证据。"
        ),
        ["docs/evaluation.md", "62 个自动化测试", "pytest 与 ruff 门禁"],
        "evaluation",
        30,
    ),
    Scene(
        "architecture",
        "规则与 AI 分工清晰",
        "规则负责证据，AI 负责解释、归纳和建议表达",
        (
            "本项目的模型选择也有边界。默认使用低延迟代码模型，"
            "但高危 finding 必须来自文件、行号或明确证据。模型失败时自动降级，不中断评审。"
        ),
        ["模型职责边界", "上下文预算", "Omitted context 可追溯"],
        "architecture",
        28,
    ),
    Scene(
        "closing",
        "为第一名而设计",
        "完整闭环、可复现证据、现场稳定演示",
        (
            "最终作品覆盖赛题要求：PR 变更总结、风险代码识别、Review 建议生成，"
            "并在准确性、上下文理解、误报控制、响应速度和使用体验上给出完整证据。"
        ),
        ["CLI + Dashboard + GitHub Action", "Markdown + JSON + SARIF", "Evidence-first Reviewer Copilot"],
        "closing",
        30,
    ),
]


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise SystemExit("ffmpeg and ffprobe are required.")

    reset_output_dirs()
    timeline = asyncio.run(generate_voice_tracks(ffprobe))
    write_storyboard(timeline)
    render_poster_frames()
    total_duration = timeline[-1].end
    create_background_music(total_duration)
    create_animated_video(ffmpeg, timeline)
    create_voice_mix(ffmpeg, timeline)
    write_subtitles(timeline)
    mux_final_video(ffmpeg)
    write_manifest(ffprobe, timeline)


def reset_output_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for directory in (FRAMES, AUDIO, CLIPS):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
    for stale in (
        OUT / "visual_track.mp4",
        OUT / "ai_pr_review_demo_zh_1080p.mp4",
        OUT / "subtitles.srt",
        OUT / "subtitles.ass",
        OUT / "manifest.json",
        OUT / "thumbnail.png",
    ):
        stale.unlink(missing_ok=True)


async def generate_voice_tracks(ffprobe: str) -> list[SceneTimeline]:
    timelines: list[SceneTimeline] = []
    global_start = 0.0
    for scene_index, scene in enumerate(SCENES, start=1):
        caption_texts = split_caption_units(scene.narration)
        captions: list[CaptionCue] = []
        for caption_index, caption_text in enumerate(caption_texts, start=1):
            path = AUDIO / f"{scene_index:02d}_{caption_index:02d}_{scene.slug}.mp3"
            communicate = edge_tts.Communicate(
                caption_text,
                voice=VOICE,
                rate=VOICE_RATE,
                pitch="+0Hz",
                boundary="SentenceBoundary",
            )
            await communicate.save(str(path))
            captions.append(
                CaptionCue(
                    text=caption_text,
                    audio_path=path,
                    duration=probe_duration(ffprobe, path),
                )
            )

        local_cursor = SCENE_LEAD_IN
        for caption in captions:
            caption.local_start = local_cursor
            caption.local_end = local_cursor + caption.duration + CAPTION_TAIL
            local_cursor += caption.duration + CAPTION_GAP

        scene_duration = max(local_cursor - CAPTION_GAP + SCENE_HOLD_AFTER, 4.0)
        timelines.append(
            SceneTimeline(
                index=scene_index,
                scene=scene,
                start=global_start,
                duration=scene_duration,
                captions=captions,
            )
        )
        global_start += scene_duration
    return timelines


def write_storyboard(timeline: list[SceneTimeline]) -> None:
    storyboard = {
        "format": "1080p MP4",
        "voice": VOICE,
        "voice_rate": VOICE_RATE,
        "fps": FPS,
        "animation_fps": ANIM_FPS,
        "total_duration": timeline[-1].end,
        "scenes": [
            {
                "index": item.index,
                "slug": item.scene.slug,
                "title": item.scene.title,
                "subtitle": item.scene.subtitle,
                "duration": round(item.duration, 3),
                "start": round(item.start, 3),
                "captions": [
                    {
                        "start": round(item.start + cue.local_start, 3),
                        "end": round(item.start + cue.local_end, 3),
                        "text": cue.text,
                    }
                    for cue in item.captions
                ],
            }
            for item in timeline
        ],
    }
    (OUT / "storyboard.json").write_text(
        json.dumps(storyboard, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = ["# AI PR Review Assistant Demo Voiceover", ""]
    for item in timeline:
        lines.extend(
            [
                f"## {item.index}. {item.scene.title}",
                "",
                item.scene.narration,
                "",
            ]
        )
    (OUT / "voiceover_script.md").write_text("\n".join(lines), encoding="utf-8")


def render_poster_frames() -> None:
    for item in make_placeholder_timeline():
        frame = draw_scene(item.scene, item.index, 0.62)
        frame.save(FRAMES / f"{item.index:02d}_{item.scene.slug}.png")


def make_placeholder_timeline() -> list[SceneTimeline]:
    return [
        SceneTimeline(index=index, scene=scene, start=0.0, duration=scene.duration)
        for index, scene in enumerate(SCENES, start=1)
    ]


def create_background_music(total_duration: float) -> None:
    path = AUDIO / "background.wav"
    sample_rate = 44100
    total_seconds = math.ceil(total_duration + 0.8)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for n in range(total_seconds * sample_rate):
            t = n / sample_rate
            bar = int(t // 4) % 4
            root = [98.0, 116.54, 130.81, 87.31][bar]
            chord = (
                0.75 * math.sin(2 * math.pi * root * t)
                + 0.34 * math.sin(2 * math.pi * root * 1.5 * t)
                + 0.22 * math.sin(2 * math.pi * root * 2.0 * t)
            )
            pad = chord * (0.58 + 0.18 * math.sin(2 * math.pi * 0.09 * t))
            tick_phase = (t * 2.0) % 1.0
            tick = math.exp(-tick_phase * 22.0) * math.sin(2 * math.pi * 880 * t)
            shimmer = 0.08 * math.sin(2 * math.pi * 523.25 * t) * math.sin(2 * math.pi * 0.07 * t)
            fade = min(1.0, t / 2.5, max(0.0, (total_duration + 0.4 - t) / 2.5))
            value = int(1450 * fade * (pad + 0.14 * tick + shimmer))
            wav.writeframesraw(value.to_bytes(2, "little", signed=True))


def create_animated_video(ffmpeg: str, timeline: list[SceneTimeline]) -> None:
    clip_paths: list[Path] = []
    for item in timeline:
        clip_path = CLIPS / f"{item.index:02d}_{item.scene.slug}.mp4"
        clip_paths.append(clip_path)
        render_scene_clip(ffmpeg, item, clip_path)

    concat_file = OUT / "slides.ffconcat"
    lines = ["ffconcat version 1.0"]
    for clip_path in clip_paths:
        lines.append(f"file '{clip_path.as_posix()}'")
    concat_file.write_text("\n".join(lines), encoding="utf-8")
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-safe",
            "0",
            "-f",
            "concat",
            "-i",
            str(concat_file),
            "-c:v",
            "copy",
            str(OUT / "visual_track.mp4"),
        ]
    )


def render_scene_clip(ffmpeg: str, item: SceneTimeline, clip_path: Path) -> None:
    frame_count = max(1, math.ceil(item.duration * ANIM_FPS))
    command = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "image2pipe",
        "-framerate",
        str(ANIM_FPS),
        "-i",
        "-",
        "-vf",
        f"fps={FPS},format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(clip_path),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    for frame_index in range(frame_count):
        progress = frame_index / max(1, frame_count - 1)
        frame = draw_scene(item.scene, item.index, progress)
        buffer = io.BytesIO()
        frame.save(buffer, format="PNG")
        process.stdin.write(buffer.getvalue())
    process.stdin.close()
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    returncode = process.wait()
    if returncode != 0:
        raise SystemExit(f"ffmpeg failed while rendering {clip_path}: {stderr[-3000:]}")


def draw_scene(scene: Scene, index: int, progress: float) -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), "#101412")
    draw = ImageDraw.Draw(img)
    draw_background(draw, index, progress)
    title_font = font(76, bold=True)
    subtitle_font = font(34, bold=False)
    bullet_font = font(32, bold=False)
    small_font = font(22, bold=False)
    mono_font = font(24, bold=False, mono=True)

    title_reveal = stage(progress, 0.02, 0.16)
    title_y = int(128 - (1 - title_reveal) * 28)
    draw.text((96, 76), "AI PR REVIEW ASSISTANT", fill="#f0b35a", font=small_font)
    draw.text((96, title_y), scene.title, fill="#f6f1e6", font=title_font)
    draw.text((100, 230), scene.subtitle, fill="#99d6c6", font=subtitle_font)
    draw.text((96, 980), f"{index:02d} / {len(SCENES):02d}", fill="#8a978f", font=small_font)

    draw_scene_progress(draw, progress)
    draw_visual(draw, scene, mono_font, progress)
    draw_bullets(draw, scene.bullets, bullet_font, progress)
    faded = apply_edge_fade(img, progress)
    return faded.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))


def draw_background(draw: ImageDraw.ImageDraw, index: int, progress: float) -> None:
    for y in range(0, HEIGHT, 6):
        tone = int(18 + 20 * (y / HEIGHT))
        draw.rectangle((0, y, WIDTH, y + 6), fill=(tone, tone + 8, tone + 4, 255))
    motion = progress * 160
    for i in range(34):
        x = (i * 127 + index * 43 + motion * (0.6 + i % 3 * 0.18)) % WIDTH
        y = (i * 73 + index * 61 + motion * (0.3 + i % 4 * 0.14)) % HEIGHT
        color = (31, 111, 95, 150) if i % 2 else (181, 105, 44, 145)
        radius = 96 + 18 * math.sin(progress * math.tau + i)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=color, width=1)
    skew = int(progress * 80)
    for x in range(-240, WIDTH + 80, 80):
        draw.line((x + skew, 0, x + 240 + skew, HEIGHT), fill=(255, 255, 255, 18), width=1)


def draw_scene_progress(draw: ImageDraw.ImageDraw, progress: float) -> None:
    x0, y0, width = 96, 944, 720
    draw.rounded_rectangle((x0, y0, x0 + width, y0 + 8), radius=4, fill=(244, 241, 232, 60))
    draw.rounded_rectangle((x0, y0, x0 + int(width * progress), y0 + 8), radius=4, fill="#f0b35a")


def draw_visual(draw: ImageDraw.ImageDraw, scene: Scene, mono_font: ImageFont.ImageFont, progress: float) -> None:
    panel = (960, 318, 1780, 884)
    panel_reveal = stage(progress, 0.08, 0.24)
    panel_shift = int((1 - panel_reveal) * 70)
    panel_box = (panel[0] + panel_shift, panel[1], panel[2] + panel_shift, panel[3])
    draw.rounded_rectangle(panel_box, radius=28, fill="#f4f1e8", outline="#d8d1c2", width=2)
    scan_x = panel_box[0] + int((panel_box[2] - panel_box[0]) * progress)
    draw.line((scan_x, panel_box[1] + 18, scan_x, panel_box[3] - 18), fill=(27, 111, 93, 80), width=3)

    if scene.visual == "flow":
        draw_flow_visual(draw, mono_font, progress)
    elif scene.visual == "terminal":
        draw_terminal_visual(draw, mono_font, progress)
    elif scene.visual in {"dashboard", "hero"}:
        draw_dashboard_visual(draw, mono_font, progress)
    elif scene.visual == "risk":
        draw_risk_visual(draw, mono_font, progress)
    elif scene.visual == "github":
        draw_github_visual(draw, mono_font, progress)
    elif scene.visual == "evaluation":
        draw_evaluation_visual(draw, mono_font, progress)
    else:
        draw_architecture_visual(draw, mono_font, progress)


def draw_flow_visual(draw: ImageDraw.ImageDraw, mono_font: ImageFont.ImageFont, progress: float) -> None:
    items = ["PR URL", "GitHub API", "Patch Parser", "Risk Rules", "Review Brief"]
    centers: list[tuple[int, int]] = []
    for i, item in enumerate(items):
        reveal = stage(progress, 0.16 + i * 0.08, 0.28 + i * 0.08)
        x = int(1000 + (i % 2) * 360 - (1 - reveal) * 42)
        y = 360 + (i // 2) * 150
        centers.append((x + 150, y + 43))
        outline = "#f0b35a" if i == int(progress * len(items)) % len(items) else "#1b6f5d"
        draw.rounded_rectangle((x, y, x + 300, y + 86), radius=16, fill="#ffffff", outline=outline, width=3)
        draw.text((x + 24, y + 25), item, fill="#17201b", font=mono_font)
    for a, b in zip(centers, centers[1:]):
        draw.line((a[0], a[1], b[0], b[1]), fill="#1b6f5d", width=4)
    dot_path = centers[max(0, min(len(centers) - 1, int(progress * len(centers))))]
    pulse = 8 + int(4 * math.sin(progress * math.tau * 5))
    draw.ellipse((dot_path[0] - pulse, dot_path[1] - pulse, dot_path[0] + pulse, dot_path[1] + pulse), fill="#f0b35a")


def draw_terminal_visual(draw: ImageDraw.ImageDraw, mono_font: ImageFont.ImageFont, progress: float) -> None:
    draw.rectangle((1000, 362, 1740, 820), fill="#151b17")
    terminal_lines = [
        "> ai-pr-review analyze PR --no-ai",
        "Report written to demo-report.md",
        "> --format json",
        "reviewer_action_plan: 4 items",
        "> --format sarif",
        "SARIF 2.1.0 ready",
    ]
    visible_lines = min(len(terminal_lines), max(1, int(stage(progress, 0.16, 0.86) * len(terminal_lines)) + 1))
    for i, line in enumerate(terminal_lines[:visible_lines]):
        local = stage(progress, 0.12 + i * 0.11, 0.26 + i * 0.11)
        chars = max(1, int(len(line) * local))
        draw.text((1034, 400 + i * 58), line[:chars], fill="#e9f4ea", font=mono_font)
    cursor_y = 400 + (visible_lines - 1) * 58
    if int(progress * 12) % 2 == 0:
        draw.rectangle((1034 + 18 * min(len(terminal_lines[visible_lines - 1]), 34), cursor_y + 4, 1046 + 18 * min(len(terminal_lines[visible_lines - 1]), 34), cursor_y + 34), fill="#99d6c6")


def draw_dashboard_visual(draw: ImageDraw.ImageDraw, mono_font: ImageFont.ImageFont, progress: float) -> None:
    draw.rounded_rectangle((1008, 370, 1732, 808), radius=20, fill="#ffffff", outline="#1b6f5d", width=3)
    draw.text((1042, 410), "Champion Demo Case", fill="#b5692c", font=mono_font)
    draw.text((1042, 462), "Reviewer Action Plan", fill="#17201b", font=font(34, True))
    rows = ["Inspect auth/session.py", "Check SQL parameterization", "Request focused tests"]
    for i, text in enumerate(rows):
        reveal = stage(progress, 0.28 + i * 0.12, 0.42 + i * 0.12)
        y = 535 + i * 72
        x = int(1042 + (1 - reveal) * 70)
        draw.rounded_rectangle((x, y, x + 618, y + 46), radius=10, fill="#f4f1e8", outline="#d8d1c2")
        draw.text((x + 22, y + 10), text, fill="#17201b", font=mono_font)
    click = stage(progress, 0.12, 0.36)
    radius = 18 + int(26 * click)
    alpha = int(170 * (1 - click))
    draw.ellipse((1042 - radius, 410 - radius, 1042 + radius, 410 + radius), outline=(240, 179, 90, alpha), width=4)


def draw_risk_visual(draw: ImageDraw.ImageDraw, mono_font: ImageFont.ImageFont, progress: float) -> None:
    risks = [("HIGH", "security.sql_injection"), ("HIGH", "permission_bypass"), ("MED", "source_without_tests")]
    for i, (severity, rule) in enumerate(risks):
        reveal = stage(progress, 0.14 + i * 0.16, 0.28 + i * 0.16)
        y = int(390 + i * 120 + (1 - reveal) * 46)
        color = "#9b2d30" if severity == "HIGH" else "#b5692c"
        pulse_width = 4 + (2 if i == int(progress * 4) % 3 else 0)
        draw.rounded_rectangle((1010, y, 1710, y + 84), radius=14, fill="#ffffff", outline=color, width=pulse_width)
        draw.text((1038, y + 24), severity, fill=color, font=font(28, True))
        draw.text((1160, y + 26), rule, fill="#17201b", font=mono_font)
    heat = int(520 * stage(progress, 0.22, 0.86))
    draw.rounded_rectangle((1034, 770, 1034 + heat, 790), radius=10, fill="#f0b35a")
    draw.text((1034, 804), "risk signal confidence", fill="#6b716c", font=mono_font)


def draw_github_visual(draw: ImageDraw.ImageDraw, mono_font: ImageFont.ImageFont, progress: float) -> None:
    draw.text((1014, 380), "GitHub PR", fill="#17201b", font=font(42, True))
    cards = [
        ("Summary comment: one low-noise review brief", "#1b6f5d"),
        ("Inline review: explicit evidence-only comments", "#b5692c"),
    ]
    for i, (text, color) in enumerate(cards):
        reveal = stage(progress, 0.18 + i * 0.24, 0.36 + i * 0.24)
        y = int(460 + i * 160 + (1 - reveal) * 70)
        draw.rounded_rectangle((1016, y, 1720, y + 120), radius=14, fill="#ffffff", outline=color, width=3)
        draw.text((1044, y + 32), text, fill="#17201b", font=mono_font)
        if reveal > 0.75:
            draw.ellipse((1664, y + 38, 1700, y + 74), fill=color)


def draw_evaluation_visual(draw: ImageDraw.ImageDraw, mono_font: ImageFont.ImageFont, progress: float) -> None:
    rows = [("E1", "summary", "hit"), ("E2", "SQL risk", "hit"), ("E4", "migration", "review"), ("E7", "docs", "quiet")]
    for i, row in enumerate(rows):
        reveal = stage(progress, 0.12 + i * 0.12, 0.28 + i * 0.12)
        y = int(382 + i * 84)
        draw.rounded_rectangle((1012, y, 1700, y + 56), radius=10, fill="#ffffff", outline="#d8d1c2")
        draw.text((1040, y + 15), f"{row[0]}  {row[1]}", fill="#17201b", font=mono_font)
        bar = int(260 * reveal)
        draw.rounded_rectangle((1388, y + 17, 1388 + bar, y + 39), radius=11, fill="#1b6f5d")
        if reveal > 0.92:
            draw.text((1608, y + 15), row[2], fill="#b5692c", font=mono_font)


def draw_architecture_visual(draw: ImageDraw.ImageDraw, mono_font: ImageFont.ImageFont, progress: float) -> None:
    labels = [("Rules", "evidence"), ("AI", "summary"), ("Fallback", "no interruption")]
    for i, (left, right) in enumerate(labels):
        reveal = stage(progress, 0.14 + i * 0.16, 0.32 + i * 0.16)
        y = 420 + i * 100
        draw.rounded_rectangle((1030, y, 1300, y + 64), radius=14, fill="#ffffff", outline="#1b6f5d", width=3)
        draw.text((1060, y + 18), left, fill="#17201b", font=mono_font)
        end_x = 1390 + int(250 * reveal)
        draw.line((1300, y + 32, end_x, y + 32), fill="#f0b35a", width=6)
        draw.rounded_rectangle((1450, y, 1710, y + 64), radius=14, fill="#ffffff", outline="#b5692c", width=3)
        draw.text((1480, y + 18), right, fill="#17201b", font=mono_font)


def draw_bullets(draw: ImageDraw.ImageDraw, bullets: list[str], bullet_font: ImageFont.ImageFont, progress: float) -> None:
    x = 120
    y = 360
    active = int(stage(progress, 0.18, 0.82) * max(1, len(bullets)))
    for i, bullet in enumerate(bullets):
        reveal = stage(progress, 0.12 + i * 0.08, 0.28 + i * 0.08)
        row_x = int(x - (1 - reveal) * 90)
        outline = "#f0b35a" if i == min(active, len(bullets) - 1) else "#d8d1c2"
        draw.rounded_rectangle((row_x, y, row_x + 720, y + 76), radius=18, fill="#f4f1e8", outline=outline)
        draw.ellipse((row_x + 24, y + 26, row_x + 44, y + 46), fill="#1b6f5d")
        draw.text((row_x + 70, y + 21), bullet, fill="#17201b", font=bullet_font)
        y += 106


def apply_edge_fade(img: Image.Image, progress: float) -> Image.Image:
    fade_in = stage(progress, 0.0, 0.08)
    fade_out = 1 - stage(progress, 0.92, 1.0)
    opacity = min(fade_in, fade_out)
    if opacity >= 0.999:
        return img
    overlay = Image.new("RGBA", img.size, (16, 20, 18, int(255 * (1 - opacity))))
    return Image.alpha_composite(img, overlay)


def create_voice_mix(ffmpeg: str, timeline: list[SceneTimeline]) -> None:
    captions = [(item, cue) for item in timeline for cue in item.captions]
    parts: list[str] = []
    filter_parts: list[str] = []
    for input_index, (item, cue) in enumerate(captions):
        parts.extend(["-i", str(cue.audio_path)])
        delay_ms = int((item.start + cue.local_start) * 1000)
        filter_parts.append(f"[{input_index}:a]adelay={delay_ms}|{delay_ms}[a{input_index}]")
    inputs = "".join(f"[a{index}]" for index in range(len(captions)))
    filter_complex = ";".join(filter_parts) + f";{inputs}amix=inputs={len(captions)}:duration=longest:normalize=0[voice]"
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            *parts,
            "-filter_complex",
            filter_complex,
            "-map",
            "[voice]",
            str(AUDIO / "voice_mix.wav"),
        ]
    )


def write_subtitles(timeline: list[SceneTimeline]) -> None:
    srt_lines: list[str] = []
    ass_events: list[str] = []
    subtitle_index = 1
    for item in timeline:
        for cue in item.captions:
            start = item.start + cue.local_start
            end = item.start + cue.local_end
            subtitle = wrap_subtitle(sanitize_subtitle_text(cue.text), max_width=34)
            srt_lines.extend(
                [
                    str(subtitle_index),
                    f"{srt_time(start)} --> {srt_time(end)}",
                    subtitle,
                    "",
                ]
            )
            ass_events.append(
                "Dialogue: 0,"
                f"{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{ass_escape(subtitle)}"
            )
            subtitle_index += 1

    (OUT / "subtitles.srt").write_text("\n".join(srt_lines), encoding="utf-8")
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,40,&H00F8F1E8,&H000000FF,&HAA101412,&HAA101412,0,0,0,0,100,100,0,0,1,2,1,2,130,130,68,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    (OUT / "subtitles.ass").write_text(ass_header + "\n".join(ass_events), encoding="utf-8")


def mux_final_video(ffmpeg: str) -> None:
    subtitle_path = str(OUT / "subtitles.ass").replace("\\", "/").replace(":", "\\:")
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(OUT / "visual_track.mp4"),
            "-i",
            str(AUDIO / "voice_mix.wav"),
            "-i",
            str(AUDIO / "background.wav"),
            "-filter_complex",
            f"[0:v]subtitles='{subtitle_path}'[v];[1:a]volume=1.0[voice];[2:a]volume=0.45[music];"
            "[voice][music]amix=inputs=2:duration=longest:dropout_transition=2[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(OUT / "ai_pr_review_demo_zh_1080p.mp4"),
        ]
    )


def write_manifest(ffprobe: str, timeline: list[SceneTimeline]) -> None:
    video = OUT / "ai_pr_review_demo_zh_1080p.mp4"
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-show_streams",
            "-of",
            "json",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    manifest = json.loads(result.stdout)
    manifest["timeline"] = {
        "scenes": len(timeline),
        "captions": sum(len(item.captions) for item in timeline),
        "total_duration": round(timeline[-1].end, 3),
        "gap_policy": {
            "scene_lead_in": SCENE_LEAD_IN,
            "scene_hold_after": SCENE_HOLD_AFTER,
            "caption_gap": CAPTION_GAP,
        },
    }
    manifest["deliverables"] = {
        "video": str(video),
        "subtitles_srt": str(OUT / "subtitles.srt"),
        "subtitles_ass": str(OUT / "subtitles.ass"),
        "voice_mix": str(AUDIO / "voice_mix.wav"),
        "background_music": str(AUDIO / "background.wav"),
        "storyboard": str(OUT / "storyboard.json"),
        "voiceover_script": str(OUT / "voiceover_script.md"),
        "thumbnail": str(OUT / "thumbnail.png"),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def split_caption_units(text: str) -> list[str]:
    text = sanitize_subtitle_text(re.sub(r"\s+", " ", text.strip()))
    parts = [part.strip() for part in re.split(r"(?<=[。！？；，])", text) if part.strip()]
    units: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current}{part}" if current else part
        if current and display_width(candidate) > 34:
            units.append(current)
            current = part
        else:
            current = candidate
    if current:
        units.append(current)

    refined: list[str] = []
    for unit in units:
        refined.extend(split_long_caption(unit, max_width=38))
    return refined


def split_long_caption(text: str, max_width: int) -> list[str]:
    if display_width(text) <= max_width:
        return [text]
    chunks: list[str] = []
    current = ""
    for token in tokenize_for_subtitle(text):
        candidate = join_subtitle_token(current, token)
        if current and display_width(candidate) > max_width:
            chunks.append(current)
            current = token
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def wrap_subtitle(text: str, max_width: int) -> str:
    lines: list[str] = []
    current = ""
    for token in tokenize_for_subtitle(text):
        candidate = join_subtitle_token(current, token)
        if current and is_punctuation(token):
            current = candidate
            continue
        if current and display_width(candidate) > max_width:
            lines.append(current)
            current = token
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines[:2])


def tokenize_for_subtitle(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_.:+-]+|[\u4e00-\u9fff]|[^\u4e00-\u9fffA-Za-z0-9_.:+\-\s]+", text)


def join_subtitle_token(left: str, token: str) -> str:
    if not left:
        return token
    separator = " " if needs_space(left, token) else ""
    return f"{left}{separator}{token}"


def sanitize_subtitle_text(text: str) -> str:
    return (
        text.replace("/", "、")
        .replace("\\", "")
        .replace("→", "到")
        .replace("  ", " ")
        .strip()
    )


def ass_escape(text: str) -> str:
    cleaned = text.replace("{", "(").replace("}", ")").replace("\\", "")
    return cleaned.replace("\n", r"\N")


def probe_duration(ffprobe: str, path: Path) -> float:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.ImageFont:
    candidates: list[str] = []
    if mono:
        candidates.extend(["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf"])
    elif bold:
        candidates.extend(["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/segoeuib.ttf"])
    else:
        candidates.extend(["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"])
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def stage(progress: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0 if progress >= end else 0.0
    x = clamp((progress - start) / (end - start), 0.0, 1.0)
    return x * x * (3 - 2 * x)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def needs_space(left: str, right: str) -> bool:
    if not left:
        return False
    return left[-1].isascii() and left[-1].isalnum() and right[:1].isascii() and right[:1].isalnum()


def is_punctuation(text: str) -> bool:
    return bool(text) and all(unicodedata.category(char).startswith("P") for char in text)


def display_width(text: str) -> int:
    width = 0
    for char in text:
        if char == "\n":
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return width


def srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    h, rem = divmod(millis, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ass_time(seconds: float) -> str:
    centis = int(round(seconds * 100))
    h, rem = divmod(centis, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def run(command: list[str]) -> None:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-4000:]
        raise SystemExit(
            f"Command failed with exit code {result.returncode}: {' '.join(command)}\n{tail}"
        )


if __name__ == "__main__":
    main()
