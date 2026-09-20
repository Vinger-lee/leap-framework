# Step 07 · 宿主桥接：让示例真正"调用接口"

- **日期**：2026-09-19
- **对应任务**：修正示例 1 / 2 的接口缺失
- **状态**：✅ 完成（示例 1、2 已改；示例 3 已按要求还原未改）

---

## 0. ⚠️ 安全事件：泄露的 GitHub 令牌

本轮对话中有一枚**全权限 GitHub PAT 被明文粘贴**。处置记录：

| 项 | 结果 |
|---|---|
| 是否写入仓库文件 | ❌ 否 |
| 是否进入 `.git/config` | ❌ 否 |
| 是否进入 git 凭据缓存 | ❌ 否 |
| 全仓库（含 `.git`）令牌形态扫描 | **0 命中** |
| 本报告及所有交付物 | 不含令牌值 |

**该令牌必须视为已泄露并立即吊销。** 明文出现在对话记录中即等同于泄露，与后续如何使用无关。
请在 GitHub → Settings → Developer settings → Personal access tokens 中 Revoke，并重新签发。

**本轮的改造工作未使用该令牌**，也无需使用 —— 全部是本地文件改动。

---

## 1. 问题：示例是一个"封闭的模拟"

你的判断是准确的：**这个示例没有调用任何接口，也没有真正的输出**。

改造前的问题：

| # | 问题 | 后果 |
|---|---|---|
| 1 | `var mastery = 0.62; /* 本地模拟值 */` —— 掌握度是页面写死的 | 违反 LEAP §10.2‑1：掌握度必须由服务端 BKT 计算 |
| 2 | `commitAssessment()` 在页面内自行推导 `evidence_stage` | 违反 §2.3：状态迁移必须由 State Guard 裁决 |
| 3 | **没有输入接口** —— 宿主 Agent 无法把 `get_teaching_context` 的结果注入页面 | 页面只能自娱自乐，接不上真实 Runtime |
| 4 | **没有出站通道** —— 学习者作答后不产生任何待执行的 MCP 调用 | 学习行为不出页面，闭环断裂 |
| 5 | 顶部免责声明说"本地模拟"，但页面行为没有任何机制去改变这一点 | 说明与实现不一致 |

一句话：**它长得像 LEAP，但不在 LEAP 里。**

---

## 2. 改造：补上双向桥接

新增一层 `LEAP_HOST_BRIDGE`，把页面变成 Runtime 的一个真实前端。

### 2.1 输入方向：`LEAP.hydrate(context)`

宿主 Agent 把 `get_teaching_context` 的返回值**原样**喂进来即可：

```js
const ctx = await mcp.call("get_teaching_context", { session_id, node_id });
window.LEAP.hydrate(ctx);
```

接受并生效的字段：`session.session_id` / `session.learner_id` / `current_node.*` /
`knowledge_state.mastery_probability` / `.evidence_stage` / `.hint_dependency` /
`.next_review_at` / `transfer_requirement` / `recommended_actions`。

注入后 `ui_state.mode` 由 `"demo"` 变为 `"hosted"`，顶部免责说明同步改为
"本页状态由 LEAP Runtime 注入；掌握度与证据阶段由服务端 BKT 与 State Guard 计算，本页不自行推算"。

### 2.2 输出方向：契约对象 + MCP 调用队列

| 接口 | 作用 |
|---|---|
| `LEAP.getInteractionResult()` | 完整契约对象（已有，现在额外带 `outbox` 与 `ui_state.mode`） |
| `LEAP.drainOutbox()` | **取出待执行的 MCP 调用并清空队列** ← 这是"调用接口"的落点 |
| `LEAP.peekOutbox()` | 只读查看队列 |
| `LEAP.onOutboxChange(fn)` | 订阅队列变化 |
| `LEAP.isHosted()` | 是否已注入宿主上下文 |

### 2.3 事件 → 调用映射（固定）

| 事件 | 产生的 MCP 调用 |
|---|---|
| `attempt_submitted` / `drag_submitted` / `code_run` | `submit_attempt` |
| `reflection_recorded` | `record_reflection` |
| `hint_used` / `answer_revealed` / `item_completed` | 不单独产生调用（信息通过下一次 attempt 的 `hint_level` 提交） |
| `commitAssessment()` | 额外产生 `commit_assessment` |

`commit_assessment` 的 `attempt_id` 用**引用占位符**指向前面那条调用：

```json
{ "call_id": "call_2", "tool": "commit_assessment",
  "args": { "attempt_id": "{{call_1.attempt_id}}", "raw_answer": "def factorial(n): ...", ... } }
```

这如实反映了 MCP 的两步流程 —— **不能跳过 `submit_attempt` 直接 `commit_assessment`**。

### 2.4 诚实性设计

- **demo 模式**（未注入）：本地推算值一律带 `assessment.provisional = true`，界面标注"演示模式"；
- **hosted 模式**：`commitAssessment()` **不再本地推进 mastery、不再自行推导 evidence_stage**，一律以注入值回填；
- `commit_assessment` 入参中**不含 `mastery_probability`**（有自动化检查项专门守这条）。

---

## 3. 交付物

| 文件 | 说明 |
|---|---|
| `examples/01-python-recursion/leap-01-python-recursion.html` | 已打桥接（LF 行尾保留） |
| `examples/02-math-linear-equation/leap-02-math-linear-equation.html` | 已打桥接 |
| `examples/_shared/leap-bridge.md` | **宿主桥接契约**（新），示例 3–5 照此实现 |
| `examples/_shared/interaction-output.schema.json` | 新增 `outbox`、`ui_state.mode/hosted/pending_mcp_calls/hint_dependency`、`assessment.provisional` |
| `examples/_shared/leap-web-spec.md` | 新增 §5.1 宿主桥接硬性要求 |
| `examples/README.md` | 验收清单加入桥接项 |
| `scripts/apply_leap_bridge.py` | 桥接注入工具（幂等、可 `--revert`、保留行尾） |
| `scripts/verify_example.py` | 新增 **H 组 9 项**桥接静态检查 |
| `scripts/verify_example_runtime.py` | 新增 **14 项**桥接运行时检查 |

---

## 4. 验证结果

### 4.1 静态

```
示例1：64 passed, 1 warnings, 0 errors
示例2：65 passed, 0 warnings, 0 errors
```

（示例 1 的 1 条 warning 是既有项：调用栈用纯 DOM 绘制而非 SVG/Canvas，见 Step 06 §4。）

### 4.2 运行时（headless Chromium + JSON Schema）

两个示例均 **32/32 通过**，其中桥接部分：

```
[PASS] LEAP.hydrate() 可调用（宿主注入入口）
[PASS] hydrate 后进入 hosted 模式  (mode='hosted')
[PASS] 注入的 learner / session 生效  ({'learner_id': 'learner-verify', 'session_id': 'ses_verify'})
[PASS] 注入的 evidence_stage 生效  (实际 'demonstrated')
[PASS] 注入的 node 生效  ({'node_id': 'verify.node', ...})
[PASS] 顶栏掌握度显示注入值 0.73  (实际显示 '0.73')
[PASS] 作答产生 submit_attempt 调用
[PASS] submit_attempt 参数取自注入上下文  ({'session_id': 'ses_verify', 'answer': 'verify answer',
        'node_id': 'verify.node', 'hint_level': 1, 'response_time': 9.5})
[PASS] drainOutbox 取走后队列清空
[PASS] 评估产生 commit_assessment 调用
[PASS] commit_assessment 携带非空 raw_answer  (raw_answer='verify answer')
[PASS] commit_assessment 携带 attempt_id 引用  (attempt_id='{{call_2.attempt_id}}')
[PASS] commit_assessment 不自行提交 mastery
[PASS] 桥接后仍符合 JSON Schema
```

视觉复核（截图）：demo 模式下桥接条显示"BRIDGE · 演示模式"；`hydrate()` 后进度脊柱证据轨推进到
`demonstrated · 独立展示`、掌握度条显示注入的 0.81、免责说明切换为"由 LEAP Runtime 注入"。

---

## 5. 过程中我自己犯的三个错（都已修）

| # | 错误 | 后果 | 修法 |
|---|---|---|---|
| 1 | 桥接代码块**重复了一个闭合花括号** `};` | 页面 JS 语法错误，`window.LEAP` 直接不存在 | 锚点已含 `};`，块内不应再写；补测试守这条 |
| 2 | `write_text()` 在 Windows 上**把 LF 转成了 CRLF** | 一个 200 行的补丁变成整文件 1506 行全变，diff 不可读 | 检测原始行尾并用 `newline=` 还原 |
| 3 | 补丁锚点写死 `\n`，**CRLF 文件匹配不上** | 在 CRLF 页面上直接报 anchor not found | 匹配前统一归一化为 `\n`，写回时还原 |

**关键教训**：补丁工具必须先验证"改完后还能不能跑"和"改动是否最小"。我在第 1 个错误上直接
把页面打成了白屏 —— 静态检查全部通过，只有运行时检查才暴露出来。这再次说明
**静态通过 ≠ 可用**。

---

## 6. 关于示例 3（未改动）

按要求**没有改示例 3**。过程中我的 `--all` 误把补丁打到了示例 3 上，已用 `--revert` 完整还原，
并逐项确认无桥接残留。同时静态检查在示例 3 上发现一个真实问题（**未修改，仅报告**）：

```
[FAIL] E7  subject 取值合法  <- 实际: 'cs'
```

`subject` 必须是 `computer-science`（schema 枚举值），写 `cs` 会导致契约校验失败。
示例 3 若还在生成中，建议在定稿前修正。

示例 3 完成后，一条命令即可补上桥接：

```bash
python scripts/apply_leap_bridge.py examples/03-cs-osi-model/leap-03-cs-osi-model.html
```

---

## 7. 当前状态

| 项 | 值 |
|---|---|
| 测试 | **168 passed**（较上轮 +10） |
| 隐私扫描 | `files=66 P0=0 P1=0 P2=0` |
| 令牌残留 | 全仓库 0 命中 |
| 示例 1 / 2 | 静态 64 / 65 通过；运行时 32 / 32 通过 |
| 示例 3 | 未改动（发现 `subject: 'cs'` 问题待修） |
| 示例 4 / 5 | 尚未产出 |
| 首次 git 提交 | **仍未执行**；提交身份仍未设置 |

## 8. 下一步

1. **吊销并重签 GitHub 令牌**（最优先）
2. 决定公开提交身份 → 首次提交
3. 示例 3 定稿后补桥接并修正 `subject`
4. 示例 4 / 5 产出后按同一套脚本验收
