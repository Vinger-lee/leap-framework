# 架构

**语言**：[English](ARCHITECTURE.md) ｜ 中文

> 权威的框架设计文档与视觉设计规范由项目作者另行维护，**不包含在本仓库**。
> 本文档描述本仓库的实现架构。

---

## 1. 分层

```
学习者
   ↓
宿主 Agent —— 推理、生成、交互、多模态
   ↓  MCP (stdio)
LEAP MCP Server —— 工具接口、请求校验、错误映射
   ↓
LEAP Learning Runtime
   目标 · 诊断 · 知识 DAG · 状态估计
   策略 · 评估 · 保持 · 迁移 · 状态守卫
   ↓
持久化 —— SQLite · 工件 · 只追加事件日志
```

分层是有意为之的：**Prompt 引导行为，服务端保证一致性。**
所有不允许在会话间漂移的东西 —— 掌握度、前置依赖、评估充分性、迁移证据、复习状态、
知识点能否结束 —— 都由服务端裁决。

## 2. 设计原则

| 原则 | 后果 |
|---|---|
| 三层分离 | 循证原则 → 教学策略 → 工程参数。所有阈值都是可配置启发值，不是"科学最优值" |
| 状态驱动 | Session 只是容器，**学习者状态才是教学决策的输入**。不存在硬编码的讲解节奏 |
| 服务端权威 | State Guard 是唯一有权批准状态迁移的组件 |
| 答对 ≠ 学会 | 一次正确只产生一条证据；证据阶段会回退 |
| 渐进式披露 | 答案是一种教学资源：保留思考空间 → 检测困难 → 适度支持 → 必要时示范 → **后置验证** |
| 保持与迁移才是证据 | 本轮任务成功不等于学习结果 |
| 模型无关 | 不绑定任何具体大模型 |

## 3. 运行时子系统

| 子系统 | 模块 | 职责 |
|---|---|---|
| 状态估计 | `runtime/bkt.py` | 遗忘感知 BKT；掌握度在此计算，不由 LLM 输出 |
| 证据阶段 | `runtime/evidence.py` | `estimated → … → transferred` 的升级/回退启发式 |
| 教学策略 | `runtime/policy.py` | 依状态选择策略与动作；含交错练习与会话级覆写 |
| 状态守卫 | `runtime/state_guard.py` | 唯一迁移裁决者；返回结构化的允许/拒绝 |
| 复习调度 | `runtime/scheduler.py` | 基于 FSRS 的间隔重复，评分 1–4 |
| 学习模式 | `runtime/learning_modes.py` | 学习者提出的模式 → 会话级策略覆写 |
| 效果指标 | `runtime/metrics.py` | 学习效果指标 |
| 插件注册表 | `runtime/plugins.py` | 依配置解析六个接缝 |
| 契约 | `runtime/contracts.py` | 替换实现必须满足的协议 |
| 事件 | `runtime/events.py` | 只追加日志；每个决策都可回放 |

## 4. 数据模型

SQLite，教学实体只有 `knowledge_node`。**unit 是业务聚合标签**（`knowledge_nodes.unit_tag`），
不建表。

| 关注点 | 权威源 | 缓存字段 |
|---|---|---|
| 错误概念 | `misconceptions` | `learner_knowledge_state.misconception_state` |
| 复习状态 | `review_items` | `learner_knowledge_state.next_review_at` |
| 证据阶段 | `learner_knowledge_state.evidence_stage` | `assessment_results.evidence_stage`（单次快照） |

缓存字段由 Runtime 刷新，业务代码不直接写入。

**全项目时间戳为 Unix 秒。** 由于同一秒内可能有多个事件，任何"前后切分"（例如诊断基线
与后测）都必须用事件日志的追加顺序，不能只依赖时间戳。

Schema 变更是增量的：`CREATE TABLE IF NOT EXISTS` 不会修改已有表，因此新列登记在
`ADDED_COLUMNS` 中，由 `Database._migrate()` 施加。

## 5. 请求流程

1. `create_session` —— 若返回 `domain_grounding_notice`，Agent 必须向学习者明示
   （Token 成本、等待时间、跳过风险）并让其选择。
2. 领域校准 —— Agent 先学习该专题，再 `save_benchmark_report`。
3. `save_learning_goal`，然后 `generate_diagnostic` / `submit_diagnostic`。
4. `decompose_topic` 返回**模板**；Agent 撰写节点与边并提交，服务端校验 DAG。
5. 教学循环：`get_teaching_context` → `commit_pedagogical_decision` → `submit_attempt` →
   `commit_assessment` → `get_mastery_status`。
6. `check_advance_unit`（干跑）→ `advance_unit`，或 `rollback_unit`。
7. `schedule_review` / `get_due_reviews` / `submit_review`，以及 `generate_transfer_probe`
   与 `record_transfer_result`。
8. `record_reflection` → `generate_final_report` → `complete_session`。

## 6. 错误模型

失败的工具返回 `{ ok: false, error: { code, message, details } }`。常见 code：
`domain_grounding_required`、`state_guard_rejected`、`invalid_knowledge_dag`、
`invalid_argument`、`invalid_score`、`unknown_session`。

**失败的调用永远不会变成一次静默的状态更新。**

## 7. 扩展点

见 [`README.md`](../README_CN.md#-可插拔设计)。每个接缝都是 `runtime/contracts.py` 里的一个
`Protocol`；实现按 kind 注册到 `runtime/plugins.py`，由 `config/default.yaml` 按名字选择。

## 8. 多语言

面向学习者的文案通过 `src/leap/i18n.py` 解析：当前语言 → 默认语言 → key 本身，
因此缺翻译会降级而不是抛异常。工具名、字段名、枚举值有意不翻译。
见 [`LOCALIZATION_CN.md`](LOCALIZATION_CN.md)。

## 9. 质量门禁

| 门禁 | 命令 |
|---|---|
| 测试 | `pytest -q` |
| 密钥与个人信息 | `python scripts/security_scan.py --root .` |
| 示例静态规范符合性 | `python scripts/verify_example.py --all` |
| 示例运行时符合性 | `python scripts/verify_example_runtime.py --all` |
| 规范覆盖率 | `python scripts/spec_coverage.py` |
| 宿主桥接完整性 | `python scripts/apply_leap_bridge.py --check` |

退出码：`0` 干净 / `1` 阻断 / `2` 仅警告。前四项在 CI 中每次 push 都会跑。

## 10. 发布卫生

AI 助手工作区与本地临时目录永不进入提交。由三层保障：

1. `.gitignore` 覆盖整个类别，并用通配形式防变体名。
2. 扫描器规则 `AI001` 基于路径，即使 `.gitignore` 被绕过也会触发。
3. `tests/test_infrastructure.py::TestAiWorkspaceIsolation` 查询 `git ls-files` 与全部提交
   历史并断言此类文件为 0；CI 每次 push 都会跑。
