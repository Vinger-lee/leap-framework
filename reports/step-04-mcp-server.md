# Step 04 · MCP Server（stdio）与工具集

- **日期**：2026-09-19
- **对应任务**：#4
- **状态**：✅ 完成

---

## 1. 目标

把 Runtime 暴露给任意宿主 Agent。落实 §3.1 的 P0 传输边界：**仅 stdio 本地进程，无 HTTP/SSE，无鉴权**。

## 2. 分层设计

关键决策：**业务逻辑与传输层彻底分离**。

```
leap/server.py          ← MCP 适配层（薄，只做注册 + 错误转换）
        ↓
leap/tools/*.py         ← 工具实现（纯 Python，可脱离传输层测试）
        ↓
leap/runtime/*.py       ← 决策核心
        ↓
leap/storage/*.py       ← 持久化
```

好处：136 项测试全部直接调用 `LeapService`，**不需要起 MCP 进程**，测试 2.4 秒跑完。

### 模块划分（按领域，非按工具名）

| 文件 | 工具 |
|---|---|
| `tools/base.py` | 上下文注入、幂等、错误类型、通用校验 |
| `tools/session.py` | 会话 / 目标 / 诊断（9 个） |
| `tools/knowledge.py` | 知识 DAG + 校验引擎（6 个） |
| `tools/assessment.py` | 多维评估 / 状态更新 / 错误概念 / 迁移（10 个） |
| `tools/retention.py` | 复习调度（5 个） |
| `tools/teaching.py` | 教学上下文 / 策略 / 状态守卫（11 个） |
| `tools/evidence.py` | 领域校准与证据（5 个） |
| `tools/artifact.py` | 工件 / 规范 / 报告（7 个） |

## 3. 工具注册结果

```
registered tools: 54
tools without description: []
```

54 个工具全部带描述（描述会直接成为宿主 Agent 看到的工具说明，因此按"什么时候用、返回什么"来写，而不是按函数名复述）。

覆盖 §22 全部 10 组：Session/Goal、Diagnostic、Knowledge、Teaching Context、Policy、Assessment、Retention、State Guard、Evidence/Grounding、Artifact。另加 6 个工程必要工具：`check_advance_unit`（干跑校验）、`resolve_misconception`、`list_artifacts`、`complete_session` 等。

## 4. 关键契约实现

### 4.1 强制 DAG 校验（§22.3）

`save_knowledge_edges` 在校验**合并后的完整图**（已有边 + 新边）通过后才落库。校验失败 → 抛 `invalid_knowledge_dag` → **一条边都不写**。

实测：

| 场景 | 结果 |
|---|---|
| 合法链 n1→n2→n3 | ✅ 通过 |
| 加 n3→n1 形成环 | ❌ `illegal_cycle`，边数不变 |
| 目标节点不存在 | ❌ `dangling_edge_target` |
| 源节点不存在 | ❌ `dangling_edge_source` |
| 自环 | ❌ `self_loop` |
| `related` 关系成环 | ✅ 通过（仅 prerequisite/extension 构成硬依赖子图） |
| 孤立节点 | ⚠️ 警告，不阻断 |

### 4.2 `commit_assessment` 审计要求（§22.8）

- `raw_answer` **必填**，数据库层 `NOT NULL` 双重保障
- `assessor_type` 受 CHECK 约束（5 种取值）
- `overall_score` 按配置权重聚合，**`transfer` 与 `hint_dependency` 被排除**
- 权重在缺失维度上**自动归一化**（选择题没有 reasoning rubric 也能算出有意义的综合分）

### 4.3 幂等与错误边界

- `request_log` 表实现请求重放（§19.4）
- 工具失败**绝不静默变成状态更新**（§29.1）：统一返回 `{ok:false, error:{code,message,details}}`
- 幂等记账失败不会影响业务操作本身

## 5. 端到端验证

Python 递归场景完整跑通：

```
create_session                   OK  domain_grounding_stage=pending
save_learning_goal               OK
generate_diagnostic (gated)      REJECTED  [domain_grounding_required]
save_benchmark_report            OK
generate_diagnostic (unlocked)   OK  diagnostic_depth=adaptive
save_knowledge_nodes             OK
save_knowledge_edges             OK
save_knowledge_edges (cycle)     REJECTED  [invalid_knowledge_dag]
save_knowledge_edges (dangling)  REJECTED  [invalid_knowledge_dag]
validate_knowledge_dag           OK  valid=True, node_count=3, edge_count=2
start_unit                       OK  current_node_id=n1
advance_unit (blocked)           REJECTED  [state_guard_rejected]
submit_attempt                   OK  attempt_index=1
assess_response                  OK  overall_score=0.92
commit_assessment                OK  stage_before=estimated → stage_after=practiced
get_mastery_status               OK  mastery=0.6298 hint_dep=0.000 stage=practiced
evaluate_pedagogical_policy      OK  Scaffolding / Review Prerequisite
get_teaching_context             OK  strategy=Scaffolding
record_transfer_result           OK  evidence_stage=practiced
schedule_review                  OK  created=True
submit_review                    OK  rating=3, interval_days=1.0
get_due_reviews                  OK  count=0, blocks_new_learning=False
get_obsidian_structure           OK
get_web_component_spec           OK
generate_final_report            OK  artifact_id=art_...
export_session_data              OK
```

`events: 20 | artifacts: 3`

**注意第 11 行**：一次满分作答后 `stage` 只到 `practiced`（mastery 0.63 < 0.8），且 Policy 正确识别出前置 `n1` 未达标 → 返回 `Review Prerequisite`。这验证了 §2.4「答对不是学会的充分条件」。

## 6. 静态规范输出（§22.10）

`get_obsidian_structure` / `get_web_component_spec` **只返回静态 JSON 规范**，不读写本地文件、不读取前端源码。规范文件落在 `src/leap/specs/`，随包分发。

Web 规范把"禁 CDN"约束固化成机器可读契约：禁 Tailwind CDN / 禁 KaTeX / 禁 Pyodide，并定义 `window.LEAP.getInteractionResult()` 输出契约与设计 token。

## 7. 依赖

| 包 | 版本 | 说明 |
|---|---|---|
| `mcp` | 2.2.0 | **注意：2.x 已把 `FastMCP` 改名为 `MCPServer`**（`mcp.server.mcpserver`），且装饰器/签名有变化 |

## 8. 下一步

任务 #5：测试、文档、CI 与报告。
