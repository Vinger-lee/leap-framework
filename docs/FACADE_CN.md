---
title: "粗粒度教学 API 与工具档位"
tags: ["leap", "integration", "reference"]
aliases: ["粗粒度教学 API 与工具档位 guide"]
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP 粗粒度教学 API 门面层 next_call 工具档位 foundations definitions workflow`
> Extension: `LEAP 粗粒度教学 API 门面层 next_call 工具档位 failure cases examples comparison`
> Advanced: `LEAP 粗粒度教学 API 门面层 next_call 工具档位 invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/INTEGRATION_CN]] · [[docs/mcp-tools]] · [[docs/FACADE]] · [[docs/scope-and-limits_CN]] · [[README_CN]] · [[docs/host-config]]

# 粗粒度教学 API 与工具档位

Runtime 的工具面刻意做成细粒度：每次状态变更都是独立的可审计调用，State Guard 是唯一可以
放行状态迁移的组件。代价落在宿主 Agent 身上——一个教学回合常常需要六次以上且顺序正确的调用，
顺序错误是最常见的接入故障。

本文说明消除这部分成本的两件事：**粗粒度教学 API**（8 个工具，在服务端组合细粒度调用）与
**工具档位**（`quickstart` 提供日常教学所需的较小工具集合，实际目录见生成参考）。

## 1. 粗粒度教学 API

每个粗粒度工具内部调用与细粒度工具完全相同的 runtime 方法。它是门面层（facade），不是第二套
状态机，因此同一个会话内可以混用两种调用。

完整的粗粒度工具清单、组合语义、签名与档位归属见 [[docs/mcp-tools|自动生成工具参考]]。

每个回包都带 `next_call`：下一次该调用的工具、参数与原因。门面层因此是自解释的，宿主 Agent
不必记住生命周期。`next_call` 只保证目标工具在当前档位存在；涉及语义决策的参数（例如复习
评分）必须按真实观察填写；`next_call` 给 `review_item_id`/`session_id`/`allowed_ratings`，
但不提供可照抄评分；会话关闭后回包 `next_call` 为 null。

### 门面层没有改变的东西

- **State Guard 仍然是唯一裁决者**：`advance_lesson` 先试跑 Guard，被拒时返回
  `advanced: false` 与失败的具体检查项和修复动作，且不写入任何状态；拒绝不是"重试"信号。
- **失败仍是失败**：失败步骤返回 `{"ok": false, "error": {"code", "message", "details"}}`。
  `submit_answer` 第二步失败时，回包会给出 `failed_step` 与已落库的 `attempt_id`，宿主可修好
  原因后直接调用 `commit_assessment`，作答不会丢失。
- **原始作答逐字保存**，并复用为 `raw_answer`，消除 attempt 与 assessment 文本不一致的常见错误。
- **掌握度仍由服务端估计**，`mastery_probability` 不接受宿主传入。
- **交付政策 3.0 仍然生效**：回包使用紧凑 envelope，只携带 `policy_version`；需要完整政策时
  调用一次 `get_teaching_delivery_policy()`，不凭记忆复述。
- **两档均执行领域校准与题目门禁**。`submit_answer` 和 `continue_lesson`
  等工具要求当前有效证据和预审教学包。

### `submit_answer` 的两种合法用法

带分数时一次调用同时落库作答与评估；不带分数时只落库作答，并返回指向 `commit_assessment` 的
`next_call`——这正是自由文本仍待宿主语义评审时应采取的形态。绝不能用关键词推导分数。

两个档位都开放 `commit_assessment`，评分失败时保留 `attempt_id`，修正后直接
提交原文与评分，不重新记录作答。`assess_misconception`（记录新误解）与
`resolve_misconception`（解决已有误解）也在两个档位中可用，使教学门面的误解分支
有真实可执行的后续工具。必须先有纠正证据再标记解决。

用 `get_grounding_sources` 读取预审来源的定位和检查题，按 [[docs/INTEGRATION_CN]]
完成校准并登记预审教学包。首包用 `topic="高等数学"`，范围为「从极限到导数与可导性」。
证据缺失、撤回或过期时暂停正式授课。

`start_learning` 默认复用同一 learner+topic 的 active 会话（回包
`existing_session=true`）；确实要新会话时才传 `force_new=True`。
`advance_lesson` 成功回包带 `next_unit_tag`/`has_next_unit`；没有下一单元时
`next_call` 指向 `generate_final_report`。`get_review_queue` 的 next_call 提供
`review_item_id`/`session_id`/`allowed_ratings` 与 `required_arguments=["rating"]`，
但不预填评分，必须按真实回忆填写 1–4。

### 报告与关闭

`generate_final_report` 只生成并保存报告；`complete_session` 才修改会话状态。
先核对报告回执，再关闭并用 `get_learner_snapshot` 确认 `session_status`。
报告成功而关闭失败时分别报告，不能宣称整个结课已完成。重复关闭是幂等的，不再
重复发出完成事件；`request_id` 只能作为审计/幂等关联，不能替代实际回执。
关闭后回包 `next_call` 为 null，`continue_lesson`、`submit_answer` 等教学调用返回
`session_closed`；不得继续教学，需按用户意图用
`complete_session(status="active", reopen=True)` 显式重开会话。

## 2. 工具档位

档位决定 MCP 客户端看到多少工具。注册过程在各档位完全一致，runtime 能力不减少，切换档位不需要
数据迁移。

| 档位 | 内容 |
|---|---|
| `quickstart` | 36 个工具，涵盖粗粒度教学 API、预审来源校准、知识 DAG、预审教学包与题目登记、诊断、评估恢复、误解、迁移、反思、报告和结课 |
| `full` | 75 个工具（默认），含细粒度状态与证据查询、教学草稿和页面桥接 |

数量与逐工具档位归属见 [[docs/mcp-tools|生成工具参考]]。`next_call` 及其后续调用
仍需检查宿主真实目录。现有 HTML outbox 全套桥接与细粒度证据读取需 `full`；
会话查找 `find_session` 两个档位都可用；
quickstart 下无法确认具体写入时暂停该写入，补充查询能力，避免重复写入。
支持仓库 Skill 的宿主参见 [leap-tutor 接入与验收](agent-skill.md)，MCP/Skill 配置
样例见 [[docs/host-config|宿主配置]]。

回包成本：修复后每次调用只带紧凑 `policy_version`，完整交付政策用
`get_teaching_delivery_policy()` 取一次；`continue_lesson()` 默认只回当前节点摘要，
需要完整上下文时传 `verbose=True`。`quickstart` 还能把一次性工具 schema 从约 54 KB
降到约 26 KB。

选择顺序：

```bash
python -m leap.server --tool-profile quickstart    # 显式参数
LEAP_TOOL_PROFILE=quickstart python -m leap.server  # 环境变量
# 或在 config/default.yaml 中设置 tool_profile: quickstart
```

档位名写错会在启动时报错，不会静默退回 `full` 而暴露全部工具。

## 3. 如何验证粗粒度接入

测试与验证命令统一见 [[CONTRIBUTING|贡献指南]]；安装状态可用 `python -m leap.doctor` 自检。

门面层测试不只覆盖顺利路径：被拒的推进不改变任何状态、评估失败后作答仍可补救、无法识别的学习模式
会被回报，Grounding 门禁仍然生效。

## 4. 何时仍应用细粒度工具

当你需要把一次粗粒度调用的两半分到不同时刻执行时（例如先记录作答、人工评审后再评估），或需要在
提交前比较多个候选动作时。两套 API 操作同一批数据行、事件与版本号。

> [!note]- Reading and verification sequence: LEAP 粗粒度教学 API 门面层 next_call 工具档位
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README_CN]] · [[docs/FACADE]] · [[docs/INTEGRATION_CN]] · [[docs/scope-and-limits_CN]] · [[docs/host-config]] · [[docs/agent-skill]]
