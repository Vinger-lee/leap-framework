# 学习生命周期

用于实际 LEAP 教学与续学。工具参数以宿主 MCP schema 和实际返回为准；回包为紧凑
envelope，完整交付政策只在创作前用 `get_teaching_delivery_policy()` 获取一次。

## 建会话和续学

新会话调用 `start_learning()`，提供 learner_id、topic 及已知目标、深度、领域、
预算、先验知识和约束；仅澄清会影响教学的缺失信息。同一 learner+topic 的 active
会话默认复用（回包 `existing_session=true`），确实要新会话时才传 `force_new=True`。
首包用 `topic="高等数学"`，范围为「从极限到导数与可导性」。缺少有效证据时
向学习者说明缺口并暂停正式授课。

有 session_id 时先 `get_learner_snapshot()`，检查 session_status、current_node_id、
setup_gaps、证据阶段与到期复习。已关闭会话不自动重开；先确认用户意图，再用
`complete_session(status="active", reopen=True)` 显式重开。会话 ID 不明时用
`find_session()` 查找（两个档位都提供），不为续学自动新建会话。
重启后继续使用同一 SQLite 数据库，通过原会话恢复。历史记录可读，恢复正式授课需当前证据有效。

## 领域、知识结构和教学包

1. 调用 `get_grounding_sources(session_id)`。实际阅读每个片段的原文定位，独立
   解答每条 `checks[*].prompt`。记录来源中的条件、推导及复核结果。
2. 调用 `save_benchmark_report()`，传入 `session_id`、实际阅读和复核的
   `report_text`、返回的 `course_revision`、所有 `sources[*].chunk_id` 组成的
   `chunk_ids`，以及以 `checks[*].id` 为键、答案字符串为值的 `check_answers`。
3. 校准成功后调用 `get_grounding_sources(session_id, include_lesson=True)`。
   用 `save_knowledge_nodes()` 保存包含返回的 `.lesson.node` 的列表。
4. 用 `save_teaching_package()` 提交原样的 `.lesson.subject`、`.lesson.markdown`、
   `.lesson.html`、`.lesson.manifest` 及实际会话和节点 ID。接受后独立复核
   `.lesson.items`，逐题用 `save_assessment_item()` 原样登记，传入实际会话与节点 ID、
   唯一 `item_id` 和返回的 `package_id`（参数名 `teaching_package_id`）。
   可由会话 ID、课程版本和题目顺序组成 `item_id`，已有登记直接复用。

## 诊断和教学循环

- `generate_diagnostic()` 返回蓝图。正式题目先登记，再用 `submit_diagnostic()`
  保存实际作答。带 question 时必须与引用 item_id 的登记题干一致；无 item_id
  只用于通用学习者自述。`save_diagnostic_result()` 汇总真实观察到的前置与缺口；
  诊断完成后 `next_step` 是 `unit_start`（下一步 `start_unit()`），不会再送回诊断。
- 用 `start_unit()` 进入允许的节点。`continue_lesson()` 默认返回紧凑摘要
  （当前节点、策略、动作、证据阶段、next_call）；需要完整上下文时才传
  `verbose=True`。在预审范围内解释、示范、分层提示，随后给已登记的检查题
  或迁移题；`log_teaching_action()` 记录实际动作，动作词表以回包的 allowed_actions
  或 `get_available_actions()`（full only）为准。
- 使用登记题目，保留实际答案。`submit_answer()` 可组合记录与评分；需要稍后
  语义评阅时不传分数，保留 attempt_id，之后 `commit_assessment()` 提交。
  只有客观题可在登记的 assessor_scope 内使用规则评分，自由文本须语义评阅。
- 若存在 active_misconceptions，先补教并收集纠正证据；新观察到的误解用
  `assess_misconception()` 记录（quickstart 与 full 均提供），再用返回的误解 ID
  调用 `resolve_misconception()`。不要为了消除提示而直接把误解标为解决。
- `advance_lesson()` 由 State Guard 决定是否推进。成功回包带 `next_unit_tag` 与
  `has_next_unit`；没有下一单元时 next_call 指向 `generate_final_report`。检查
  advanced 和实际回执，拒绝时使用 guard、remediation 修复。一次答对不等于持久
  掌握；宿主不能指定 manual_override 绕过守卫。
- `rollback_unit()`（full only）仅在真实前置缺口且契约允许时使用；quickstart
  可继续补教前置节点，确需回退状态则报告档位缺口，不模拟回退。

## 复习、迁移、反思和结课

`get_review_queue()` 获取真实到期项，先让学习者回忆再 `review_answer()`。
`rating` 必须按实际表现取 1–4，并带上当前 `session_id`；回包 `next_call` 给出
`review_item_id`、`session_id`、`allowed_ratings` 和 `required_arguments=["rating"]`，
但不提供可直接照抄的评分——不要依赖其中的评分字段，必须按真实回忆填写。
空队列与到期项都不是全局推进结论，以当前策略和守卫为准。

按 Runtime 的 transfer_requirement 使用 `generate_transfer_probe()` 生成蓝图，
选择已登记的预审题目，收集实际作答后 `record_transfer_result()`（带
`session_id`、`learner_id`、`node_id`、`transfer_type` 与 `score`）。
`record_reflection()` 记录学习者真实反思，不能编造引语或代替用户反思。

最后先 `generate_final_report()`，保存回执并说明观测、估计与未验证假设；成功后
用 `complete_session(session_id)` 关闭（无报告回执时会被 `final_report_required`
拒绝），再读取 `get_learner_snapshot()` 核对 session_status。报告失败时先处理失败，
不直接宣布结课；关闭失败时保留报告，分别说明状态。重复关闭是幂等的，不重复
发出完成事件；该接口不是通用幂等操作。关闭后 `next_call` 为 null 且教学调用返回
`session_closed`；不得继续教学，按用户意图用
`complete_session(status="active", reopen=True)` 显式重开。只需暂停时按用户意图
选择支持的 status。
