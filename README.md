# LEAP Framework V2.0

**Learning Evolution & Adaptation Pipeline** —— 面向 AI Agent 的 **Agentic Intelligent Tutoring System（智能导师引擎）** 基础架构。

**语言 / Language**：**简体中文** ｜ [English](README.en.md)

> LEAP 的核心不是让大模型"更像老师"，而是为 Agent 提供一套**可执行、可持久化、可审计、可迭代**的学习闭环：
> **理解目标 → 领域校准 → 诊断学习者 → 建立知识结构 → 估计学习状态 → 选择教学策略 → 执行教学动作 → 获取评估证据 → 更新状态 → 安排保持与迁移 → 进入下一轮决策**

```
Learner
   ↓
Host Agent（推理 / 生成 / 交互 / 多模态）
   ↓  MCP (stdio)
LEAP MCP Server（工具接口 / 请求校验）
   ↓
LEAP Learning Runtime
   Goal · Diagnostic · Knowledge DAG · State Estimation
   Policy · Assessment · Retention/Transfer · State Guard
   ↓
Persistence（SQLite / Artifact Store / Event Log）
```

---

## 1. 核心设计原则

| 原则 | 含义 |
|---|---|
| **三层分离** | 循证原则（Level 1）→ 教学策略（Level 2）→ 工程参数（Level 3）。所有阈值都是可配置启发值，不是"科学最优值" |
| **状态驱动** | Session 只是容器，**Learner State 才是教学决策的主要输入**。不存在"讲解 10 分钟 → 提问"这类硬编码节奏 |
| **Prompt 引导行为，服务端保证一致性** | 掌握状态、前置依赖、评估完成度、迁移证据、复习状态、单元能否结束，全部由 **Server-side State Guard** 最终校验 |
| **"答对" ≠ "学会"** | 一次正确只产生一条证据。内部证据模型：`estimated → practiced → demonstrated → retained → transferred`，**允许回退** |
| **渐进式答案披露** | 答案是一种教学资源，不是永久禁止的输出。先保留思考空间 → 检测困难 → 适度支持 → 必要时完整示范 → **后置验证** |
| **保持与迁移是最终证据** | 不把"本轮任务成功"当作最终结果。Retention 与 Transfer 是**互补的两个长期证据维度**，不必严格线性 |
| **模型无关** | 不绑定 GPT / Claude / Gemini / Qwen 等任何具体模型 |

---

## 2. 快速开始

### 环境要求

- Python ≥ 3.11
- 无外部服务依赖（P0 为纯本地进程）

### 安装

```bash
git clone <repo-url>
cd LEAP_Framework
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest
```

### 启动 MCP Server（stdio）

```bash
python -m leap.server
# 或安装后
leap-mcp
```

### 发布前隐私自检

```bash
python scripts/security_scan.py --root . --md reports/security-scan.md
```

退出码 `0` 干净 / `1` 有 P0+P1（阻断发布）/ `2` 仅有 P2。可直接接入 CI。

> **不参与上传的内容**：AI 助手工作区（`.workbuddy-ai/`、`.claude/`、`.cursor/` 等）、
> 本地归档（`_archive/`）、缓存与本地运行数据。由 `.gitignore` + 扫描器规则 `AI001` +
> 测试 `TestAiWorkspaceIsolation` 三重保障。详见 [`docs/README.md`](docs/README.md)。

### 校验前端示例

```bash
python scripts/verify_example.py --all                    # 静态规范符合性
python scripts/verify_example_runtime.py --all            # 运行时行为 + JSON Schema
```

前者检查结构与契约（零依赖），后者用 headless Chromium 真实执行页面，校验
`window.LEAP.getInteractionResult()` 的返回值是否符合 `interaction-output.schema.json`。
后者需要 `playwright` 与一个 Chromium，可用 `--chromium <path>` 指定浏览器。

---

## 3. 目录结构

```
LEAP_Framework/
├── config/default.yaml          # 全部工程参数（可被 Policy 覆写）
├── src/leap/
│   ├── config.py                # 配置加载（YAML + 环境变量 + 覆盖）
│   ├── i18n.py                  # 多语言消息目录（zh-CN / en）
│   ├── server.py                # MCP Server（stdio），58 个工具
│   ├── runtime/                 # 服务端决策核心
│   │   ├── contracts.py         #   §35 六个可插拔协议
│   │   ├── plugins.py           #   实现注册表（配置选择实现）
│   │   ├── bkt.py               #   简化遗忘感知 BKT 估计器
│   │   ├── scoring.py           #   多维评分聚合（§10.3-1）
│   │   ├── evidence.py          #   Evidence Stage 升级/回退启发式
│   │   ├── scheduler.py         #   py-fsrs 复习调度
│   │   ├── state_guard.py       #   状态守卫（唯一有权批准迁移者）
│   │   ├── policy.py            #   教学策略决策引擎（含 §31 交错练习）
│   │   ├── learning_modes.py    #   §32 自定义学习模式与策略覆写
│   │   ├── metrics.py           #   §26 学习效果评测指标
│   │   └── events.py            #   事件日志
│   ├── storage/                 # SQLite schema + 连接/事务/幂等
│   ├── tools/                   # 工具实现（按领域分模块）
│   └── specs/                   # Obsidian / Web 组件静态规范
├── tests/                       # 244 项测试
├── scripts/
│   ├── security_scan.py         # 隐私与密钥扫描器（CI 门禁）
│   ├── verify_example.py        # 前端示例静态规范符合性检查
│   ├── verify_example_runtime.py# 前端示例运行时检查（headless + JSON Schema）
│   └── apply_leap_bridge.py     # 给示例注入宿主桥接（幂等 / 可撤销）
├── examples/                    # 前端交互示例（由 Host Agent 生成）
└── reports/                     # 分阶段实施报告
```

---

## 4. 学习生命周期

```
1. Goal Specification
2. Domain Grounding【Agent 领域自学校准】   ← 默认强制前置
3. Learner Diagnostic                      ← 受 State Guard 保护
4. Knowledge Representation（DAG）
5. Learner State Initialization
6. Dynamic Teaching Loop
   Read State → Policy → Action → Attempt → Assessment → State Update
7. Retention（FSRS 复习调度）
8. Transfer（近迁移 → 变式 → 远迁移 → 综合任务）
9. Reflection & Persistence
```

### Domain Grounding（默认强制）

正式教学前，宿主 Agent 必须先对目标专题完成自学习，产出《Agent 内部知识基准报告》。

- **收益**：极大降低幻觉，教学内容事实准确性更高
- **代价**：消耗更多 Token、增加前期等待时间
- **可跳过**：`allow_skip_domain_grounding=true`（**per-session** 配置），但会升高内容出错风险，开启前必须向用户明示

未完成校准且未开启跳过时，`generate_diagnostic` 会被 State Guard 拒绝。

---

## 5. 关键机制

### 5.1 `mastery_probability` 由服务端计算

掌握度是**模型估计值，不是事实真值**。P0 由 Runtime 内置简化遗忘 BKT 计算，**不由 Host Agent 的 LLM 输出概率**（避免数值不稳定）。

单次更新四步：时间衰减 → 证据更新（guess/slip 后验）→ 状态转移 → 自发遗忘。

- 支持**部分得分**：`s·P(正确) + (1-s)·P(错误)`
- 支持**低置信度降权**：评估不确定时把观测拉回先验，**不允许把"不确定"写成 `mastery = 0`**

### 5.2 Evidence Stage 允许回退

| 阶段 | 参考默认判据 |
|---|---|
| `estimated` | 仅通过 DAG / 诊断间接推断，无该 node 的答题证据 |
| `practiced` | ≥1 次有效尝试，且 `hint_dependency < 0.9` |
| `demonstrated` | `mastery ≥ 0.8`、`hint_dependency ≤ 0.5`，且至少一次低提示成功 |
| `retained` | 已达 `demonstrated`，且经过配置间隔后复习仍达标 |
| `transferred` | 完成至少一次 transfer probe，且得分 `≥ 0.7` |

回退：长期未接触 → 退回 `practiced` 并重新进入复习队列；新场景失败 → 退回 `demonstrated`。

> 判据位于 **Policy 层且可配置**；State Guard 只读取最终 `evidence_stage`，不强制校验升级条件。

### 5.3 `advance_unit` 是批量业务封装

- **数据层唯一实体是 `knowledge_node`**；`unit` 只是业务聚合标签（`knowledge_nodes.unit_tag`），**不建 unit 表**
- `advance_unit` 遍历该 unit 下全部 node，**逐个执行 node 级 State Guard 校验，任一不过则整体拒绝**
- 7 项检查：`prerequisites_met` / `assessment_sufficient` / `evidence_sufficient` / `transfer_required` / `transfer_completed` / `current_state_version_valid` / `manual_override`

### 5.4 权威源与缓存

| 语义 | 权威源 | 缓存字段 |
|---|---|---|
| 错误概念 | `misconceptions` 表 | `learner_knowledge_state.misconception_state` |
| 复习状态 | `review_items` 表 | `learner_knowledge_state.next_review_at` |
| 证据阶段 | `learner_knowledge_state.evidence_stage` | `assessment_results.evidence_stage`（单次快照，不可修改） |

缓存字段由 Runtime 自动刷新，**禁止业务代码直接写入**。

### 5.5 到期复习不全局阻塞

存在到期复习项 **不等于**必须阻断全部新知识。是否插入、优先或阻塞由 Policy + State Guard 按节点决定。

---

## 6. 工程参数

`config/default.yaml` 收录全部参数，**每一项都是 engineering heuristic，Policy 可以全部覆写**。常用项：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `mastery_threshold` | `0.80` | 掌握阈值（初始工程值） |
| `max_hint_level` | `3` | 提示层级 |
| `max_retry_before_example` | `3` | 触发示范的失败次数 |
| `friction_window` | `3` | 摩擦观察窗口，**单位 = attempt 次数** |
| `reasoning_quality_low` | `0.5` | 低于此视为推理质量显著偏低 |
| `hint_dependency_high` | `0.7` | 高于此视为高提示依赖 |
| `overall_score_weights` | `0.4/0.3/0.2/0.1` | correctness / conceptual / reasoning / application |
| `review_scheduler` | `py-fsrs` | 复习调度器，rating 1–4 |
| `mcp_transport` | `stdio` | P0 仅本地进程 |
| `auth_enabled` | `false` | P0 单机本地信任环境 |

`transfer` 与 `hint_dependency` **不参与** `overall_score` 聚合，单独作为 Policy 输入。

---

## 6.1 多语言适配

运行时内置 i18n 层，**学习者与运维人员会读到的文本**全部走消息目录，不硬编码：

| 已本地化 | 未本地化（有意为之） |
|---|---|
| State Guard 拒绝原因 | 代码注释、日志、异常类型 |
| 领域校准提示文案 | 工具名、字段名、枚举值 |
| 学习模式名称与描述 | Policy 决策理由（内部审计用） |
| 结业报告标题与小节名 | |

```yaml
locale: zh-CN          # 支持 zh-CN | en
```

也可用环境变量覆盖：`LEAP_LOCALE=en`。语言只影响文案，**不改变任何状态迁移行为**。

新增语言的步骤见 [`docs/i18n.md`](docs/i18n.md)。测试会强制两份目录的**键集合完全一致**，缺翻译不会静默漏出原始 key。

---

## 7. P0 交付边界

### ✅ 已实现

1. LEAP MCP Server（stdio）+ SQLite
2. 完整工具集（58 个）
3. Server-side State Guard
4. 内置简化遗忘 BKT
5. FSRS（`py-fsrs`）复习调度
6. 事件日志与决策日志
7. Artifact 存储
8. 静态规范输出（Web 组件规范 / Obsidian 目录规范）
9. 隐私扫描器 + 测试套件

### ❌ P0 不交付

> Web 前端页面、真实 Obsidian 库读写代码、完整参考 Agent 程序。
> **MCP 只输出规范，生成文件全部交给宿主 Agent 完成。**

### 后续阶段

- **P1**：参考最小 Host Agent 示例代码、外部估计器（模式 B）、多维 Rubric 扩展
- **P2**：HTTP / SSE 传输、认证、多租户、Teacher Dashboard

---

## 8. 文档

| 文档 | 内容 |
|---|---|
| （作者维护的框架设计文档，不在本仓库） | 完整框架设计（42 节；权威文档不在本仓库） |
| **教学界面视觉规范**。示例必须与作者维护的视觉规范对齐；该规范不在本仓库。 |
| [`docs/`](docs/README.md) | 文档索引 |
| [`docs/host-agent-system-prompt.md`](docs/host-agent-system-prompt.md) | 宿主 Agent 接入指南（中文） |
| [`docs/host-agent-system-prompt.en.md`](docs/host-agent-system-prompt.en.md) | Host Agent integration guide (English) |
| [`docs/i18n.md`](docs/i18n.md) | 多语言适配说明 |
| [`examples/`](examples/README.md) | 5 个学科前端示例 + 规范 + 验收脚本 |
| [`reports/`](reports/) | 分阶段实施报告 |

---

## 9. 许可证

[MIT](LICENSE)
