# Step 02 · P0 工程骨架与数据库落地

- **日期**：2026-09-19
- **对应任务**：#2
- **状态**：✅ 完成

---

## 1. 目标

按计划书 §36 的 P0 交付边界，把"文档"落成"可运行的工程骨架"：包结构、配置加载、SQLite 全量 Schema。

## 2. 目录结构

```
LEAP_Framework/
├── config/
│   └── default.yaml              # §30 全部默认工程参数
├── src/leap/
│   ├── __init__.py
│   ├── config.py                 # 配置加载（YAML + 环境变量 + 覆盖）
│   └── storage/
│       ├── __init__.py
│       ├── schema.sql            # §23 全部表结构
│       ├── seed.sql              # §9 策略库种子数据
│       └── database.py           # 连接 / 事务 / 幂等
├── scripts/security_scan.py
├── reports/
├── examples/
├── pyproject.toml
├── LICENSE
└── .gitignore
```

## 3. 数据库 Schema（§23 全量落地）

共 **20 张表** = 计划书 §23 定义的 18 张 + 2 张工程辅助表。

**业务表 18 张**：`learners`、`learning_sessions`、`learning_goals`、`knowledge_nodes`、`knowledge_edges`、`learner_knowledge_state`、`misconceptions`、`assessment_items`、`learning_attempts`、`assessment_results`、`transfer_results`、`pedagogical_strategies`、`pedagogical_decisions`、`review_items`、`evidence_sources`、`benchmark_claims`、`event_log`、`artifacts`

**工程辅助表 2 张**：`request_log`（§19.4 幂等）、`schema_meta`（版本元数据）

### 3.1 已落实的关键修订决议

| 决议 | 落地方式 |
|---|---|
| Unit 不建表 | `knowledge_nodes.unit_tag TEXT`，无独立 `units` 表 |
| Domain Grounding per-session | `learning_sessions` 含 `allow_skip_domain_grounding` / `domain_grounding_warn_user` / `domain_grounding_stage` |
| 基准报告存 artifacts | `learning_sessions.benchmark_report_artifact_id` → `artifacts.artifact_id` |
| 时间戳统一 Unix 秒 | 全部 `*_at` 字段为 `INTEGER` |
| 权威源 vs 缓存 | `misconception_state`（缓存）/ `misconceptions`（权威）；`next_review_at`（缓存）/ `review_items`（权威）；`evidence_stage` 双处语义已分表 |
| `raw_answer` 不可丢弃 | `assessment_results.raw_answer TEXT NOT NULL` |
| `assessor_type` 审计 | CHECK 约束限定 5 种取值 |
| `dag_version` 属 P1 | 字段已预留，P0 允许为空 |
| 乐观并发 | `learning_sessions.state_version INTEGER` |

### 3.2 额外加固（超出文档但必要）

- **`assessment_results` 增加 `transfer` 列** —— §10.3 的多维评估含 `transfer` 维度，但 §23.10 表定义遗漏。按 §10.3 补齐。
- **`review_items` 增加 `difficulty` 列** —— FSRS-6 算法需要 difficulty 参数，§13.3 表定义未列。按 FSRS 实现补齐。
- **`knowledge_nodes` / `assessment_items` 增加 `session_id`** —— 否则无法按会话隔离知识结构。
- **外键约束 + 索引**：为所有高频查询路径建立索引（learner+node、session+created_at、learner+next_review_at 等）。
- **枚举 CHECK 约束**：`status`、`relation_type`、`evidence_stage`、`assessor_type`、`transfer_type`、`last_rating(1-4)` 全部加约束，防止脏数据。

## 4. 配置系统

`config/default.yaml` 收录 §30 全部参数，并补充：

- **BKT 参数组**（文档未给具体值，属实现缺口）：`p_init=0.20`、`p_transit=0.30`、`p_guess=0.20`、`p_slip=0.10`、`p_forget=0.02`、`forget_halflife_days=30`。均为标准 BKT 启发值，**已在文件注释中标注为 engineering heuristic**。
- **FSRS 参数组**：`desired_retention=0.90`、`maximum_interval_days=365`、`scheduler_version=fsrs-6`。
- **`transfer_pass_score=0.70`** —— 对齐 §11.4 中 `transferred` 的判据。

配置加载优先级：`default.yaml` → 环境变量（`LEAP__BKT__P_INIT=0.25`）→ 显式覆盖。

## 5. 验证结果

```
tables: 20
strategies seeded: 10
schema_version: 2.0.0
mastery_threshold: 0.8
bkt.p_init: 0.2
weights: {'correctness': 0.4, 'conceptual_understanding': 0.3, 'reasoning_quality': 0.2, 'application': 0.1}
mcp_transport: stdio
```

Schema 可重复执行（全部 `IF NOT EXISTS` / `ON CONFLICT DO NOTHING`），`initialize()` 幂等。

## 6. 依赖

已在隔离 venv 中安装并验证：

| 包 | 版本 | 用途 |
|---|---|---|
| `mcp` | 2.2.0 | MCP 协议（stdio） |
| `fsrs` | 6.3.2 | §13 复习调度 |
| `PyYAML` | 6.0.3 | 配置 |
| `pytest` | 9.1.1 | 测试 |

> 注意：内部镜像源无 `mcp` 包，需显式使用 `-i https://pypi.org/simple`。

## 7. 下一步

任务 #3：核心 Runtime —— State Guard（§19）、简化遗忘 BKT（§10.2-1）、FSRS 调度（§13）、Policy 引擎骨架（§8）、Evidence Stage 启发式（§11.4）。
