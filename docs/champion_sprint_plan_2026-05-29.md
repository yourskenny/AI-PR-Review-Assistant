# 2026-05-29 冠军冲刺规划

本文面向下一阶段执行者、参赛提交负责人和最终演示负责人。读完后应能按优先级推进冠军冲刺，判断每一项是否达到可验收标准，并把作品包装成一个能争夺第一名的 AI PR Review 工具。

## 冲刺目标

本项目当前已经具备可提交闭环：用户指定 GitHub PR，系统获取 PR metadata 和 diff，生成变更总结、风险 finding、Review 建议，并支持 CLI、Markdown、JSON、Dashboard、GitHub summary comment 和可选行级 Review。

冠军冲刺的目标不是继续堆功能，而是让评委在短时间内确认三件事：

1. 这不是简单把 diff 丢给模型，而是有结构化上下文、证据绑定、规则与 AI 分工的评审系统。
2. 这不是只能演示一次的 demo，而是有评测证据、测试门禁、低噪声策略和可解释输出的工程作品。
3. 这不是空泛的 AI 助手，而是能进入真实 PR Review 流程，帮助 Reviewer 更快抓住最值得人工确认的问题。

最终对外定位应统一为：

> AI PR Review Assistant 是一个证据优先、低噪声、可离线降级的 AI Reviewer Copilot。它先结构化解析 PR diff，绑定文件和新增行证据，运行高置信规则与可选 scanner，再让 AI 生成可执行的 Review Brief，帮助人类 Reviewer 更快发现真正值得关注的风险。

## 评分点拆解

| 赛题关注点 | 当前状态 | 冠军级补强 |
| --- | --- | --- |
| PR 变更总结 | 已支持本地和 AI summary | 增加影响面、风险路径、Reviewer Action Plan |
| 风险代码识别 | 已有规则、scanner、行号证据 | 扩展高价值规则，加入排序解释和置信度校准 |
| Review 建议生成 | 已输出 recommendation 和可复制评论 | 让建议包含验证方式、测试建议、人工 Review 顺序 |
| 分析准确性 | 有单元测试，缺评测样例 | 建立 evaluation cases，记录命中、误报、漏报、耗时 |
| 上下文理解 | 主要基于 PR patch | 轻量补充相关文件、测试文件、敏感路径和上下文覆盖说明 |
| 误报与漏报控制 | 低噪声策略已写入 README | 用排序、阈值、证据门槛和评测表证明策略有效 |
| 响应速度 | GitHub API + patch budget | 在评测文档中记录 no-AI 与 AI-assisted 耗时 |
| 使用体验 | CLI、Dashboard、GitHub comment 已具备 | Dashboard 增加演示样例、风险概览、行动计划 |
| 模型选择 | README 已说明默认模型和 fallback | 增加模型职责边界：AI 解释和归纳，不凭空制造高危 finding |
| 上下文获取 | README 已说明不 clone、不执行代码 | 增加“上下文覆盖率”和“未覆盖风险”说明 |
| 未来扩展 | 已列出 GitHub App、多语言、企业部署 | 补 SARIF、Semgrep、Gitleaks、历史反馈闭环的演进图 |

## 冠军标准

下一阶段所有工作都应围绕以下验收标准：

- 评委能在 3 分钟内看懂作品差异化。
- 无模型 key 时仍能完整演示核心流程。
- 有模型 key 时能体现 AI 对总结、解释、归纳和建议表达的价值。
- 每个高危 finding 都有证据、文件、行号或 hunk、置信度、来源和修复建议。
- 没有证据的风险不包装成高危结论。
- Dashboard 能支撑现场演示，不要求评委自己准备 PR。
- README 能一一对应赛题评分点。
- 文档能证明准确性、低噪声、响应速度和上下文边界。
- 全量测试、lint、CLI smoke 在最终提交前必须通过。

## 冲刺主线

### 主线一：评测证据包

这是最高优先级。冠军作品必须证明自己有效，而不是只展示功能列表。

交付物：

- 新增评测说明，记录评测方法、样例来源、预期风险、实际输出、误报、漏报和耗时。
- 增加 5 到 10 个 evaluation cases，覆盖安全、可靠性、测试缺口、配置风险、PR hygiene 和无风险 PR。
- 每个 case 同时记录 no-AI 输出和 AI-assisted 输出的差异。
- 增加一张评分表，明确每个 case 的命中结果和人工判断。

建议 case 组合：

1. 动态执行或命令执行风险。
2. Secret 或 token 泄露风险。
3. 权限、认证、支付或配置路径变更但缺少测试。
4. 源代码变更但没有测试文件变化。
5. 大 PR、空 PR 描述、迁移说明缺失等 Review readiness 问题。
6. 低风险文档 PR，验证系统不会强行报高危。
7. scanner 命中样例，验证外部工具结果能合并到统一 finding。

验收标准：

- 每个 case 都能用固定命令复现。
- 评测表能说明为什么报、为什么不报、误报如何处理。
- 文档中有耗时数据，至少区分 no-AI 和 AI-assisted。
- README 链接到评测文档。

### 主线二：高信号规则与排序

当前规则已经能演示，但冠军级需要更像真实 Reviewer 的风险判断。

规则扩展优先级：

1. Secret detection：API key、token、private key、password literal。
2. Injection：SQL 拼接、shell=True、subprocess 拼接、危险命令。
3. Unsafe execution：eval、exec、pickle、yaml unsafe load。
4. Auth and permission risk：认证、权限、支付、配置路径变更时提高风险权重。
5. Test gap：源代码变更无测试，敏感路径变更无测试。
6. Reliability：宽泛异常吞掉错误、静默 fallback、超宽 timeout 或无 timeout。
7. Migration and compatibility：schema、migration、配置变更无回滚或兼容说明。
8. Review readiness：PR 描述为空、变更过大、生成文件或依赖锁大幅变化。

排序策略：

```text
priority = severity_weight
         + confidence_weight
         + changed_line_relevance
         + sensitive_path_weight
         + test_gap_weight
         + scanner_source_weight
         - weak_evidence_penalty
```

输出要求：

- 每条 finding 都要说明“为什么值得先看”。
- 风险矩阵要展示 severity、confidence、source、file、line。
- Review Brief 只突出 Top risks，避免把所有低价值信息推到前面。
- 没有新增行号证据的 finding 可以进入 summary，但默认不生成行级评论。

验收标准：

- 每类规则有 focused tests。
- 规则命中新增行或 PR metadata，不扫描无关旧代码。
- 误报案例要能通过阈值、路径、证据门槛或配置解释。

### 主线三：轻量上下文增强

不要做大型全仓索引。冠军冲刺需要的是可解释、稳定、低成本的上下文增强。

建议能力：

- 识别改动文件语言和类型。
- 根据文件名推断对应测试文件。
- 根据 import 或同目录关系补充少量相关文件摘要。
- 标记敏感路径：auth、permission、security、payment、billing、config、migration、infra。
- 输出上下文覆盖说明：已分析哪些 patch，补充了哪些相关上下文，哪些因预算被省略。

设计边界：

- 默认仍不执行 PR 代码。
- 默认仍以 GitHub API diff 为主。
- 如需要拉取相关文件，应通过 GitHub contents API 或 raw URL，只拉取小体积文本文件。
- 任何上下文省略都要进入报告，避免给出“全量理解”的错觉。

验收标准：

- 报告能说明“为什么这个 PR 影响面较高或较低”。
- 相关测试文件缺失能反映到 Test Gaps。
- 大 PR 中被省略的文件可追溯。

### 主线四：Dashboard 演示体验

现在 Dashboard 已能输入 PR 并查看报告。冠军级需要降低评委试用门槛，让它成为现场演示控制台。

建议增强：

- 增加 demo case 入口，一键加载内置样例结果。
- 顶部增加运行耗时、文件数、finding 数、最高风险、上下文覆盖数量。
- 增加 Reviewer Action Plan：建议先看哪个文件、验证什么测试、如何修复。
- 每个 finding 增加“为什么被报出”和“为什么是这个置信度”。
- 支持 no-AI 与 AI-assisted 对比展示。
- 保留 Markdown comment 和 JSON report 复制区。

验收标准：

- 无需配置 GitHub token，也能用内置样例完成演示。
- 评委能从第一页看出作品不是纯文本报告。
- 页面不夸大能力，不把低置信 finding 包装成确定漏洞。

### 主线五：输出生态与集成信号

冠军作品要显示可扩展性，但不能牺牲稳定性。

建议补强：

- 增加 SARIF 或 diagnostics JSON 输出，说明可接 GitHub Code Scanning、reviewdog 或企业平台。
- 保持 GitHub Action 默认 summary comment，不默认开启行级噪声。
- 行级 Review 继续显式开启，后续再做去重、更新和线程管理。
- 文档中给出未来接 Semgrep、Gitleaks、CodeQL、GitHub App 的路线。

验收标准：

- 新输出格式有 schema 测试。
- README 明确各输出格式适用场景。
- 不引入沉重依赖，不破坏 no-AI 模式。

### 主线六：最终包装与提交

冠军冲刺必须把技术点翻译成评委能快速打分的材料。

交付物：

- README 增加“赛题评分点对应表”。
- README 增加“为什么不是普通 LLM diff prompt”。
- README 补 Demo 视频链接。
- Demo 脚本调整为冠军叙事：先展示痛点，再展示证据链，再展示评测结果。
- 阶段总结更新为最终提交说明。
- 当前功能分支合回 main，最终提交分支保持干净。

验收标准：

- 新用户按 README 能安装、运行、查看 dashboard、生成报告。
- Demo 视频覆盖 no-AI fallback、AI-assisted、Dashboard、GitHub comment、评测证据。
- 最终提交前测试、lint、CLI smoke 全部通过。

## 推荐执行顺序

### P0：必须先做

1. 合并当前行级 Review 分支到 main，保证主分支包含当前完整能力。
2. 建立 evaluation cases 和评测文档。
3. 补强高价值规则和测试。
4. README 增加评分点对应表。
5. Dashboard 增加 demo case 和核心指标区。

### P1：冲高分关键

1. 轻量上下文增强。
2. Review Brief 增加 Reviewer Action Plan。
3. finding 增加排序解释。
4. 记录 no-AI 与 AI-assisted 响应耗时。
5. Demo 脚本重写为冠军叙事。

### P2：锦上添花

1. SARIF 或 diagnostics JSON 输出。
2. Semgrep 或 Gitleaks 适配计划和最小实现。
3. 行级评论去重策略设计。
4. GitHub App / 企业部署路线图。

## 每日冲刺节奏

### Day 1：证据与规则

- 上午：确定 evaluation cases，写评测文档骨架。
- 下午：补安全、测试缺口、Review readiness 规则。
- 晚上：跑全量测试，生成第一版评测结果。

验收：评测文档可以证明至少 5 个 case 的命中与不命中逻辑。

### Day 2：上下文与体验

- 上午：实现轻量上下文增强和上下文覆盖说明。
- 下午：Dashboard 增加 demo case、指标区、Action Plan。
- 晚上：录制本地演示 dry run，记录卡点。

验收：无 GitHub token 也能在 Dashboard 展示完整样例。

### Day 3：包装与最终提交

- 上午：README 增加评分点对应表、评测结果和设计亮点。
- 下午：录制 Demo 视频并补链接。
- 晚上：全量验证、合并 main、最终提交检查。

验收：从 clean checkout 到完成演示的路径可复现。

## 最终演示叙事

演示不应从功能列表开始，应从真实 Review 痛点开始：

1. Reviewer 面对 PR 时最缺的是时间、上下文和高信号风险排序。
2. 本工具不是替代 Reviewer，而是先把 PR 变成证据化 Review Brief。
3. 系统先解析 diff 和新增行，再运行高置信规则和 scanner。
4. AI 只负责归纳、解释和生成可执行建议，不凭空制造高危结论。
5. no-AI 模式证明系统不是 API key 绑定 demo。
6. Dashboard 展示人类 Reviewer 真正需要的风险矩阵、证据和行动计划。
7. 评测文档证明准确性、低噪声和响应速度不是口号。

## 风险控制

- 不要把冠军冲刺变成大而散的平台改造。
- 不要默认启用大量行级评论。
- 不要引入无法稳定安装的大依赖。
- 不要让 AI 输出没有文件证据的高危 finding。
- 不要为了展示 scanner 牺牲 no-AI 主链路。
- 不要遗漏 README、Demo、评测文档这些评委直接看到的材料。
- 不要把“未来可扩展”写成“当前已实现”。

## 最终提交检查表

- [ ] 主分支包含当前所有已完成能力。
- [ ] README 有快速开始、功能、设计、评分点对应、评测结果、Demo 链接。
- [ ] 评测文档有至少 5 个可复现 case。
- [ ] Dashboard 可以用内置样例演示。
- [ ] no-AI 模式可完整运行。
- [ ] AI-assisted 模式有清晰模型职责边界。
- [ ] GitHub Action 示例仍保持低噪声 summary comment。
- [ ] 行级 Review 是显式开启能力。
- [ ] pytest 全量通过。
- [ ] ruff 全量通过。
- [ ] CLI smoke 生成 Markdown 和 JSON 报告。
- [ ] 最终演示脚本在本机完整走通。

## 决策原则

如果时间不足，优先级如下：

1. 评测证据优先于新功能。
2. 低噪声排序优先于规则数量。
3. Dashboard 演示确定性优先于在线 GitHub 依赖。
4. README 评分点对应优先于长篇架构解释。
5. no-AI 稳定链路优先于更强模型效果。

冠军作品的核心不是“功能最多”，而是“每个评分点都有证据，每个输出都有解释，每个演示步骤都稳定”。
