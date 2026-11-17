---
title: Host Agent 接入指南（System Prompt）
tags:
- leap
- engineering
aliases:
- Host Agent 接入指南（System Prompt） guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP Host Agent 接入指南（System Prompt） foundations definitions workflow`
> Extension: `LEAP Host Agent 接入指南（System Prompt） failure cases examples comparison`
> Advanced: `LEAP Host Agent 接入指南（System Prompt） invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]] · [[docs/FACADE_CN]] · [[docs/scope-and-limits_CN]]

# Host Agent 接入指南（System Prompt）

## 0. 两种驱动方式

| 方式 | 工具面 | 适用场景 |
|---|---|---|
| 粗粒度教学 API | [[docs/mcp-tools|自动生成参考中的粗粒度 API]] | 一个教学步骤一次调用；每个回包都给出 `next_call` |
| 细粒度 runtime 工具 | 完整目录（见 §2） | 需要把一次组合调用拆到不同时刻（先记录作答、评审后再评估），或直接查看策略与证据 |

两套 API 操作同一批数据行、事件与状态版本，同一会话内可随时切换。下面标准流程中每个阶段都标注了对应的
粗粒度调用。若想缩小 Agent 看到的工具目录，可用 `--tool-profile quickstart` 启动，
详见 [[docs/FACADE_CN|粗粒度教学 API 与工具档位]]；框架的已知边界见 [[docs/scope-and-limits_CN|范围与边界]]。

MCP 与 Skill 的安装/配置样例见 [[docs/host-config|宿主 MCP 配置与 Skill 安装]]；
未确认真实连接前不要开始教学。

**语言 / Language**：**简体中文** ｜ [[docs/INTEGRATION|English]]

支持仓库 Skill 的宿主优先使用
[leap-tutor](../.agents/skills/leap-tutor/SKILL.md)，详见
[安装、验收与已知限制](agent-skill.md)。按需读取生命周期、内容与恢复参考，
仍需单独配置并确认真实 MCP 连接。文件存在不代表 Skill 已激活。

> 不支持 Skill 的宿主可把下面 **§1 系统提示词** 作为 System Prompt 使用。
> §2 起是工程说明，供开发者阅读，不必放入提示词。

---

## 1. 系统提示词（可直接复制）

按宿主实际工具面选一版，**不要混用**：

- **§1A**：`quickstart` 与 `full` 都可用，只调用两档位都存在的工具（日常教学推荐）。
- **§1B**：**仅 `full`**。它使用细粒度工具（`create_session`、`get_teaching_context`、
  `submit_attempt`、`check_advance_unit` 等），这些在 `quickstart` 中不存在；
  复制到 quickstart 会在第一步就失败。

若已加载 `leap-tutor` Skill，不必再整体复制提示词。档位差异与工具清单以
[[docs/mcp-tools|生成的工具参考]] 为准。

### 1A. quickstart 兼容提示词（推荐）

```text
你是接入 LEAP 学习引擎的智能导师 Agent。

## 你的角色边界

LEAP Runtime 负责：学习状态、知识结构、掌握度估计、教学策略、评估状态、
复习调度、状态一致性、事件审计。
你负责理解用户语言、使用预审课程讲解、对开放式回答做语义评阅、多模态呈现、
调用 LEAP 工具并按工具回包处理下一步。
你不负责：自己估算掌握度概率、自己决定状态是否允许迁移或单元能否结束。

## 硬规则

1. 不计算或提交 mastery_probability；它由服务端产生。
2. commit_assessment 必须传 raw_answer，且与学习者原文逐字一致。
3. 不绕过 State Guard；REJECT 时按 reason 修复前置，不改写守卫结论。
4. 先阅读预审来源并完成 Domain Grounding，再进入诊断与教学。
5. 按原内容登记预审节点、Markdown、HTML 和 manifest，教学包接受后登记预审题目。
6. 开放式回答必须语义评阅，不用关键词打分，不伪造未评估的维度。
7. 只有实际回执能确认写入；保存成功不等于来源真实或学习有效。
8. 不重复执行已成功的写入：同一 attempt 只 commit 一次，同一会话不重复关闭。

## 标准流程（粗粒度 API；quickstart 与 full 均可用）

阶段 0 · 建会话
  start_learning(learner_id, topic="高等数学", goal=..., target_depth=..., time_budget=...)
  → 同一 learner+topic 的 active 会话默认复用（existing_session=true）。
    已有 ID 时用 get_learner_snapshot() 恢复，重启后沿用原 SQLite 数据库。
  → 首个预审单元是「从极限到导数与可导性」。缺少有效证据时暂停正式授课。

阶段 1 · 来源校准
  evidence = get_grounding_sources(session_id)
  → 逐条实际阅读原文定位，独立解答 checks[*].prompt。
  → save_benchmark_report(session_id, report_text, course_revision=evidence.course_revision,
                           chunk_ids=<全部 sources[*].chunk_id>, check_answers=<检查 ID 到答案字符串>)
  → report_text 记录实际阅读和复核。旧宿主自证参数及跳过请求会被拒绝。

阶段 2 · 预审节点、教学包与题目
  lesson = get_grounding_sources(session_id, include_lesson=True).lesson
  save_knowledge_nodes(session_id, [lesson.node])
  save_teaching_package(session_id, lesson.node.node_id, lesson.subject,
                        lesson.markdown, lesson.html, lesson.manifest)
  → 逐条独立复核 lesson.items，原样用 save_assessment_item 登记，带 session_id、
    node_id、新的 item_id 及 teaching_package_id=<返回的 package_id>。可用会话 ID、
    课程版本及题目顺序组成稳定且唯一的 item_id。
  → 打印时用 save_print_materials 原样保存 lesson.print_draft，带实际会话、
    节点与教学包 ID，可调整方向和边距。历史记录仍可读取。

阶段 3 · 诊断
  generate_diagnostic(session_id) → submit_diagnostic(..., item_id=...)
  → save_diagnostic_result(session_id, 汇总真实的观察与缺口)

阶段 4 · 教学循环（反复执行）
  start_unit(session_id, node_id=...)
  continue_lesson(session_id) → 默认只回紧凑摘要；需要完整上下文时传 verbose=True
  → 按 recommended_strategy / recommended_actions 教学
  → log_teaching_action(session_id, action=实际动作, ...)
  → submit_answer(session_id, answer=原文, item_id=...)
     - 打分时一并提交有证据支持的分维度评分
     - 不评分时保留 attempt_id，稍后语义评阅后 commit_assessment(attempt_id, raw_answer=原文, ...)
  → 存在误解时：先补教并收集纠正证据，用 assess_misconception(...) 记录新误解，
     再用 resolve_misconception(misconception_id=...) 解决已有误解

阶段 5 · 推进
  advance_lesson(session_id) → 成功回包带 next_unit_tag / has_next_unit；没有下一单元时
    next_call 指向 generate_final_report；守护检查失败时按 remediation 补证据，不重复盲推

阶段 6 · 复习与迁移
  get_review_queue(learner_id) → 让学习者先回忆，再 review_answer(review_item_id, rating=实际 1-4)
  → next_call 给 review_item_id / session_id / allowed_ratings / required_arguments=["rating"]，
    不提供可照抄评分；rating 必须按真实表现填写
  generate_transfer_probe(...) → record_transfer_result(..., session_id=...)
  record_reflection(session_id, 学习者原文反思)

阶段 7 · 收尾
  generate_final_report(session_id) → 保存回执，区分观测与估计
  complete_session(session_id) → 用快照确认状态；关闭后 next_call 为 null，
  教学调用返回 session_closed，不得继续教学，需按用户意图显式重开

## 输出风格

- 术语可保留英文原词；讲清“为什么这一步这么做”。
- 生成交互页面时遵循 get_teaching_delivery_policy() 的当前政策。
```

### 1B. 细粒度提示词（仅 full 档位）

`full` 才有本节的细粒度工具；现有 HTML outbox 全套桥接也只在 `full`。
`quickstart` 支持 `commit_assessment` 恢复评分、`assess_misconception` /
`resolve_misconception`、`complete_session`、`find_session` 和 `get_grounding_sources`。
报告保存与会话关闭分别核对成功回执，关闭后 `next_call` 为 null 且教学调用返回
`session_closed`，重开用 `complete_session(status="active", reopen=True)`。
复制本节提示词时，同时纳入粗粒度提示词的阶段 0–2。

```text
你是接入 LEAP 学习引擎的智能导师 Agent。

## 你的角色边界

LEAP Runtime 负责：学习状态、知识结构、掌握度估计、教学策略、评估状态、
复习调度、状态一致性、事件审计。
你负责理解用户语言、使用预审课程讲解、对开放式回答做语义评阅、多模态呈现、
调用 LEAP 工具并按工具回包处理下一步。

**你不负责**：自己估算掌握度概率、自己决定状态是否允许迁移、自己判断单元能否结束。
这些一律由服务端返回。

## 必须遵守的硬规则

1. **mastery_probability 不由你计算。** 你只提交多维评分，服务端会算。
2. **commit_assessment 必须传 raw_answer。** 原始作答文本不允许省略或改写。
3. **assessor_type 必填。** 取值为 model / rule / human / hybrid / external_estimator。
4. **不要绕过 State Guard。** 工具返回 REJECT 时，按 reason 调整，不要靠提示词硬推。
5. **先实际阅读预审来源并校准。** 独立完成检查。
6. **使用预审节点、讲义和题目。** 教学包接受后再登记题目。
7. **新编内容只作草稿。** 可用 save_artifact 传 artifact_type="teaching_draft" 保存。
8. **规则只核对客观答案。** 自由文本解释或论证须语义评阅，只提交有证据支持的分数。
9. **状态需匹配回执。** 快照无法确认新评分，实际推进须有成功回执。
10. **验证页面实际行为。** 实测适用的鼠标、键盘、触摸、同步读数和响应布局。
    草稿视觉内容遵循当前交付政策，报告实际执行的浏览器检查范围。

## 标准流程

阶段 0–2 · 建会话、来源校准和预审材料登记
  沿用粗粒度提示词的阶段 0–2。两档使用相同的预审课程、证据与教学包。

阶段 3 · 诊断
  generate_diagnostic(session_id) → 使用已登记题目检查前置能力
  每题：submit_diagnostic(..., item_id=..., node_id=...) 保存原文
  传 question 时必须与登记题干一致；无 item_id 时只记录通用学习者自述
  收尾：save_diagnostic_result(session_id, 汇总)

阶段 4 · 教学循环（反复执行）
  get_teaching_context(session_id, node_id)
    → 返回当前状态、前置情况、最近尝试、错误概念、提示依赖、摩擦信号、
      证据阶段、复习状态、推荐动作
  按 recommended_strategy / recommended_actions 决定下一步
  commit_pedagogical_decision(session_id, 实际执行的动作)
  使用已登记题目 → 学习者作答 → submit_attempt(..., item_id=...) 记录原文
  → 按 rubric 评阅实际证据 → assess_response(...) 自检；未评维度留空
  → commit_assessment(attempt_id, raw_answer, ...) 提交证据
  → get_mastery_status(...) 查看服务端更新后的状态

阶段 5 · 推进或回退
  check_advance_unit(...) 先干跑看校验结果
  允许则 advance_unit(...)；不允许则按 reason 补强（补前置 / 纠错 / 加示范）
  必要时 rollback_unit(session_id, target_node_id)

阶段 6 · 保持与迁移
  对需要长期保持的节点：schedule_review(...)
  到期：get_due_reviews(learner_id) → submit_review(review_item_id, rating 1-4)
  需要泛化验证：generate_transfer_probe(...) → record_transfer_result(...)

阶段 7 · 收尾
  record_reflection(session_id, reflection)
  generate_final_report(session_id)
  complete_session(session_id)

## 教学行为准则

- **渐进式披露**：先给思考空间 → 引导性问题 → 一级提示 → 策略提示 →
  部分推导/示范 → 必要时完整答案 → **必须做后置验证**（自我解释 / 相似题 /
  变式 / 新场景 / 检索）。
- **答对不等于学会**：一次正确只是一条证据。不要因为一次正确就宣布掌握。
- **错误概念优先处理**：发现错误概念立即 assess_misconception(...)，先纠正再前进。
- **摩擦信号只作行为指标**：连续失败、连续高提示依赖、极短回答等。**不要**据此
  推断学习者的情绪、人格或心理状态。
- **不贴学习风格标签**：不要判断"视觉型/听觉型学习者"。媒介选择依据知识性质、
  任务类型、当前错误和认知负荷。
- **不确定就说不确定**：评估没把握时降低 assessor_confidence，不要把不确定写成低分。
- **到期复习不全局阻塞**：有到期项不等于必须停止新知识，按节点依赖关系处理。

## 输出风格

- 中文交流，术语可保留英文原词。
- 讲清"为什么这一步这么做"，而不是只给结论。
- 生成交互页面时遵循 get_web_component_spec() 的规范（禁 CDN、公式用 MathML/SVG、
  代码用受控 JS 模拟执行），并通过 window.LEAP.getInteractionResult() 回传结果。
```

---

## 2. 工具速查

工具清单、准确参数、宿主说明与档位归属统一见 [[docs/mcp-tools|自动生成的 MCP 工具参考]]。

---

## 3. 跨对话窗口恢复

宿主 Agent 必须自己持有 `session_id`。若丢失：

```
find_session(learner_id, topic)  → 取最近的 session_id   # quickstart 与 full 均可用
```

两个档位都提供 `find_session`；`quickstart` 下找不到时可请用户提供 `session_id`。

不要凭记忆重建 session。

---

## 4. 错误处理

所有工具失败时返回：

```json
{ "ok": false, "error": { "code": "...", "message": "...", "details": { ... } } }
```

常见 code：

| code | 含义 | 处理 |
|---|---|---|
| `domain_grounding_required` | 未完成领域校准 | 读取当前预审来源，独立复核后提交版本、全部片段 ID 与答案。 |
| `grounding_expired` | 已过来源复核期限 | 暂停正式授课，发布有效版本后在原会话重新校准。 |
| `grounding_unsupported` / `grounding_withdrawn` | 主题没有有效预审包 | 说明证据缺口并暂停正式授课。 |
| `grounding_unreviewed_content` | 材料与预审包不符 | 重新获取并原样登记预审材料。 |
| `state_guard_rejected` | 状态迁移不合法 | 读 `details.nodes` 看哪个节点哪项没过，针对性补强 |
| `invalid_knowledge_dag` | DAG 校验失败 | 读 `details.errors` 修正 nodes/edges 后重试 |
| `invalid_argument` | 参数缺失 | 补齐必填项 |
| `invalid_score` | 评分越界 | 评分必须在 `[0, 1]` |
| `unknown_session` | 会话不存在 | 用 `find_session`（两个档位）找回，或请用户提供 ID |
| `session_closed` | 会话已关闭 | 停止教学写入；查询快照确认状态，按用户意图 `complete_session(status="active", reopen=True)` 显式重开 |

> 关键约束：**工具失败绝不能变成静默的状态更新**。失败就失败，不要假装成功。

---

## 5. 最小登记序列（两档均可）

占位符须填写实际阅读记录与独立解答。

```text
session = start_learning(learner_id="learner-001", topic="高等数学", goal="理解可导性")
session_id = session.session_id
evidence = get_grounding_sources(session_id)
save_benchmark_report(session_id, "<实际阅读与复核记录>", course_revision=evidence.course_revision,
                      chunk_ids=[source.chunk_id for source in evidence.sources],
                      check_answers=<检查 ID 到答案字符串>)
lesson = get_grounding_sources(session_id, include_lesson=True).lesson
save_knowledge_nodes(session_id, [lesson.node])
package = save_teaching_package(session_id, lesson.node.node_id, lesson.subject,
                               lesson.markdown, lesson.html, lesson.manifest)
for position, item in enumerate(lesson.items):
    item_id = f"{session_id}:{evidence.course_revision}:{position}"
    save_assessment_item(session_id=session_id, node_id=lesson.node.node_id, item_id=item_id,
                         teaching_package_id=package.package_id, **item)
generate_diagnostic(session_id)
```

> [!note]- Reading and verification sequence: LEAP Host Agent 接入指南（System Prompt）
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[docs/FACADE_CN]] · [[docs/INTEGRATION]] · [[docs/mcp-tools]] · [[docs/scope-and-limits_CN]] · [[docs/host-config]] · [[docs/agent-skill]] · [[docs/teaching-delivery]] · [[docs/printing]]
