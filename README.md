# AI PR Review Assistant

AI PR Review Assistant 是一个面向比赛作品的 GitHub Pull Request 代码评审工具。用户提供一个 GitHub PR URL，工具自动获取 PR 元数据和 diff，生成变更总结、风险代码识别和 Review 建议，帮助开发者更快完成高质量评审。

## 赛题对应能力

- PR 变更总结：按文件和补丁内容提炼本次变更目的、影响面和需要重点关注的模块。
- 风险代码识别：识别潜在安全、可靠性、性能、可维护性和测试缺口风险，并给出文件与行号证据位置。
- Review 建议生成：输出可以直接用于 PR Review 的建议，包含规则 ID、严重级别、置信度、原因和可操作修复方向。
- 误报控制：先用规则引擎定位高置信信号，再让模型基于上下文解释风险；默认保留证据片段，避免空泛判断。
- 响应速度：先拉取 GitHub API 的结构化 PR 数据，只截取必要 diff 和文件上下文，避免整仓扫描。

## 快速开始

### 1. 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### 2. 配置 GitHub 访问

公共仓库可以直接分析。私有仓库或更高限额需要配置 GitHub token：

```powershell
$env:GITHUB_TOKEN = "ghp_xxx"
```

### 3. 可选：启用模型分析

没有模型密钥时，工具会使用本地启发式分析，适合演示核心流程。配置 OpenAI API Key 后会启用 AI 综合分析：

```powershell
$env:OPENAI_API_KEY = "sk-xxx"
$env:OPENAI_MODEL = "gpt-4.1-mini"
```

模型返回非法 JSON 或 API 调用失败时，工具会自动降级到本地规则报告，不会让 CLI 因模型失败中断。

### 4. 分析 PR

```powershell
ai-pr-review analyze https://github.com/owner/repo/pull/123
```

指定模型和报告语言：

```powershell
ai-pr-review analyze https://github.com/owner/repo/pull/123 --model gpt-4.1-mini --language zh
```

生成 Markdown 或 JSON 报告文件：

```powershell
ai-pr-review analyze https://github.com/owner/repo/pull/123 --no-ai --format markdown --output analysis-output\report.md
ai-pr-review analyze https://github.com/owner/repo/pull/123 --no-ai --format json --output analysis-output\report.json
```

启动本地图形化 Review Dashboard：

```powershell
ai-pr-review dashboard --host 127.0.0.1 --port 8765
```

打开 `http://127.0.0.1:8765` 后输入 GitHub PR URL，即可在浏览器中查看 PR 摘要、风险矩阵、证据片段、Markdown Review Comment 和 JSON 报告。Dashboard 复用同一套分析引擎，适合 demo 展示和人工快速浏览；CLI 仍然是 CI / GitHub Action 的稳定入口。

使用 JSON 配置文件控制过滤、预算和规则：

```powershell
ai-pr-review analyze https://github.com/owner/repo/pull/123 --config .ai-pr-review.json
```

`.ai-pr-review.json` 示例：

```json
{
  "language": "zh",
  "model": "gpt-4.1-mini",
  "enable_ai": true,
  "max_files": 50,
  "patch_budget_per_file": 3500,
  "total_budget": 12000,
  "include_patterns": ["src/*.py", "tests/*.py"],
  "ignore_patterns": ["vendor/*", "*.min.js"],
  "enabled_rules": null,
  "min_severity": "low"
}
```

将报告写回 PR 讨论区或生成证据绑定的行级 Review：

```powershell
$env:GITHUB_TOKEN = "ghp_xxx"
ai-pr-review analyze https://github.com/owner/repo/pull/123 --no-ai --comment
ai-pr-review analyze https://github.com/owner/repo/pull/123 --no-ai --inline-comments
```

`--comment` 会查找带有 `<!-- ai-pr-review-assistant -->` 标记的 bot comment，存在则更新，不存在则创建。`--inline-comments` 会创建一条 GitHub PR Review，只把有文件路径和新增行号证据的 finding 转成行级评论；没有可定位 finding 时会跳过。默认仍不自动评论，CI 示例也继续使用单条 summary comment，避免大量行级评论干扰 Review。

可选启用外部扫描器：

```powershell
python -m pip install bandit
ai-pr-review analyze https://github.com/owner/repo/pull/123 --no-ai --enable-scanners bandit
```

外部扫描器不是默认依赖。当前 Bandit 适配器只在本地临时目录中扫描 PR 新增的 Python 内容，命令不存在或无输出时会跳过，不影响基础规则和 AI 报告。

也可以直接用 Python 模块运行：

```powershell
python -m ai_pr_review.cli analyze https://github.com/owner/repo/pull/123
```

## 输出示例

完整样例报告见：

- [Markdown 样例报告](examples/sample_report.md)
- [JSON 样例报告](examples/sample_report.json)

```markdown
# AI PR Review Report

## Change Summary
- This PR changes authentication middleware and session refresh behavior.

## Review Brief
- 变更规模：3 个文件，+120/-30 行。
- 最高风险：high/high security at auth/session.py:42

## Findings with Evidence
### HIGH security: auth/session.py:42
- Rule: `security.dynamic_code_execution`
- Confidence: `high`
- Add an explicit expired-token test around the refresh branch.
```

## 系统设计

### 数据流

1. 解析用户输入的 GitHub PR URL，得到 owner、repo 和 PR 编号。
2. 通过 GitHub REST API 获取 PR 标题、描述、文件列表和 patch。
3. 对 diff 做上下文预算控制，保留文件名、变更状态、增删行数和关键补丁片段。
4. 本地风险扫描器先发现高置信风险信号，如危险命令、宽泛异常处理、缺失测试和敏感字段。
5. 如果配置了模型，将结构化上下文发送给模型生成总结、风险和建议；否则使用本地报告器输出可解释结果。

### 模型选择

默认建议使用 `gpt-4.1-mini` 这类低延迟、成本可控且代码理解能力足够的模型处理常规 PR。对于大型重构、跨语言改动或安全敏感 PR，可以切换到更强模型。工具将模型调用封装在 `ReviewEngine` 后面，后续可以替换为本地模型、企业网关或多模型投票。

### 上下文获取方式

工具优先使用 GitHub API 的 PR 文件级 diff，而不是克隆整个仓库。这样可以减少网络和计算开销，也更贴近 Review 的真实入口。上下文预算策略包括：

- 文件级摘要：保留文件名、状态、增删行数。
- patch 截断：每个文件只截取预算内补丁，避免超长 PR 阻塞响应。
- 风险优先：命中风险规则的文件优先进入模型上下文。
- 省略记录：超过总预算的文件会记录省略原因，便于后续报告解释上下文边界。
- 可追溯证据：每条风险建议都尽量保留文件和片段，便于人工确认。

### 误报与漏报控制

本项目采用规则和模型结合的方式。规则层适合发现稳定、高置信的工程风险；模型层负责解释影响、聚合上下文和生成自然语言建议。报告中保留严重级别和证据片段，Review 人可以快速判断是否采纳。未来版本可以加入历史 PR 反馈，把“被接受的建议”和“被忽略的建议”回流到排序策略中。

### 外部扫描器

`--enable-scanners bandit` 可把 Bandit 的 JSON 结果合并到同一个 finding 结构中，保留 `file`、`line`、`rule_id`、`severity`、`confidence`、`evidence` 和 `recommendation`。扫描器接口是可选增强，目标是接入成熟工具的高置信发现，而不是复制它们的规则实现。

### GitHub Action 集成

仓库提供 [GitHub Action 示例](examples/github-action.yml)，可在 PR opened / synchronize / reopened 时运行分析并发布单条 summary comment。CLI 也支持手动使用 `--inline-comments` 生成证据绑定的行级 Review。示例使用最小权限：

- `contents: read`
- `pull-requests: write`
- `issues: write`

安全边界：

- 示例默认跳过 fork PR，避免把仓库 secrets 暴露给不可信代码。
- 默认不执行 PR 中的代码，只读取 GitHub API 提供的 PR 元数据和 patch。
- 自动化 workflow 默认只发布或更新一条 summary comment；行级评论需要显式开启，并且只针对有新增行号证据的 finding。

## 测试方式

本仓库使用 `pytest` 和 `ruff` 做基础质量门禁：

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

端到端 smoke：

```powershell
python -m ai_pr_review.cli analyze https://github.com/openai/openai-python/pull/123 --no-ai --format markdown --output analysis-output\demo-report.md
python -m ai_pr_review.cli analyze https://github.com/openai/openai-python/pull/123 --no-ai --format json --output analysis-output\demo-report.json
```

## 项目结构

```text
ai_pr_review/
  cli.py              # 命令行入口
  config.py           # JSON 配置、文件过滤和分析参数
  dashboard.py        # 本地 Web dashboard 和 JSON API
  github_commenter.py # PR summary comment 与行级 Review 创建
  github_client.py    # GitHub PR 数据获取
  models.py           # 核心数据结构
  patch_parser.py     # patch hunk 和新增行号解析
  context_builder.py  # 上下文预算控制和省略记录
  ai_client.py        # AI JSON 解析和降级
  review_engine.py    # 分析编排和模型调用
  risk_rules.py       # 本地风险规则
  report.py           # Markdown / JSON 报告生成
  scanners/
    base.py           # 外部扫描器协议
    bandit.py         # 可选 Bandit JSON 适配器
  static/
    dashboard.css     # Dashboard 样式
  templates/
    dashboard.html    # Dashboard 页面模板
examples/
  github-action.yml
tests/
  test_pr_url.py
  test_patch_parser.py
  test_context_builder.py
  test_review_engine.py
  test_risk_rules.py
  test_report.py
  test_dashboard.py
```

## 未来扩展

- GitHub App 集成：在 PR 页面自动评论，支持增量 Review。
- 仓库上下文增强：按 import、调用链和 CODEOWNERS 拉取相关文件。
- 低噪声排序：结合历史反馈、测试覆盖率和运行时指标调整风险优先级。
- 多语言规则库：为 Python、TypeScript、Go、Java 分别维护高置信规则。
- 企业部署：支持私有模型网关、审计日志和数据脱敏策略。

## Demo 视频

Demo 视频链接：待补充。

录制脚本见 [Demo 视频脚本](docs/demo_script.md)。视频应覆盖作品定位、无 AI Key 降级、Markdown / JSON 报告、GitHub Action、设计思路和测试方式。

## 第三方参考与原创声明

本项目主体为原创 Python CLI 实现，核心原创部分包括：

- GitHub PR metadata / patch 获取和统一数据模型。
- patch hunk / 新增行号解析。
- 规则优先的低噪声 finding 结构。
- 上下文预算控制和省略记录。
- AI JSON fallback 与 Markdown / JSON Review Brief。
- 单条 GitHub summary comment 与可选行级 Review comment。

项目依赖列在 `pyproject.toml`：`openai`、`requests`、`typer`、`rich`，开发依赖为 `pytest` 和 `ruff`。可选外部 scanner 参考并适配 Bandit 的 JSON 输出格式，但 Bandit 不作为默认依赖，也没有复制其规则实现。

设计上参考了 PR-Agent、reviewdog、Claude Code Security Review、Semgrep、Bandit、Gitleaks、CodeQL、Danger JS、OpenReview、Kodus 等成熟项目的公开产品思想；本仓库没有 fork 或导入这些项目的大段代码。

## 比赛提交说明

本仓库重点展示一个可运行的 AI PR Review 工具闭环：指定 PR、获取变更、构造上下文、识别风险并生成建议。实现上优先保证端到端清晰、报告可解释和扩展边界明确，后续可以在此基础上接入更深的代码图谱和自动评论能力。

后续建设以 [AI PR Review Assistant 主建设方案](docs/master_build_plan.md) 为主要依据，优先落实低噪声 Review、证据链、规则与 AI 分工、可离线降级和小 PR 持续交付。

赛题原文已保存到 [赛题原文](docs/problem_statement.md)，用于持续校验实现范围是否偏离题面要求。

官方 FAQ 中与提交规范、评分重点和作品有效性相关的信息已整理到 [官方 FAQ 关键信息摘录](docs/competition_faq_notes.md)。后续迭代本仓库时，应优先按该文档检查 PR、commit、README 和 demo 材料是否满足规则。

本阶段功能收口、验证口径和后续建议见 [2026-05-29 阶段收尾总结](docs/stage_summary_2026-05-29.md)。
