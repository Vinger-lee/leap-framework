# 学习生命周期

用于实际 LEAP 教学与续学。工具参数以宿主 MCP schema 和实际返回为准；回包为紧凑
envelope，完整交付政策只在创作前用 `get_teaching_delivery_policy()` 获取一次。

## 建会话和续学

新会话调用 `start_learning()`，提供 learner_id、topic 及已知目标、深度、领域、
预算、先验知识和约束；仅澄清会影响教学的缺失信息。同一 learner+topic 的 active
会话默认复用（回包 `existing_session=true`），确实要新会话时才传 `force_new=True`。
原样展示返回的校准 notice，取得要求的用户选择，不自行开启跳过：

- 用户选择继续：走 Domain Grounding，用自己的工具真实阅读来源。
- 用户选择跳过：先取得明确、知情的确认（说明幻觉与内容出错风险），再调用
  `set_domain_grounding_skip(session_id, allow_skip=True, reason=...)` 记录选择；
  不得重开一个新会话，也不得自行传跳过参数。已完成/已跳过的校准不会被后续
  不完整的 `save_benchmark_report` 降级。

有 session_id 时先 `get_learner_snapshot()`，检查 session_status、current_node_id、
setup_gaps、证据阶段与到期复习。已关闭会话不自动重开；先确认用户意图，再用
`complete_session(status="active", reopen=True)` 显式重开。会话 ID 不明时用
`find_session()` 查找（两个档位都提供），不为续学自动新建会话。

## 领域、知识结构和教学包

1. 用宿主文件、搜索或浏览器真实读取权威教材、官方文档或适用版本大纲。
2. `save_benchmark_report()` 提交定位、摘录、来源关联论断、独立检查的完整例题
   与限制。若 pending，按 missing_evidence 补实际证据；已完成状态只升级不降级。
3. 获取 `get_teaching_delivery_policy()` 和适用 `get_subject_catalog()`；目录不是
   所有学科的穷举。`decompose_topic()` 只给模板，节点内容由宿主编写。
4. 用 `save_knowledge_nodes()`、`save_knowledge_edges()` 保存有明确前置和粒度的
   节点与边，执行 `validate_knowledge_dag()`。保存时也会校验；失败则修复，
   不依赖“已发起保存”进入后续阶段。
5. 按内容质量参考完成 Markdown、HTML、manifest，经 `save_teaching_package()`
   接受后，将实际 package_id 和 source_ids 用于 `save_assessment_item()`。

## 诊断和教学循环

- `generate_diagnostic()` 返回蓝图。正式题目先登记，再用 `submit_diagnostic()`
  保存实际作答。带 question 时必须与引用 item_id 的登记题干一致；无 item_id
  只用于通用学习者自述。`save_diagnostic_result()` 汇总真实观察到的前置与缺口；
  诊断完成后 `next_step` 是 `unit_start`（下一步 `start_unit()`），不会再送回诊断。
- 用 `start_unit()` 进入允许的节点。`continue_lesson()` 默认返回紧凑摘要
  （当前节点、策略、动作、证据阶段、next_call）；需要完整上下文时才传
  `verbose=True`。按学习目标解释、示范、分层提示，随后给经过独立复核的检查题
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
登记并独立检查正式题目，收集实际作答后 `record_transfer_result()`（带
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
