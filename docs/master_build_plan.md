# AI PR Review Assistant 主建设方案

本文是本仓库后续建设的主要依据。它基于赛题原文、官方 FAQ、当前代码状态，以及对成熟 PR Review / AI Review 项目的参考判断。后续实现、PR 拆分、README 表达和 demo 脚本都应优先对齐本文。

## 总体判断

不要把作品做成 PR-Agent、CodeRabbit 或大型 AI Review 平台的缩小复制品。72 小时作品最需要的是一个能稳定跑通、能清晰演示、低噪声、证据可追溯、规则与 AI 结合的 PR Review 助手。

评分上最划算的方向是：

- 端到端闭环完整。
- 报告质量高。
- 工程过程规范。
- 创新点表达清楚。
- 不堆很多难以稳定演示的功能。

本项目的真正目标不是证明 AI 能替代人类 Reviewer，而是做一个能进入真实开发流程的 Reviewer Copilot：先帮人快速理解 PR，再把最值得人工关注的风险按证据排序，最后给出可复制到 PR Review 里的建议。

## 当前仓库理解

当前仓库已经具备最小闭环：

- 用户输入 GitHub PR URL。
- CLI 通过 GitHub API 获取 PR 元数据和文件 patch。
- 本地规则识别高置信风险。
- 可选 OpenAI 模型生成总结和建议。
- Markdown 报告输出 PR 摘要、风险发现和 Review 建议。
- 无模型 key 时可以用 `--no-ai` 或本地 fallback 运行。

当前短板：

- CLI 缺少 JSON 输出、语言选项、模型选项和模式选项。
- patch 还没有结构化 hunk / 行号解析。
- finding 缺少 rule id、行号、置信度、修复建议和来源。
- 规则数量少，主要是正则，缺少语言和文件类型感知。
- AI 只生成 summary / suggestions，没有结构化风险 schema 和强健 fallback。
- 报告还不够像真实 Reviewer 工作台，缺少风险矩阵、Review brief、检查清单和上下文省略说明。
- 测试还需要覆盖 GitHub client mock、patch parser、context builder、report snapshot 和 AI fallback。

## 外部参考取舍

可以参考成熟项目的思想，但不要直接 fork 大型项目作为主体。FAQ 明确要求说明依赖和原创部分，也提醒复用代码需要注明来源。本作品的原创主体应是轻量 Python CLI、PR 上下文聚合、低噪声排序、证据绑定和 AI 解释。

### PR-Agent

PR-Agent 是最接近赛题的开源项目之一，值得学习：

- PR 压缩策略。
- 动态上下文和 token 预算。
- 模型 fallback。
- provider 抽象。
- 增量 review。
- diff 添加上下文、行号、主语言排序、预算超限压缩和未处理文件列表。

不建议直接 fork，因为它体量大、架构复杂、历史包袱多，且本身已经是完整产品。

### reviewdog

reviewdog 最值得借鉴的是“只评论 diff 内问题”和诊断格式。我们的 finding 应约束为：

- file
- line / hunk
- severity
- confidence
- evidence
- recommendation
- source

短期不一定接入 reviewdog，但内部诊断结构要接近 RDFormat / SARIF 思路，便于后续转 Markdown、GitHub Review Comment、SARIF 或 reviewdog 输入。

### Claude Code Security Review

值得借鉴：

- diff-aware scanning。
- PR comments。
- 上下文理解。
- 严重级别和修复建议。
- 误报过滤。
- 安全边界说明。

本项目 README 和架构文档应明确：默认不执行 PR 代码，不默认 clone 整仓，不对 fork PR 暴露 secrets，并防范 PR diff 中的 prompt injection 指令。

### Semgrep / Bandit / Gitleaks / CodeQL

这些工具适合作为外部扫描器，不适合复制内部实现。72 小时内不要重写它们。可设计可选 scanner 接口，未来支持：

- Bandit：Python 安全检查。
- Gitleaks：secret 检测。
- Semgrep：多语言规则扫描。
- CodeQL / SARIF：语义代码分析和 GitHub code scanning。

### Danger JS

Danger 的价值是自动化 PR 规范，让 Reviewer 关注更难的问题。本项目应加入 PR Hygiene / Review Readiness：

- PR 描述是否为空。
- 是否改了源代码但没有测试。
- 是否是超大 PR。
- 是否改了认证、权限、支付、配置等高风险路径。
- 是否缺少迁移说明或兼容性说明。

### 轻量 AI Review GitHub Action

轻量 Action 项目适合参考 PR diff 获取、文件过滤、AI 调用和 PR comment 流程。但本仓库应保持 Python CLI 主体，不要在 72 小时内重写为 TypeScript / Probot。P1 可以加 `github_commenter.py`，先发单条 summary comment，不急着做 inline comments。

## 产品定位与功能边界

推荐定位：

> AI PR Review Assistant 是一个低噪声、证据优先、可离线降级的 PR 评审助手。

核心卖点：

- 先规则后模型：规则负责高置信风险召回，模型负责解释、归纳和可操作建议。
- 只基于证据输出：每条风险必须有文件、行号或 hunk、证据片段。
- 低噪声：宁可少报，也不要生成大量泛泛评论。
- 可运行闭环：无模型 key 时仍能用本地规则生成报告。
- 真实工作流友好：CLI 可本地使用，后续可接 GitHub Action 和 PR summary comment。

明确不做：

- 不做完整 Web 前端。
- 不自动修改代码并 push。
- 不做全仓深度索引。
- 不做所有 Git 平台支持。
- 不默认执行 PR 中的代码。
- 不 fork 大型 AGPL 或复杂平台作为主体。
- 不生成大量 inline comments。

## 创新点

### 低噪声 Review

不要追求输出很多评论。默认突出 Top N 个最值得人工关注的问题。排序可以参考：

```text
score = severity_weight + confidence_weight + changed_line_relevance + sensitive_path_weight + test_gap_weight
```

### 证据链优先

每条风险都必须包含：

- 文件路径。
- 新增行号或 hunk。
- 证据片段。
- 风险原因。
- 验证方式。
- 修复建议。
- 置信度。
- 来源：rule / ai / scanner。

### 规则与 AI 分工明确

规则层负责稳定、高置信信号，例如 secrets、危险函数、缺测试、危险配置。模型层负责总结变更意图、解释影响面、合并重复发现，并把建议写成真实 Reviewer 可以使用的表达。

### Review Brief

最终报告不只是风险列表，而是给 Reviewer 的决策简报：

1. 这个 PR 做了什么。
2. 影响哪些模块。
3. 最值得先看的 3 个风险。
4. 是否缺测试。
5. 人工 Review 建议顺序。
6. 可直接复制的 PR Review 评论。

### 可离线降级

没有 OpenAI API Key 时，工具仍然用本地规则生成报告。比赛 demo 中网络或 key 出问题时，作品仍应可运行。

### 安全边界可讲清楚

README 和架构文档要明确：

- 默认不执行 PR 中的代码。
- 默认不 clone 整仓。
- 默认不对 fork PR 暴露 secrets。
- PR comment 模式默认发 summary comment。
- prompt 中明确忽略 PR diff 内试图操纵 reviewer 的指令。

## 目标架构

```text
ai_pr_review/
  cli.py
  github_client.py
  models.py
  patch_parser.py
  context_builder.py
  risk_rules.py
  review_engine.py
  ai_client.py
  report.py
  github_commenter.py
  config.py

tests/
  fixtures/
  test_patch_parser.py
  test_risk_rules.py
  test_context_builder.py
  test_review_engine.py
  test_report.py

docs/
  problem_statement.md
  competition_faq_notes.md
  product_requirements.md
  architecture.md
  demo_script.md
  references.md

examples/
  sample_report.md
  sample_report.json
  github-action.yml
```

核心数据流：

```text
PR URL
  -> parse_pr_url
  -> GitHubClient.fetch_pr_context
  -> PatchParser parses files into hunks / changed lines
  -> RiskRules scan added lines and PR metadata
  -> ContextBuilder sorts and prunes context
  -> ReviewEngine runs local fallback or AI
  -> ReportRenderer renders markdown / json
  -> optional GitHubCommenter posts summary
```

## 优先级

### P0 必须完成

- 结构化 patch / hunk / line 解析。
- 风险规则升级为带 id、severity、confidence、category、message、recommendation、evidence、file、line 的 finding。
- 上下文构建与预算控制。
- Markdown 和 JSON 报告。
- AI JSON 输出校验与 fallback。
- README / docs / demo script。
- 测试覆盖核心路径。

### P1 强烈建议完成

- GitHub Action 示例。
- 单条 PR summary comment。
- `.ai-pr-review.yml` 或 JSON 配置。
- ignore / include patterns。
- 中文 / 英文报告选项。

### P2 有余力再做

- 外部 scanner 适配器接口，例如 Bandit 或 Gitleaks。
- SARIF 输出。
- 轻量技能系统。
- 仓库上下文增强。

## 推荐 PR 顺序

### PR 3：产品需求与架构文档

新增 `docs/product_requirements.md`、`docs/architecture.md`、`docs/references.md`，README 增加路线图和设计亮点入口。

验收：

- 文档中文可读。
- README 链接正确。
- pytest 和 ruff 通过。

### PR 4：Patch Parser 与行号证据

新增 `patch_parser.py`，扩展模型，解析 unified diff hunk header、新增行号、删除行号和新增行内容。

验收：

- 兼容 GitHub API 返回的 `file.patch`。
- 忽略 `+++` / `---` 文件头。
- 新增行有 `new_line_number`。
- 无 patch 文件优雅处理。
- pytest 和 ruff 通过。

### PR 5：风险规则引擎升级

重构规则引擎，finding 增加 rule id、confidence、line_start、line_end、recommendation、source。扩展 security、reliability、testing、maintainability 规则。

验收：

- 规则只基于新增行或 PR 元数据输出证据。
- 每条 finding 必须有 recommendation。
- 每类规则至少有测试。
- pytest 和 ruff 通过。

### PR 6：Context Builder 与预算控制

新增 `context_builder.py`，输入 PRContext、parsed hunks 和 findings，输出 ContextPack。

验收：

- 风险命中文件优先。
- 支持每文件 patch budget 和总 budget。
- 记录 omitted files 和 truncation reason。
- docs、lockfile、generated / minified 文件降权。
- pytest 和 ruff 通过。

### PR 7：AI 结构化分析与 fallback

新增或重构 `ai_client.py`，ReviewEngine 使用结构化 prompt 和 JSON schema。JSON parse 失败时 fallback。AI 只能补充或解释 finding，不能凭空制造无文件证据的高危 finding。

验收：

- mock OpenAI 成功 JSON。
- mock OpenAI 非法 JSON。
- no API key fallback。
- `--no-ai` fallback。
- 支持 `--language zh/en` 和 `--model`。
- pytest 和 ruff 通过。

### PR 8：报告升级

`report.py` 支持 Markdown / JSON，CLI 增加 `--format markdown|json`。Markdown 报告包含 PR 基本信息、Change Summary、Review Brief、Risk Matrix、Findings with Evidence、Test Gaps、Omitted Context、copy-ready comment 和 analyzer metadata。

验收：

- 中文默认报告清晰。
- findings 按 severity 和 confidence 排序。
- JSON 可被 `json.loads` 解析。
- pytest 和 ruff 通过。

### PR 9：配置文件与过滤规则

新增 `config.py`，支持 `.ai-pr-review.yml` 或 `.ai-pr-review.json`，CLI 支持 `--config`。

验收：

- 默认配置可用。
- 自定义 ignore / include 可用。
- 可禁用规则或设置最低严重级别。
- README 有配置示例。
- pytest 和 ruff 通过。

### PR 10：GitHub Action 与 PR summary comment

提供 `examples/github-action.yml`，新增 `github_commenter.py`。先实现 issue comment 或 summary comment，不做大量 inline comments。

验收：

- 找到已有 bot comment 则更新，没有则创建。
- workflow 使用最小权限。
- README 说明 fork PR secrets 风险。
- mock GitHub API 测试通过。

### PR 11：外部 scanner 接口

新增 scanner base schema，可选实现 Bandit 或 Gitleaks 适配器。

验收：

- 外部命令不存在时优雅跳过。
- 不作为默认必需依赖。
- 结果可合并到 ReviewReport。
- pytest 和 ruff 通过。

### PR 12：最终 demo 与提交材料

新增 `docs/demo_script.md`，补 `examples/sample_report.md` 和 `examples/sample_report.json`，README 补齐作品定位、功能列表、快速开始、环境变量、CLI 示例、no-ai 示例、GitHub Action 示例、设计思路、模型选择、上下文获取、误报漏报控制、测试方式、demo 视频链接和第三方参考与原创声明。

验收：

- 新用户按 README 能跑起来。
- `python -m pip install -e ".[dev]"` 可用。
- `python -m pytest` 通过。
- `python -m ruff check .` 通过。
- `ai-pr-review analyze <公开 PR URL> --no-ai --output analysis-output/demo-report.md` 可生成报告。

## 每个 PR 的描述模板

```markdown
## 功能描述

说明本 PR 新增或修改了什么，以及用户如何使用。

## 实现思路

说明核心技术方案、涉及文件、为什么这样设计。

## 测试方式

- python -m pytest
- python -m ruff check .
- ai-pr-review analyze ... --no-ai --output ...

## 个人分工

- yourskenny：需求确认 / 方案选择 / 验收
- Codex：实现 / 测试 / 文档更新
```

## 质量红线

- 不要一次性巨大 PR。
- 不要引入没有必要的大依赖。
- 不要复制外部项目大段代码。
- 不要输出没有证据的高危风险。
- 不要让模型失败导致 CLI 不可用。
- 不要牺牲 no-ai 模式。
- 不要为了 GitHub Action 自动评论破坏基础 CLI。
- 不要忘记更新 README 和测试。

## 推荐执行路线

第一阶段：把本地 CLI 报告打磨到很强。优先做 patch parser、规则引擎、context builder 和报告升级。

第二阶段：把 AI 接入做稳。让 AI 做总结、解释和合并建议，不让它无约束地产生大量评论。

第三阶段：补 GitHub Action 示例和 demo 材料。先用单条 summary comment，不急着做 inline comments。

第四阶段：用 README 把创新讲透。重点说明低噪声、规则 + AI、证据链、可离线降级、不 clone、不执行代码和安全边界。

最终作品应给人的印象：这是一个小而完整的 AI PR Review 工具。它不是简单把 diff 扔给模型，而是先做结构化 diff、规则扫描、上下文预算和证据绑定，再让 AI 生成 Reviewer 可用的简报和建议。它能在没有模型 key 时降级运行，也能逐步扩展到 GitHub Action、外部扫描器和企业规则库。
