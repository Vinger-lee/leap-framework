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

Related: [[Knowledge_Index]] · [[docs/INTEGRATION_CN]] · [[docs/mcp-tools]] · [[docs/FACADE]] · [[docs/scope-and-limits_CN]] · [[README_CN]]

# 粗粒度教学 API 与工具档位

Runtime 的工具面刻意做成细粒度：每次状态变更都是独立的可审计调用，State Guard 是唯一可以
放行状态迁移的组件。代价落在宿主 Agent 身上——一个教学回合常常需要六次以上且顺序正确的调用，
顺序错误是最常见的接入故障。

本文说明消除这部分成本的两件事：**粗粒度教学 API**（8 个工具，在服务端组合细粒度调用）与
**工具档位**（`quickstart` 只暴露约 25 个工具，而不是 70 个）。

## 1. 粗粒度教学 API

每个粗粒度工具内部调用与细粒度工具完全相同的 runtime 方法。它是门面层（facade），不是第二套
状态机，因此同一个会话内可以混用两种调用。

完整的粗粒度工具清单、组合语义、签名与档位归属见 [[docs/mcp-tools|自动生成工具参考]]。

每个回包都带 `next_call`：下一次该调用的工具、参数与原因。门面层因此是自解释的，宿主 Agent
不必记住生命周期。

### 门面层没有改变的东西

- **State Guard 仍然是唯一裁决者**：`advance_lesson` 先试跑 Guard，被拒时返回
  `advanced: false` 与失败的具体检查项和修复动作，且不写入任何状态；拒绝不是"重试"信号。
- **失败仍是失败**：失败步骤返回 `{"ok": false, "error": {"code", "message", "details"}}`。
  `submit_answer` 第二步失败时，回包会给出 `failed_step` 与已落库的 `attempt_id`，宿主可修好
  原因后直接调用 `commit_assessment`，作答不会丢失。
- **原始作答逐字保存**，并复用为 `raw_answer`，消除 attempt 与 assessment 文本不一致的常见错误。
- **掌握度仍由服务端估计**，`mastery_probability` 不接受宿主传入。
- **交付政策 3.0 仍然生效**：粗粒度回包只携带一次政策，嵌套子回包中的重复副本会被移除。
- **前置与题目门禁仍然生效**：未完成 Domain Grounding 时，`submit_answer` 与 `continue_lesson`
  同样返回 `domain_grounding_required`。

### `submit_answer` 的两种合法用法

带分数时一次调用同时落库作答与评估；不带分数时只落库作答，并返回指向 `commit_assessment` 的
`next_call`——这正是自由文本仍待宿主语义评审时应采取的形态。绝不能用关键词推导分数。

## 2. 工具档位

档位决定 MCP 客户端看到多少工具。注册过程在各档位完全一致，runtime 能力不减少，切换档位不需要
数据迁移。

| 档位 | 工具数 | 内容 |
|---|---|---|
| `quickstart` | 25 | 粗粒度教学 API + 完成一节课必需的配置工具：Domain Grounding、知识 DAG、canonical 教学包、题目登记、诊断、迁移、反思与结课报告 |
| `full` | 70 | 全部已注册工具（默认） |

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

[[Knowledge_Index]] · [[README_CN]] · [[docs/FACADE]] · [[docs/INTEGRATION_CN]] · [[docs/scope-and-limits_CN]]
