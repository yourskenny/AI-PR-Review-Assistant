# Demo 视频脚本

本文用于录制 3-5 分钟作品演示视频。视频重点不是逐行讲代码，而是让评委快速看到：工具能跑通、报告有用、设计边界清楚、测试可验证。

## 0:00-0:30 作品定位

开场说明：

- 作品名称：AI PR Review Assistant。
- 赛题：AI PR Review 助手。
- 目标用户：需要快速理解 GitHub Pull Request 并定位风险的开发者或 Reviewer。
- 产品定位：Reviewer Copilot，不替代人类 Reviewer，而是先生成 PR 摘要、风险排序和可复制 Review 建议。

推荐口播：

> 这个工具的重点是低噪声、证据可追溯和可离线降级。它不是简单把 diff 丢给模型，而是先解析 PR diff、运行本地规则、控制上下文预算，再用 AI 或本地 fallback 生成 Review Brief。

## 0:30-1:20 无 AI Key 降级

展示命令：

```powershell
python -m ai_pr_review.cli analyze https://github.com/openai/openai-python/pull/123 --no-ai --language zh --output analysis-output\demo-report.md
```

讲解要点：

- 无 AI Key 降级：即使没有 `OPENAI_API_KEY`，本地规则仍然能生成可读报告。
- 报告包含 Change Summary、Review Brief、Risk Matrix、Findings with Evidence、Test Gaps 和 Copy-ready Review Comment。
- 每条 finding 都有 rule id、severity、confidence、evidence 和 recommendation。

## 1:20-2:00 JSON 报告

展示命令：

```powershell
python -m ai_pr_review.cli analyze https://github.com/openai/openai-python/pull/123 --no-ai --format json --output analysis-output\demo-report.json
```

讲解要点：

- JSON 报告便于 CI、后续平台集成或转 SARIF。
- 结构包含 `pull_request`、`summary`、`review_brief`、`risk_matrix`、`findings`、`test_gaps`、`context` 和 `metadata`。

## 2:00-2:45 GitHub Action

打开 `examples/github-action.yml`，说明：

- workflow 在 PR opened / synchronize / reopened 时运行。
- 权限最小化：`contents: read`、`pull-requests: write`、`issues: write`。
- 默认跳过 fork PR，避免 secrets 暴露给不可信代码。
- `--comment` 只创建或更新一条 summary comment，避免大量 inline comments 干扰 Review。

## 2:45-3:30 设计思路

说明核心架构：

```text
PR URL
  -> GitHub API 获取 metadata 和 patch
  -> patch parser 解析 hunk 和新增行号
  -> risk rules / optional scanners 产生证据 finding
  -> context builder 做预算控制和省略记录
  -> AI client 或 local fallback 生成 summary / suggestions
  -> Markdown / JSON report / GitHub summary comment
```

重点强调：

- 模型选择：默认 `gpt-4.1-mini`，低延迟和成本可控；可用 `--model` 切换。
- 上下文获取：默认只用 GitHub API 的 PR patch，不 clone 整仓，不执行 PR 代码。
- 误报控制：规则负责高置信信号，模型负责解释和归纳；报告保留证据链。
- 扩展方向：GitHub App、更多语言规则、SARIF、Semgrep/Gitleaks、历史反馈排序。

## 3:30-4:20 测试方式

展示命令：

```powershell
python -m pytest
python -m ruff check .
python -m ai_pr_review.cli analyze https://github.com/openai/openai-python/pull/123 --no-ai --format markdown --output analysis-output\demo-report.md
python -m ai_pr_review.cli analyze https://github.com/openai/openai-python/pull/123 --no-ai --format json --output analysis-output\demo-report.json
```

说明测试覆盖：

- GitHub URL 和 API 错误处理。
- patch parser 行号证据。
- 风险规则和配置过滤。
- AI JSON fallback。
- Markdown / JSON 报告。
- GitHub comment create / update。
- GitHub Action 示例。
- 外部 scanner 适配器。

## 4:20-5:00 收尾

总结：

- 工具已经能端到端分析公开 GitHub PR。
- 核心能力覆盖赛题要求：PR 变更总结、风险代码识别、Review 建议生成。
- 作品特点是低噪声、证据优先、规则与 AI 结合、可离线降级、CI/PR 工作流友好。
