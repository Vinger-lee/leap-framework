# 失败与断点恢复

每次检查 ok、error.code、error.details、failed_step 及返回 ID。保留已经成功的
写入，不把请求已发出当作已保存。参数以实际 MCP schema 为准。回包为紧凑
envelope（`policy_version`），需要完整交付政策时单独调用
`get_teaching_delivery_policy()`，不要凭记忆复述政策。

| 情况 | 恢复操作 |
|---|---|
| MCP 未连接 | 明确说明未连接，停止受影响步骤；不伪造调用或回执。 |
| 工具不可见 | 检查真实目录与档位；只采用文档化替代路径，否则说明缺口或切换档位。 |
| 参数校验失败 | 读错误及 schema，修正具体参数；不原样重复请求。 |
| Domain Grounding pending | 按 missing_evidence 补真实来源、定位、摘录或独立检查；不伪造或自行开启跳过。 |
| 用户要求跳过校准 | 先取得明确知情确认，再调用 `set_domain_grounding_skip(session_id, allow_skip=True, reason=...)` 记录；不重开会话、不自行跳过。 |
| 知识 DAG 被拒 | 修复环、缺失端点、孤立节点等实际问题，再保存并校验；不进入被门禁挡住的步骤。 |
| 教学包不完整 | 对照返回 validation 补正文、覆盖、manifest 与来源关联；仅改措辞不算修复。 |
| State Guard 拒绝 | 读 guard 与 remediation，补教前置、纠错、收集无提示/迁移/复习证据后重读状态；不接受 manual_override 绕过。 |
| 状态版本过期 | `get_learner_snapshot()` 后重新决策，不把旧快照用于强制推进。 |
| `session_closed` | 会话已关闭；停止教学写入，查询快照确认状态，按用户意图用 `complete_session(status="active", reopen=True)` 显式重开后再继续。 |
| 报告成功、关闭失败 | 保留报告回执；查询 session_status，未关闭才修正问题并重试关闭；分别报告两种状态。 |
| 关闭缺报告 | `final_report_required`：先 `generate_final_report()`，不要为关闭而伪造报告。 |

## 作答已保存而评估未完成

`submit_answer()` 未带评分时返回 assessed=false，并给出 `commit_assessment()`
的 next_call.arguments。先语义评阅，再用其中的 attempt_id 与完全一致的
raw_answer 提交有支持的评分，确认成功回执。同一 attempt 只 commit 一次；重复
提交返回既有结果或 `already_assessed`，不再产生第二条评分。

评分阶段错误时读取 error.details.failed_step 和 attempt_id；作答已保存。
按具体错误修正分数、评阅类型、原文或状态版本，用 `commit_assessment()` 完成
已有 attempt。不重跑 `submit_answer()`，不改写原文，不重复登记正式题目。

quickstart 和 full 均提供这条恢复路径。若宿主仍看到旧目录，说明版本/档位
不匹配，刷新受支持的连接或切到 full；不得声称隐藏工具已调用成功。

## 超时与未知结果

先查询权威状态，核对已保存操作再决定是否重试。`request_id` 可用于审计与
幂等关联；仍以实际回执为准。

- `get_learner_snapshot()` 可确认会话状态和当前节点；它不能确认某次新评分的
  回执。保存已有 attempt_id、package_id、报告 ID、请求与错误。
- `get_assessment_history()`、`get_evidence()`、`list_artifacts()`（full only）
  可按需要核查细节；quickstart 无法确认具体写入时应说明未知，暂停该写入并
  请求所需读能力，不盲目补写第二条作答、评分、报告或新会话。
- `complete_session()` 成功后不要再次关闭来“确认”；查询快照即可。重复关闭
  不改变最终状态，也不再重复发出完成事件；关闭后回包 `next_call` 为 null。
- 会话关闭后任何教学调用会返回 `session_closed`；不要把它当作可重试的瞬时错误。

恢复后只报告实际确认的状态；未验证、仍失败或不可见的步骤单独列明。
