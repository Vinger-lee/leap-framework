# LEAP 宿主桥接契约（Host Bridge）

> 本文件定义教学网页与 **LEAP Runtime** 之间的双向接口。
> 结构规范见 `leap-web-spec.md`，视觉规范见仓库根目录 （视觉规范 — （作者另行维护的视觉规范，不在本仓库）），
> 机器可读契约见 `interaction-output.schema.json`。

---

## 0. 为什么需要这一层

教学网页是**参考示例**，不是产品。它必须演示清楚"页面 ↔ Runtime"是怎么接上的，否则会传递一个错误印象：好像掌握度是页面自己算的、学习行为不出页面。

LEAP 的分工是硬边界（`LEAP_Framework_V2` §2.3、§10.2‑1）：

| 谁 | 负责 |
|---|---|
| **页面（本层）** | 呈现教学内容、采集学习者动作、把动作翻译成 MCP 调用 |
| **宿主 Agent** | 执行 MCP 调用、驱动对话、决定下一步动作 |
| **LEAP Runtime** | 判定 `mastery_probability` / `evidence_stage` / 状态迁移是否允许 |

所以页面**不允许**自行推算掌握度或证据阶段。它只做两件事：**接收注入**、**产出调用**。

---

## 1. 输入方向：`LEAP.hydrate(context)`

宿主 Agent 调用 `get_teaching_context` 拿到上下文后，直接喂给页面：

```js
const ctx = await mcp.call("get_teaching_context", { session_id, node_id });
window.LEAP.hydrate(ctx);
```

`hydrate` 接受 `get_teaching_context` 的原始返回结构，按需读取：

| 字段 | 作用 |
|---|---|
| `session.session_id` / `session.learner_id` | 回填契约中的 `learner`，替换占位符 |
| `current_node.node_id` / `.title` / `.unit_tag` | 回填契约中的 `node` |
| `knowledge_state.mastery_probability` | 顶栏掌握度条与数值（**只显示，不计算**） |
| `knowledge_state.evidence_stage` | 进度脊柱五段轨的当前档位 |
| `knowledge_state.hint_dependency` | 提示阶梯说明行 + 评分面板 |
| `knowledge_state.next_review_at` | 顶栏 NEXT REVIEW |
| `transfer_requirement` | 是否需要迁移验证 |
| `recommended_actions` / `recommended_strategy` | 供页面提示"下一步建议" |

调用后 `ui_state.mode` 由 `"demo"` 变为 `"hosted"`，页面顶部的免责说明同步改为"本页状态由 LEAP Runtime 注入"。

**未调用 `hydrate()` 时页面保持 `demo` 模式**，此时本地推算值一律带 `assessment.provisional = true`，界面明确标注为演示数据。

---

## 2. 输出方向：契约对象 + 调用队列

### 2.1 `LEAP.getInteractionResult()`

返回 `interaction-output.schema.json` 定义的完整对象，宿主 Agent 用它驱动下一轮教学决策。

### 2.2 `LEAP.drainOutbox()`

返回**待执行的 MCP 调用队列**并清空队列。这是"页面调用了接口"的落点。

```js
const calls = window.LEAP.drainOutbox();
for (const call of calls) {
  const result = await mcp.call(call.tool, resolvePlaceholders(call.args, results));
  results[call.call_id] = result;
}
```

配套方法：

| 方法 | 用途 |
|---|---|
| `LEAP.peekOutbox()` | 只读查看队列，不清空 |
| `LEAP.onOutboxChange(fn)` | 订阅队列变化（`fn(call, size)`） |
| `LEAP.isHosted()` | 是否已注入宿主上下文 |

---

## 3. 事件 → 调用映射

页面在 `pushEvent` 时同步入队。映射关系是固定的：

| 事件类型 | 产生的 MCP 调用 |
|---|---|
| `attempt_submitted` | `submit_attempt` |
| `drag_submitted` | `submit_attempt` |
| `code_run` | `submit_attempt` |
| `reflection_recorded` | `record_reflection` |
| `hint_used` / `answer_revealed` / `item_completed` | **不单独产生调用** —— 它们的信息通过下一次 `attempt` 的 `hint_level` 一并提交 |

`commitAssessment()` 额外产生一条 `commit_assessment`，其 `attempt_id` 用**引用占位符**指向前面那条 `submit_attempt`：

```json
{
  "call_id": "call_2",
  "tool": "commit_assessment",
  "args": {
    "attempt_id": "{{call_1.attempt_id}}",
    "raw_answer": "def factorial(n): ...",
    "correctness": 0.9,
    "assessor_type": "model"
  }
}
```

> `{{call_N.field}}` 是占位符语法：宿主 Agent 执行完 `call_1` 后，把返回值里的 `attempt_id` 填进来。
> 这如实反映了 MCP 的两步流程 —— **不能跳过 `submit_attempt` 直接 `commit_assessment`**。

---

## 4. 完整时序

```text
宿主 Agent                          页面                        LEAP Runtime
    │                                │                              │
    │  create_session ───────────────┼──────────────────────────────▶
    │  get_teaching_context ─────────┼──────────────────────────────▶
    │                                │                              │
    │  LEAP.hydrate(ctx) ───────────▶│  (mode → hosted)             │
    │                                │                              │
    │                                │  学习者作答                   │
    │                                │  pushEvent(...)              │
    │                                │  commitAssessment(...)       │
    │                                │                              │
    │  LEAP.drainOutbox() ──────────▶│                              │
    │  ◀── [submit_attempt, commit_assessment]                      │
    │                                │                              │
    │  submit_attempt ───────────────┼──────────────────────────────▶
    │  ◀── { attempt_id }            │                              │
    │  commit_assessment(attempt_id) ┼──────────────────────────────▶
    │  ◀── { learner_state }         │                              │
    │                                │                              │
    │  LEAP.hydrate(新 context) ────▶│  (掌握度/证据阶段刷新)        │
```

---

## 5. 页面不得做的事（硬性）

| ❌ 禁止 | ✅ 应改为 |
|---|---|
| 自行推算 `mastery_probability` 并当作真值展示 | 只显示 `hydrate()` 注入的值；demo 模式下标注"本地模拟" |
| 自行决定 `evidence_stage` 升级 | 以 Runtime 返回值回填 |
| 自行判定单元能否推进 | 产生 `advance_unit` 调用，由 State Guard 裁决 |
| `commit_assessment` 不带 `raw_answer` | `raw_answer` 必须非空（§22.8：原始作答不可丢弃） |
| 把 `mastery_probability` 放进 `commit_assessment` 入参 | 只提交多维评分，掌握度由 Runtime 算（§10.2‑1） |
| 只把结果打在页面上、不产生调用 | 每次交互都要入队对应的 MCP 调用 |

---

## 6. 验收

桥接是自动化验收的一部分，不需要人工核对：

```bash
python scripts/verify_example_runtime.py --all
```

覆盖的桥接检查项：

- `LEAP.hydrate()` 可调用，注入后 `ui_state.mode === "hosted"`
- 注入的 `learner` / `node` / `mastery_probability` / `evidence_stage` 生效并反映到界面
- 一次作答产生 `submit_attempt`，其 `session_id` / `node_id` / `answer` / `hint_level` 取自注入上下文
- `drainOutbox()` 取走后队列清空
- `commit_assessment` 携带非空 `raw_answer` 与 `attempt_id` 引用
- `commit_assessment` 入参中**不含** `mastery_probability`
- 桥接后返回值仍通过 `interaction-output.schema.json` 校验

若页面缺少桥接，用下面这条命令补齐（幂等，已打过会跳过）：

```bash
python scripts/apply_leap_bridge.py --all
```
