# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/github/v/release/Vinger-lee/leap-framework" alt="Release">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-58%20tools-22bb33" alt="MCP 工具">
  <img src="https://img.shields.io/badge/tests-260%20passing-22bb33" alt="测试">
  <img src="https://img.shields.io/badge/中文-支持-ff6600" alt="中文支持">
  <br>
  <b>🤖 给你的 AI Agent 一套真正的教学引擎 —— 而不只是一段提示词。</b>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README_CN.md">中文</a> ·
  <a href="docs/i18n/README.ja.md">日本語</a> ·
  <a href="docs/i18n/README.ko.md">한국어</a> ·
  <a href="docs/i18n/README.fr.md">Français</a> ·
  <a href="docs/i18n/README.es.md">Español</a> ·
  <a href="docs/i18n/README.ru.md">Русский</a> ·
  <a href="docs/i18n/README.ar.md">العربية</a>
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
pytest -q        # 260 passed
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

58 个工具，走 stdio，按领域分组：

| 分组 | 示例 |
|---|---|
| 会话与目标 | `create_session`、`save_learning_goal`、`set_learning_configuration` |
| 诊断 | `generate_diagnostic`、`submit_diagnostic`、`save_diagnostic_result` |
| 知识 | `decompose_topic`、`save_knowledge_nodes`、`validate_knowledge_dag` |
| 策略 | `get_teaching_context`、`evaluate_pedagogical_policy`、`commit_pedagogical_decision` |
| 评估 | `generate_assessment`、`assess_response`、`assess_misconception` |
| 保持 | `schedule_review`、`get_due_reviews`、`submit_review` |
| 状态守卫 | `start_unit`、`check_advance_unit`、`advance_unit`、`rollback_unit` |
| 证据 | `save_benchmark_report`、`get_evidence`、`validate_claim` |
| 工件 | `save_artifact`、`get_obsidian_structure`、`get_web_component_spec` |
| 报告 | `generate_final_report`、`get_learning_metrics` |

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

五个单文件教学页面，均通过静态检查与 headless Chromium 运行时校验：

| 示例 | 学科 |
|---|---|
| `examples/01-python-recursion/` | 编程 —— Python 递归 |
| `examples/02-math-linear-equation/` | 数学 —— 一元一次方程 |
| `examples/03-cs-osi-model/` | 计算机基础 —— OSI 模型 |
| `examples/04-physics-free-fall/` | 物理 —— 自由落体 |
| `examples/05-logic-flowchart/` | 逻辑 —— 流程图 |

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
├── examples/                # 五个教学页面 + 共享规范
├── docs/                    # 架构、接入、多语言
├── scripts/                 # 校验器、扫描器、审计器
└── tests/                   # 260 项测试
```

## 🔍 质量门禁

```bash
pytest -q                                        # 260 项测试
python scripts/security_scan.py --root .         # 密钥与个人信息（CI 门禁）
python scripts/verify_example.py --all           # 示例静态规范符合性
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
| [`README.md`](README.md) | English |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 架构与设计决策 |
| [`docs/INTEGRATION.md`](docs/INTEGRATION.md) | 宿主 Agent 接入指南 |
| [`docs/EXAMPLES.md`](docs/EXAMPLES.md) | 五个教学页面及其契约 |
| [`docs/i18n/`](docs/i18n/) | 多语言翻译 |
| [`CHANGELOG.md`](CHANGELOG.md) | 版本历史 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 如何参与贡献 |
| [`SECURITY.md`](SECURITY.md) | 漏洞报告方式 |

> 权威的框架设计文档与视觉设计规范由项目作者另行维护，**不包含在本仓库**。
> 本仓库的实现遵循这些文档。

## 🤝 参与贡献

欢迎提交 issue 与 pull request。请先阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 📄 许可证

[MIT](LICENSE) © Vinger-lee
