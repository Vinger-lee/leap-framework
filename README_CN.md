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

Related: [Knowledge_Index](Knowledge_Index.md) · [docs/teaching-delivery](docs/teaching-delivery.md)

# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/github/v/release/Vinger-lee/leap-framework" alt="Release">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-75%20tools-22bb33" alt="MCP 工具">
  [![Tests](https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml)
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
运行测试：

```bash
pytest -q        # 运行完整测试套件
```

启动 MCP Server：

```bash
python -m leap.server      # 或：leap-mcp
```

### 📦 作为包安装

```bash
pip install "leap-framework"          # 需要验证教学页面时再加 [examples]
leap-doctor                           # 安装自检
leap-mcp --tool-profile quickstart    # stdio MCP Server（默认档位：full）
```

pip 安装的 wheel 内已包含同一份默认配置（`leap/config/default.yaml`），因此无需仓库检出即可运行
`leap-doctor` 与 server。配置优先级从低到高：

- YAML 文件 —— 仓库内的 `config/default.yaml`，否则使用打包副本；
- 环境变量覆盖，如 `LEAP__DATABASE_PATH`、`LEAP__ARTIFACT_ROOT`、`LEAP__TOOL_PROFILE`（嵌套键用双下划线）；
- 工具档位 —— `--tool-profile`、`LEAP_TOOL_PROFILE` 或配置里的 `tool_profile`。

`database_path` 与 `artifact_root` 在设置 `LEAP_HOME` 时相对该目录解析，否则相对当前工作目录解析 ——
永远不会落到安装目录里，所以 `data/leap.db` 与 `artifacts/` 不会写进 `site-packages`。稳定部署建议把
`LEAP_HOME` 指向可写目录：

```bash
LEAP_HOME=/var/lib/leap leap-mcp --tool-profile quickstart
```

**工具档位**：`full` 暴露完整工具目录（默认）；`quickstart` 暴露面向小宿主的粗粒度教学路径。
`leap-doctor` 会打印当前安装版本的档位数量。

**Agent Skill（可选）**：支持仓库技能的宿主可直接打开 `.agents/skills/leap-tutor/`（配置样例见
[docs/host-config.md](docs/host-config.md)）；不支持 Skill 的宿主按集成指南接入。两种方式的运行时门禁完全一致
—— Skill 只改变 Agent 的引导方式，不改变服务端允许的操作。

内置教学页面的验证依赖、命令和验收规则统一见 [贡献指南](CONTRIBUTING.md)。

## 🧠 学习闭环

```
1. 目标定义
2. 领域校准            ← Agent 阅读预审来源并独立解答检查题
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

完整工具名称、参数、宿主说明和档位归属统一见 [自动生成的 MCP 工具参考](docs/mcp-tools.md)。

粗粒度 API 在服务端组合教学步骤，每个回包给出下一次调用 `next_call`。State Guard 负责推进裁决；
被拒的推进不写状态，评估失败保留已提交作答，掌握度由服务端估计。初次接入推荐显式选择
`--tool-profile quickstart`；默认档位保持 `full`。使用方式见 [粗粒度 API 与工具档位](docs/FACADE_CN.md)，
能力边界见 [范围与边界](docs/scope-and-limits_CN.md)。

支持仓库技能的宿主可加载 [leap-tutor](.agents/skills/leap-tutor/SKILL.md)，
按需读取学习生命周期、内容制作与恢复参考。接入与验收见 [docs/agent-skill.md](docs/agent-skill.md)，
可直接复制的 `mcpServers` 配置样例与各宿主发现规则（例如 Claude Code 扫描 `.claude/skills`
而不是 `.agents/skills`）见 [docs/host-config.md](docs/host-config.md)。Skill 仍是草案，
宿主发现、激活与 MCP 连接需要分别验证。`quickstart` 支持记录新误解、恢复拆分评估与
显式结课。已关闭的会话不再建议教学调用。回包只带紧凑的 `policy_version`
而非完整政策，`continue_lesson` 默认只返回摘要（`verbose=True` 才展开）。现有 HTML outbox
桥接仍需 `full` 档位。

两档使用同一预审来源库。首个单元是「从极限到导数与可导性」。用 `start_learning(..., topic="高等数学")` 建会话，再用 `get_grounding_sources(session_id)` 获取片段和检查题。实际阅读每个原文定位并独立解答检查题后，通过 `save_benchmark_report` 提交阅读与复核记录、`course_revision`、全部 `chunk_id` 和以检查 ID 映射到答案字符串的 `check_answers`。旧宿主自证和跳过请求会被拒绝。来源未收录、过期或撤回时暂停正式授课。

校准后调用 `get_grounding_sources(session_id, include_lesson=True)`。用 `save_knowledge_nodes` 登记 `.lesson.node`，用 `save_teaching_package` 原样登记返回的 `subject`、`markdown`、`html` 和 `manifest`，再用 `save_assessment_item` 登记预审题目，带实际会话、节点、唯一题目 ID 与教学包 ID。自由文本由宿主做语义评阅。A4 正式版使用 `.lesson.print_draft`，带会话、节点和教学包 ID 调用 `save_print_materials`。

重启后沿用同一 SQLite 数据库可恢复校准回执和历史学习记录。首包复核期限为 180 天。维护者可按需运行 `python scripts/review_grounding_sources.py` 预查已批准链接与定位，人工核准并发布更新后重启 MCP。新编内容可通过 full 的 `save_artifact(artifact_type="teaching_draft", ...)` 保存为待审草稿。详见[宿主接入指南](docs/INTEGRATION_CN.md)。

参见[内容质量与真实联调流程](docs/content-quality.md)及[本次交付物审计](docs/quality-audit-2026-10-10.md)。浏览器场景、真实 MCP 联调、内容审校分别验收。

交付政策涵盖内容深度、可控图示、宽屏、完整 Obsidian 知识源和精准资源。学科目录可参考，八个仓库示例可离线预览。详见[交付政策](docs/teaching-delivery.md)和[学科知识地图](docs/subject-knowledge-map.md)。

## A4 打印资料

通过宿主 Agent 导出整套课程时，默认在 `~/LEAP/课程输出/课程名/` 保存教学课件 HTML、
讲义册、题目册、答案与解析、合订册。文件名均带课程标题。

打开[一元一次方程交互课程](examples/02-math-linear-equation/leap-02-math-linear-equation.html)，
在「打印资料」里选择版式，再点「导出 PDF」。默认是 A4 纵向合订册，讲义和练习分开起页。
也可以直接打开[配图讲义](print-examples/linear-equations/handout.html)、
[题目册](print-examples/linear-equations/workbook.html)和[同版本答案解析](print-examples/linear-equations/answers.html)。
离线打印、预审材料的 MCP 导出及命令行用法见 [A4 打印指南](docs/printing.md)。

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

完整验证顺序、浏览器依赖安装和通过判据统一见 [贡献指南](CONTRIBUTING.md)；自动执行范围由
`.github/workflows/ci.yml` 定义。工具目录由 CI 对照自动生成参考逐字节校验。

AI 助手工作区和本地临时目录不参与发布；`.gitignore`、扫描器与 CI 测试共同检查索引及历史中未包含此类文件。

## 📖 文档

| 文档 | 内容 |
|---|---|
| [README.md](README.md) | English |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构与设计决策 |
| [docs/INTEGRATION.md](docs/INTEGRATION.md) | 宿主 Agent 接入指南 |
| [docs/EXAMPLES.md](docs/EXAMPLES.md) | 八个教学页面及其契约 |
| [`docs/i18n/`](docs/i18n/) | 多语言翻译 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 如何参与贡献 |
| [SECURITY.md](SECURITY.md) | 漏洞报告方式 |

> 权威的框架设计文档与视觉设计规范由项目作者另行维护，**不包含在本仓库**。
> 本仓库的实现遵循这些文档。

## 🤝 参与贡献

欢迎提交 issue 与 pull request。请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 📄 许可证

[MIT](LICENSE) © Vinger-lee

> [!note]- Reading and verification sequence: LEAP 🎓 LEAP Framework
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[Knowledge_Index](Knowledge_Index.md) · [README](README.md) · [docs/ARCHITECTURE_CN](docs/ARCHITECTURE_CN.md) · [docs/FACADE_CN](docs/FACADE_CN.md) · [docs/i18n/README.ar](docs/i18n/README.ar.md) · [docs/i18n/README.es](docs/i18n/README.es.md) · [docs/i18n/README.fr](docs/i18n/README.fr.md) · [docs/i18n/README.ja](docs/i18n/README.ja.md) · [docs/i18n/README.ko](docs/i18n/README.ko.md) · [docs/i18n/README.ru](docs/i18n/README.ru.md) · [docs/scope-and-limits_CN](docs/scope-and-limits_CN.md) · [docs/teaching-upgrade-plan](docs/teaching-upgrade-plan.md) · [examples/01-python-recursion/knowledge](examples/01-python-recursion/knowledge.md) · [examples/05-logic-flowchart/knowledge](examples/05-logic-flowchart/knowledge.md)
