---
title: 🎓 LEAP Framework
tags:
- leap
- engineering
aliases:
- 🎓 LEAP Framework guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP 🎓 LEAP Framework foundations definitions workflow`
> Extension: `LEAP 🎓 LEAP Framework failure cases examples comparison`
> Advanced: `LEAP 🎓 LEAP Framework invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/github/v/release/Vinger-lee/leap-framework" alt="Release">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-70%20tools-22bb33" alt="MCP 工具">
  [![Tests](https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml)
  <img src="https://img.shields.io/badge/中文-支持-ff6600" alt="中文支持">
  <br>
  <b>🤖 给你的 AI Agent 一套真正的教学引擎 —— 而不只是一段提示词。</b>
</p>

<p align="center">
  [[README|English]] ·
  [[README_CN|中文]] ·
  [[docs/i18n/README.ja|日本語]] ·
  [[docs/i18n/README.ko|한국어]] ·
  [[docs/i18n/README.fr|Français]] ·
  [[docs/i18n/README.es|Español]] ·
  [[docs/i18n/README.ru|Русский]] ·
  [[docs/i18n/README.ar|العربية]]
</p>

---

## 🚀 LEAP 是什么？

**LEAP（Learning Evolution & Adaptation Pipeline）是一个面向 AI Agent 的状态驱动教学运行时。**
它为 Agent 提供一套可持久化、可审计的学习闭环，而不是"讲一段再考一题"的一次性提示词。

Agent 继续做它擅长的事 —— 理解学习者、生成讲解、出题、评判开放式回答。
LEAP 负责所有必须保持一致的部分：

- **学习者状态**与掌握度估计
- **前置依赖**以及某个知识点能否进入
- **评估充分性**与证据质量
- **复习调度**与长期保持
- **状态迁移** —— 不通过服务端 State Guard，任何状态都不会推进

```bash
# Agent 向 LEAP 询问下一步该做什么
get_teaching_context(session_id, "py.recursion.base_case")
# 👉 策略: Retrieval Practice · 动作: Generate Practice
#    证据阶段: practiced · 掌握度: 0.62 · 提示依赖: 0.25
#    到期复习: 2 · 活跃错误概念: 1
```

## ⚡ 快速开始

```bash
git clone https://github.com/Vinger-lee/leap-framework.git
cd leap-framework
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

运行测试：

```bash
pytest -q        # inspect the current test result
```

启动 MCP Server：

```bash
python -m leap.server      # 或：leap-mcp
```

校验内置教学页面：

```bash
python scripts/verify_example.py --all          # 静态规范符合性
python scripts/verify_example_runtime.py --all  # headless 运行时 + JSON Schema
```

## 🧠 学习闭环

```
1. 目标定义
2. 领域校准            ← Agent 先学习该专题，再开始教学
3. 学习者诊断
4. 知识表示            ← 知识节点 DAG
5. 学习者状态初始化
6. 动态教学循环        ← 读状态 → 策略 → 动作 → 尝试 → 评估 → 更新
7. 保持                ← FSRS 间隔复习
8. 迁移                ← 近迁移 → 变式 → 远迁移 → 综合任务
9. 反思与持久化
```

### 🔒 State Guard（状态守卫）

State Guard 是唯一有权批准状态迁移的组件。当工具返回 `REJECT` 时，Agent 应依据原因调整，
而不是用提示词硬推。**失败的调用永远不会变成一次静默的状态更新。**

### 📊 掌握度由服务端估计

`mastery_probability` 是**模型估计值，不是事实真值**。它由内置的遗忘感知 BKT 模型计算，
**不由宿主 Agent 的 LLM 输出概率** —— 这样数值稳定且可审计。每次更新分四步：
时间衰减 → 证据更新 → 状态转移 → 自发遗忘。

支持部分得分与低置信度降权。**不允许把"不确定"写成 `mastery = 0`。**

### 🪜 证据阶段（允许回退）

`estimated → practiced → demonstrated → retained → transferred`

一次答对只产生一条证据 —— 不等于学会。学习者长期未接触或在新场景失败时，阶段**会回退**。
判据位于 Policy 层且完全可配置。

### ⏰ 保持与迁移

存在到期复习项**不等于**必须阻断全部新知识。是否插入、优先或阻塞按节点决定。
保持（FSRS，评分 1–4）与迁移（近 / 变式 / 远 / 综合）是两个互补的长期证据维度。

## 🔧 MCP 工具

70 个工具，走 stdio，按领域分组：

### 🚀 八次调用即可开始

细粒度工具的存在是为了让每次状态变更都可独立审计；宿主 Agent 不必逐个驱动它们。8 个粗粒度工具在
服务端完成组合，且每个回包都带 `next_call`——下一次该调用的工具及其参数。

| 粗粒度工具 | 组合的细粒度调用 |
|---|---|
| `start_learning` | `create_session` + `save_learning_goal` + `set_learning_configuration` |
| `continue_lesson` | `get_teaching_context` + `get_session_info` |
| `log_teaching_action` | `commit_pedagogical_decision` |
| `submit_answer` | `submit_attempt` + `commit_assessment` + `get_mastery_status` |
| `advance_lesson` | `check_advance_unit` + `advance_unit`（先试跑 Guard） |
| `get_review_queue` | `get_due_reviews` |
| `review_answer` | `submit_review` |
| `get_learner_snapshot` | `get_session_info` + `get_mastery_status` + `get_knowledge_nodes` + `get_due_reviews` |

门面层不放松任何约束：State Guard 仍是裁决者，被拒的推进不写入状态，评估失败时作答仍可补救，原始作答
逐字保存，掌握度仍由服务端估计。工具档位可缩小目录——`--tool-profile quickstart` 只暴露 25 个工具。
详见 [[docs/FACADE_CN|粗粒度教学 API 与工具档位]]，以及 [[docs/scope-and-limits_CN|范围与边界]]。

| 分组 | 示例 |
|---|---|
| 会话与目标 | `create_session`、`save_learning_goal`、`set_learning_configuration` |
| 诊断 | `generate_diagnostic`、`submit_diagnostic`、`save_diagnostic_result` |
| 知识 | `decompose_topic`、`save_knowledge_nodes`、`validate_knowledge_dag` |
| 策略 | `get_teaching_context`、`evaluate_pedagogical_policy`、`commit_pedagogical_decision` |
| 评估 | `generate_assessment`、`save_assessment_item`、`submit_attempt`、`commit_assessment`、`assess_response` |
| 保持 | `schedule_review`、`get_due_reviews`、`submit_review` |
| 状态守卫 | `start_unit`、`check_advance_unit`、`advance_unit`、`rollback_unit` |
| 证据 | `save_benchmark_report`、`get_evidence`、`validate_claim` |
| 教学交付 | `get_teaching_delivery_policy`、`get_subject_catalog`、`save_teaching_package` |
| 工件 | `save_artifact`、`get_obsidian_structure`、`get_web_component_spec` |
| 反思 | `record_reflection` |
| 报告 | `generate_final_report`、`get_learning_metrics` |

上表只列示例；[[docs/mcp-tools|自动生成的完整工具参考]] 包含全部注册工具与准确参数，并由 CI 核对。

领域校准现在要求 `save_benchmark_report(verification=...)` 提供来源定位、摘录、关联论断、复核例题和不确定性；仅保存文字报告会保持 pending，教学入口也受门禁约束。宿主必须自行阅读资料，出题前用 `save_assessment_item` 登记题目条件、答案、推导与独立检查。自由文本推理必须由宿主做语义评估：LEAP 检查记录并估计学习状态，不能证明学科答案正确。

参见[[docs/content-quality|内容质量与真实联调流程]]及[[docs/quality-audit-2026-10-10|本次交付物审计]]。浏览器场景、真实 MCP 联调、内容审校分别验收。

所有模式永久执行完整教学、可控图示、宽屏、完整 Obsidian 原始知识源和头部精准资源规则。先登记实际 Markdown/HTML 正文对 `save_teaching_package`，再登记题目；规范详见 [[docs/teaching-delivery]]。学科目录包含11类领域，八个示例配有完整知识笔记与行为清单。2028数一第一章生成配方见 [[curricula/math1-2028-ch01/README]]。

## 🧩 可插拔设计

六个组件通过插件注册表解析，可在 `config/default.yaml` 中替换实现，**调用点无需改动**：

| 接缝 | 默认实现 | 可替换 |
|---|---|---|
| 状态估计 | `simplified_bkt` | PFA、DKT、贝叶斯、混合 |
| 评分聚合 | `weighted` | rubric、模型驱动 |
| 教学策略 | `rule_based` | LLM、混合、学习式 |
| 复习调度 | `py-fsrs` | 任意调度器 |
| 存储 | `sqlite` | PostgreSQL、分布式 |
| 工件存储 | `local` | 对象存储、知识库 |

## 🌍 多语言

面向学习者的文案走消息目录（`zh-CN` / `en`）。**工具名、字段名、枚举值有意不翻译** ——
翻译会破坏宿主 Agent 的集成代码。在 `config/default.yaml` 设置 `locale`，或用
`LEAP_LOCALE` 环境变量覆盖。

## 📦 配置

所有参数都在 `config/default.yaml`，均为工程启发值，Policy 引擎可全部覆写：

| 参数 | 默认值 | 含义 |
|---|---|---|
| `mastery_threshold` | `0.80` | 掌握阈值 |
| `max_hint_level` | `3` | 提示层级上限 |
| `max_retry_before_example` | `3` | 触发示范的失败次数 |
| `hint_dependency_high` | `0.7` | 高提示依赖阈值 |
| `overall_score_weights` | `0.4/0.3/0.2/0.1` | correctness / conceptual / reasoning / application |
| `review_scheduler` | `py-fsrs` | 间隔重复后端 |
| `interleaving_enabled` | `conditional` | 交错练习 |
| `locale` | `zh-CN` | 面向学习者的文案语言 |

## 📚 示例

八个单文件教学页面，均通过静态检查与 headless Chromium 运行时校验：

| 示例 | 学科 |
|---|---|
| `examples/01-python-recursion/` | 编程 —— Python 递归 |
| `examples/02-math-linear-equation/` | 数学 —— 一元一次方程 |
| `examples/03-cs-osi-model/` | 计算机基础 —— OSI 模型 |
| `examples/04-physics-free-fall/` | 物理 —— 自由落体 |
| `examples/05-logic-flowchart/` | 逻辑 —— 流程图 |
| `examples/06-statistics-probability/` | 统计 —— 条件概率 |
| `examples/07-chemistry-stoichiometry/` | 化学 —— 化学计量 |
| `examples/08-electronics-ohms-law/` | 电路 —— 欧姆定律 |

每个页面都是**参考实现**：零 CDN、零网络请求，并演示真实的"页面 ↔ 运行时"桥接 ——
`LEAP.hydrate(context)` 注入状态，`LEAP.drainOutbox()` 取出待执行的 MCP 调用。

## 🗂 仓库结构

```
leap-framework/
├── config/default.yaml      # 全部工程参数
├── src/leap/
│   ├── i18n.py              # 消息目录
│   ├── server.py            # MCP Server（stdio）
│   ├── runtime/             # 决策核心
│   │   ├── contracts.py     #   插件接缝
│   │   ├── plugins.py       #   实现注册表
│   │   ├── bkt.py           #   掌握度估计
│   │   ├── policy.py        #   教学策略
│   │   ├── scheduler.py     #   FSRS 复习调度
│   │   ├── state_guard.py   #   状态迁移裁决
│   │   └── ...
│   ├── storage/             # SQLite schema + 迁移
│   ├── tools/               # 工具实现
│   └── specs/               # Obsidian / web 组件规范
├── examples/                # 八个教学页面 + 共享规范
├── docs/                    # 架构、接入、多语言
├── scripts/                 # 校验器、扫描器、审计器
└── tests/                   # inspect the current test result
```

## 🔍 质量门禁

```bash
pytest -q                                        # inspect the current test result
python scripts/security_scan.py --root .         # 密钥与个人信息（CI 门禁）
python scripts/verify_example.py --all           # 示例静态规范符合性
python scripts/verify_teaching_repository.py     # canonical notes, reciprocal links and full paired bodies
python scripts/verify_mcp_bridge.py              # actual stdio Runtime + shipped page
python scripts/verify_example_runtime.py --all   # 示例运行时符合性
python scripts/spec_coverage.py                  # 规范覆盖率
python scripts/apply_leap_bridge.py --check      # 宿主桥接完整性
```

退出码：`0` 干净 / `1` 阻断 / `2` 仅警告。前四项在 CI 中每次 push 都会跑。

AI 助手工作区（`.workbuddy*/`、`.claude*/`、`.cursor*/`、`agent-state/` 等）与本地临时目录
不参与发布，由 `.gitignore`、扫描器规则 `AI001` 以及一项 CI 测试共同保证 —— 该测试断言
索引与全部历史中此类文件数量为 0。

## 📖 文档

| 文档 | 内容 |
|---|---|
| [[README|README.md]] | English |
| [[docs/ARCHITECTURE|docs/ARCHITECTURE.md]] | 架构与设计决策 |
| [[docs/INTEGRATION|docs/INTEGRATION.md]] | 宿主 Agent 接入指南 |
| [[docs/EXAMPLES|docs/EXAMPLES.md]] | 八个教学页面及其契约 |
| [`docs/i18n/`](docs/i18n/) | 多语言翻译 |
| [[CHANGELOG|CHANGELOG.md]] | 版本历史 |
| [[CONTRIBUTING|CONTRIBUTING.md]] | 如何参与贡献 |
| [[SECURITY|SECURITY.md]] | 漏洞报告方式 |

> 权威的框架设计文档与视觉设计规范由项目作者另行维护，**不包含在本仓库**。
> 本仓库的实现遵循这些文档。

## 🤝 参与贡献

欢迎提交 issue 与 pull request。请先阅读 [[CONTRIBUTING|CONTRIBUTING.md]]。

## 📄 许可证

[MIT](LICENSE) © Vinger-lee

> [!note]- Reading and verification sequence: LEAP 🎓 LEAP Framework
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README]] · [[curricula/math1-2028-ch01/README]] · [[docs/ARCHITECTURE_CN]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]] · [[docs/i18n/README.ru]] · [[docs/teaching-upgrade-plan]] · [[examples/01-python-recursion/knowledge]] · [[examples/05-logic-flowchart/knowledge]]
