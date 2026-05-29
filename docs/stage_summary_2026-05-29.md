# 2026-05-29 阶段收尾总结

本文面向后续维护者、参赛提交检查者和需要接手本仓库的开发者。读完后应能判断当前作品能力边界、知道如何验证本阶段交付，并决定后续是否继续扩展行级 Review、SARIF 或更多扫描器。

## 当前状态

本阶段把 AI PR Review Assistant 从最小 CLI 原型推进到可演示的比赛作品闭环。工具现在可以读取 GitHub Pull Request，基于 PR metadata 和 patch 生成结构化上下文，运行本地风险规则和可选外部扫描器，并输出 Markdown、JSON、Dashboard 视图或 GitHub 评论。

主线功能以低噪声和证据链为核心：默认不 clone 整仓，不执行 PR 代码，不在自动化流程里生成大量行级评论。用户可以先看 summary comment 或报告，再按需要显式开启行级 Review。

## 已完成能力

- PR URL 解析、GitHub API 拉取 PR metadata 和文件 patch。
- Patch hunk 解析和新增行号证据绑定。
- 风险 finding 结构化，包含 rule id、severity、confidence、source、evidence、recommendation 和文件行号。
- 本地规则扫描，覆盖安全、可靠性、测试缺口、可维护性等常见 PR Review 信号。
- Context builder 对文件和 patch 做预算控制，并记录省略原因。
- OpenAI 结构化 JSON 分析和本地 fallback；无 API key 或模型失败时 CLI 仍可生成报告。
- Markdown / JSON 报告，包含 Change Summary、Review Brief、Risk Matrix、Findings with Evidence、Test Gaps 和可复制评论。
- JSON 配置文件，支持语言、模型、AI 开关、文件 include / ignore、预算、规则和最低严重级别。
- GitHub Action 示例和单条 summary comment 创建 / 更新。
- 可选 Bandit scanner 适配器，不作为默认依赖。
- 本地 Web Dashboard，复用同一套分析引擎展示摘要、风险矩阵、证据和报告。
- 本阶段新增显式 `--inline-comments`，可把有文件路径和新增行号的 finding 发布为 GitHub PR Review 行级评论。

## 行级评论收尾

此前 `feature/inline-review-comments` 分支已有测试但源码未实现，导致完整测试集失败。本阶段补齐了两处行为：

- CLI `analyze` 命令新增 `--inline-comments`，与 `--comment` 相互独立，可单独使用或同时使用。
- GitHub commenter 新增行级 Review 创建逻辑：先过滤没有文件路径或新增行号的 finding；如没有可定位 finding，返回 `skipped`，不请求创建 Review；如有可定位 finding，读取 PR head sha 并通过 GitHub Pull Request Reviews API 创建一条 review。

这个能力保持显式开启，不改变默认自动化策略。GitHub Action 示例仍使用 summary comment，避免 CI 默认产生过多行级噪声。

## 提交与演示口径

推荐演示顺序：

1. 使用 `--no-ai` 对公开 PR 生成 Markdown 报告，证明无模型 key 时仍可运行。
2. 使用 `--format json` 生成机器可读报告，说明后续可接 CI、SARIF 或平台。
3. 启动 Dashboard，展示人工 Review 工作台视图。
4. 展示 GitHub Action 示例和 `--comment` 的单条 summary comment 策略。
5. 如需要展示行级证据，可对有新增行号 finding 的 PR 手动运行 `--inline-comments`。

## 本阶段验证口径

提交前应在项目虚拟环境中运行：

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ai_pr_review.cli analyze https://github.com/openai/openai-python/pull/123 --no-ai --format json --output "$env:TEMP\ai-pr-review-status-smoke.json"
```

通过标准：

- pytest 全量通过。
- ruff 无 lint 错误。
- CLI smoke 能生成 JSON 报告文件。

## 剩余风险与后续建议

- Demo 视频链接仍需在最终录制并上传后补入 README。
- 行级 Review 当前只对新增行做单行评论；如果后续要支持多行范围评论，需要扩展 finding 的 diff position 映射和测试。
- 外部 scanner 目前只有 Bandit 适配器；如果继续增强多语言能力，优先考虑 Semgrep 或 Gitleaks 的标准输出适配，而不是重写规则。
- GitHub Action 默认使用 summary comment 是正确边界；不要在默认 workflow 中开启行级评论，除非后续有去重、更新和噪声控制策略。
- 目前上下文仍以 PR patch 为主；大型重构或跨文件依赖分析可以作为下一阶段能力，不应影响当前作品提交稳定性。
