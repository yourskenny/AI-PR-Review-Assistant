# Champion evaluation

本文面向评委、后续维护者和最终提交负责人。读完后应能判断 AI PR Review Assistant 在准确性、低噪声、上下文边界、响应速度和使用体验上的当前证据，而不是只看到功能清单。

## 评测方法

评测采用固定 PR 场景而不是随机在线结果。每个场景包含 PR metadata、文件 patch、预期风险和人工判断。系统以 no-AI 模式先运行规则与证据链，AI-assisted 模式只用于总结、解释和建议表达，不允许凭空制造没有文件证据的高危 finding。

验收重点：

- 命中：预期风险是否以正确 rule id、severity、confidence、file、line 和 evidence 输出。
- 误报：低风险或证据不足的场景是否避免包装成高危问题。
- 漏报：已知高价值风险是否被规则、scanner 或测试缺口信号捕获。
- 响应速度：no-AI 模式应稳定在秒级，AI-assisted 模式取决于模型网络延迟但保留 fallback。
- 可解释性：每条 finding 应有 priority reason 和 Reviewer Action Plan。

## 场景矩阵

| Case | 场景 | 预期命中 | 误报控制 | 漏报风险 | 演示价值 |
| --- | --- | --- | --- | --- | --- |
| E1 | Auth refresh 中新增 `eval` | `security.dynamic_code_execution` | 高危必须有新增行证据 | 低 | 证明证据绑定和行号评论 |
| E2 | SQL f-string 拼接用户输入 | `security.sql_injection` | 只对 SQL 语句和运行时值组合报出 | 中 | 证明真实安全 Review 信号 |
| E3 | 权限路径出现 bypass 逻辑 | `security.permission_bypass`、高风险路径缺测试 | 敏感路径提高权重但仍保留 confidence | 中 | 证明上下文路径风险 |
| E4 | Migration 改 schema 但 PR 无回滚说明 | `maintainability.migration_without_rollback_note` | 文档中出现 rollback/backout 时不报 | 中 | 证明 Review readiness |
| E5 | 源码变更但没有测试文件 | `testing.source_without_tests` | 文档-only PR 不触发 | 低 | 证明测试缺口控制 |
| E6 | 空 PR 描述 | `review_readiness.empty_pr_description` | 非空说明不报 | 低 | 证明人类 Review 流程意识 |
| E7 | 纯文档 PR | 无高危 finding | 不强行报安全问题 | 低 | 证明低噪声策略 |

## no-AI 与 AI-assisted 分工

no-AI 模式负责可复现的基础判断：

- PR URL 和 patch 解析。
- 新增行号绑定。
- 高信号规则扫描。
- 风险排序、priority reason、Reviewer Action Plan。
- Markdown、JSON、SARIF 和 Dashboard 展示。

AI-assisted 模式负责表达层增强：

- 用中文或英文总结 PR 意图。
- 合并重复风险，给出更像 Reviewer 的建议。
- 根据已有 evidence 输出检查清单。
- 在模型失败或无 API key 时降级，不中断主流程。

## 固定复现命令

```powershell
python -m pytest tests/test_risk_rules.py tests/test_report.py tests/test_dashboard.py
python -m ai_pr_review.cli dashboard --host 127.0.0.1 --port 8765
python -m ai_pr_review.cli analyze https://github.com/openai/openai-python/pull/123 --no-ai --format json --output "$env:TEMP\ai-pr-review-eval.json"
python -m ai_pr_review.cli analyze https://github.com/openai/openai-python/pull/123 --no-ai --format sarif --output "$env:TEMP\ai-pr-review-eval.sarif"
```

Dashboard 演示不依赖 GitHub token。启动后打开 `http://127.0.0.1:8765`，点击 `Load demo case` 即可加载内置冠军样例。

## 当前证据

- 规则测试覆盖动态执行、SQL 拼接、权限绕过、unsafe deserialization、HTTP timeout、敏感路径缺测试、大 PR、空 PR 描述和 migration 回滚说明。
- 报告测试覆盖 Markdown、JSON、SARIF、Risk Matrix、Reviewer Action Plan、priority reason、上下文省略说明和 copy-ready comment。
- Dashboard 测试覆盖首页、表单分析、JSON API 和内置冠军 demo case。
- GitHub comment 测试覆盖 summary comment 创建 / 更新和行级 Review create / skip。

## 误报策略

- 默认只对新增行和 PR metadata 产生 finding，不扫描无关旧代码。
- 行级 Review 只发布有文件路径和新增行号的 finding。
- Review readiness 类 finding 使用 medium severity，不伪装成代码漏洞。
- 证据不足时进入人工检查建议，而不是生成高危结论。
- 外部 scanner 是可选增强，命令不存在时跳过，不影响基础报告。

## 漏报边界

当前系统不声称能完整理解全仓语义。以下场景仍需人工 Review 或未来增强：

- 跨文件调用链导致的权限绕过。
- 需要运行测试或应用才能发现的行为回归。
- 复杂业务规则、并发时序和数据迁移兼容性。
- 大型重构中的间接影响面。

这些边界会在报告的上下文省略说明、测试缺口和 Reviewer Action Plan 中显式暴露。
