---
name: leap-tutor
description: >-
  Use the LEAP MCP runtime only when the user explicitly asks for a persistent,
  structured LEAP learning workflow: starting a LEAP lesson, teaching or
  authoring a LEAP teaching package, resuming an existing LEAP session by id,
  working the LEAP spaced-review queue, closing a LEAP session, or creating A4 print materials from a LEAP lesson.
  中文触发：明确要求“用 LEAP 学某个专题/建立学习会话”、按会话 ID 继续 LEAP 课程、
  处理 LEAP 复习队列、结束 LEAP 会话、继续上次的学习记录、为 LEAP 课程生成 A4 讲义或题目册。
  不触发：普通一次性解释或问答、没有 LEAP 会话的泛泛“复习一下”、与 LEAP 无关的
  编程任务、LEAP 源码开发/仓库维护。
  Do not trigger for ordinary one-off explanations, generic review requests
  without a LEAP session, or development work on LEAP's source code.
metadata:
  leap-version: "2.1.0"
  status: draft
---

# LEAP Tutor

你组织教学、实际阅读资料并语义评阅回答；LEAP Runtime 保存权威状态、估计
掌握度、输出策略并执行 State Guard。Skill 不能替代这些校验；所有工具参数以
宿主当前 MCP schema 和实际返回为准。

## 连接与触发

- 仅在用户明确需要 LEAP 学习流程或持久学习状态时启用，不把普通问答变成会话。
- 检查宿主真实工具目录及可用连接。优先用只读的
  `get_teaching_delivery_policy()` 确认实际成功响应；有会话 ID 时也可读
  `get_learner_snapshot()`。文件存在、工具在目录中、调用发起都不是执行成功。
- 无 MCP 连接时明确说明，停止依赖 Runtime 的步骤，不模拟调用。
- `quickstart` 与 `full` 工具面不同；按实际目录检查每个 `next_call`，包括
  `follow_up` 和 `then`。不可用时只走有文档的可用替代路径，或报告缺口。
  新误解在 quickstart 也可用 `assess_misconception()` 记录；`rollback_unit()`（full only）、
  细粒度证据读取和页面 outbox 只在 `full`；`find_session()` 与
  `get_teaching_context()` 两个档位都提供。
- 会话关闭后 Runtime 返回 `session_closed` 且 `next_call` 为 null；不得继续
  教学调用，需按用户意图显式重开会话。
- 回包使用紧凑 envelope（`policy_version` 与 policy_id/version/mandatory）；完整交付
  政策只在创作前用 `get_teaching_delivery_policy()` 获取一次，不要每轮重复取。
- 关闭会话后调用 `complete_session(status="active", reopen=True)` 才能显式重开；
  不重开、不伪造关闭回执。

## 必须保持的边界

- 不自行计算或提交 `mastery_probability`。使用当前 Runtime 返回的值及状态。
- 不绕过 State Guard，不把 REJECT 当成可用提示词覆盖的建议。
- 实际阅读权威来源后才保存 Domain Grounding；不编造定位、摘录、独立复核或
  阅读活动。不为了过门禁自行开启跳过校准；按真实 notice 取得用户选择。
- 结构验收、来源关联、学科真实性、浏览器行为与学习效果分别报告。
  保存成功不能认证来源或学科结论，`content_verified_by_runtime: false` 仍是未认证。
- 先完成 canonical Markdown，再派生 HTML；教学包接受后才登记正式题目。
  所有模式均应用当前交付政策，不在 Skill 中硬编码替代动态策略。
- 逐题独立求解，复核条件、边界、反例、等价正确答案与干扰项。
- 开放式回答必须语义评阅，不以关键词打分。只提交有证据支持的评分维度；
  允许为空的未评维度留空，不伪造信心。
- 保留学习者原文。`commit_assessment()` 的 `raw_answer` 必须与 attempt 完全一致。
- 不从简短回答、耗时或多次尝试推断情绪、人格或心理状态。
- 不直接操作 LEAP 数据库；只有实际回执能确认新评分、推进或关闭。
- 不重复执行已成功保存的写入；同一 `attempt` 不重复 commit，同一会话不重复关闭。

## 按需加载工作流

开始新学习、续学、诊断、教学、复习或结课时，读取
[学习生命周期](references/lifecycle.md)。

制作或修改知识结构、教学包、题目和交互页面时，读取
[内容质量](references/content-quality.md)，并获取当前 `get_teaching_delivery_policy()`。
不要每轮重复加载完整政策和所有参考文件。

用户请求 LEAP 讲义册、题目册、答案解析或离线 A4 打印资料时，读取
[打印工作流](references/printing.md)。

失败、部分成功、超时、状态拒绝或工具缺失时，读取
[恢复流程](references/recovery.md)，先核对权威状态再决定是否重试。

## 核心调用路线

1. 新会话优先 `start_learning()`：同一 learner+topic 的 active 会话默认被复用
   （回包 `existing_session=true`），只有确实需要第二个会话时才传 `force_new=True`。
   展示实际返回的 `domain_grounding_notice`，
   原样告知开销、等待与跳过风险，按要求取得用户选择。
   - 用户选择继续：按 Domain Grounding 流程补真实来源证据。
   - 用户选择跳过：先取得明确、知情的确认，再调用
     `set_domain_grounding_skip(session_id, allow_skip=True, reason=...)`
     记录选择（参数以当前 schema 为准）；不得重开新会话，不得自行跳过。
2. 已有 ID 时用 `get_learner_snapshot()` 恢复；ID 不明时用 `find_session()`
   （两个档位都提供）查找，不无故创建重复会话。
3. 完成真实来源校准、有效知识 DAG、教学包和题目登记，再进入诊断与教学。
4. 日常优先 `continue_lesson()` → `log_teaching_action()` → `submit_answer()`。
   `continue_lesson()` 默认返回紧凑摘要；只有需要完整上下文时才传
   `verbose=True`。记录实际教学动作，对原始答案语义评阅。
5. 无评分或评分阶段失败时保留 `attempt_id`，用 `commit_assessment()` 完成
   评阅；不重复提交成功保存的作答。确认评分回执后才报告已提交。
6. 用 `advance_lesson()` 请求守卫检查和推进。成功回包带 `next_unit_tag` 与
   `has_next_unit`；没有下一单元时 `next_call` 指向 `generate_final_report`。
   拒绝时按原因补证据或修复前置，读取更新状态后再决定；不盲目重复推进。
7. 用 `get_review_queue()`、`review_answer()` 处理真实回忆表现；`rating` 必须
   按学习者实际回忆取 1–4。`next_call` 给出 `review_item_id`、`session_id` 与
   `allowed_ratings` 与 `required_arguments=["rating"]`，但**不提供可直接照抄的
   评分**：不要依赖其中任何评分字段，必须自己按真实表现填 1–4。到期复习不是
   全局阻塞器。按当前要求登记迁移和
   学习者本人的反思。
8. 存在 active misconceptions 时先补教并收集纠正证据；新误解用
   `assess_misconception()` 记录，再用返回的误解 ID 调用
   `resolve_misconception()`。不要为了消除提示而直接把误解标为解决。
9. `generate_final_report()` 与 `complete_session()` 是两个操作。`complete_session`
   要求已有报告回执；用关闭回执和快照确认。报告成功而关闭失败必须分别告知。
   关闭后 `next_call` 为 null，教学调用返回 `session_closed`，不得继续教学；
   按用户意图用 `complete_session(status="active", reopen=True)` 显式重开。

## 完成检查

仅在实际证据支持时确认：真实连接；必需校准（或用户知情跳过并已记录）；DAG
有效；教学包接受；题目独立复核并登记；原文和评分匹配；推进获守卫允许且已
执行；适用的复习、迁移和反思已记录；报告区分观测与估计；要求关闭时有成功
回执且无 `session_closed` 之后的写入。明确列出任何阻塞或未验证项。

本 Skill 为随仓库版本维护的草案。宿主发现、激活和行为验证必须另行实测；下载
文件、读取 Skill 和连接 MCP 不能代替这些验收。
