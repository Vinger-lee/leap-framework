---
title: "LEAP MCP 与 Agent Skill 接入"
tags: ["leap", "engineering"]
aliases: ["LEAP MCP 与 Agent Skill 接入 guide"]
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP repository Agent Skill host activation recovery acceptance foundations definitions workflow`
> Extension: `LEAP repository Agent Skill host activation recovery acceptance failure cases examples comparison`
> Advanced: `LEAP repository Agent Skill host activation recovery acceptance invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/host-config]] · [[docs/FACADE_CN]] · [[docs/INTEGRATION_CN]]

# LEAP MCP 与 Agent Skill 接入

`leap-tutor` 的入口是仓库内
[SKILL.md](../.agents/skills/leap-tutor/SKILL.md)，随 LEAP 2.1.0 维护，当前为
**draft**。Skill 组织工作流；MCP 暴露工具；Runtime 继续保存权威状态并执行所有
领域、教学包、题目与状态门禁。Skill 不直接操作数据库，也不计算掌握度。

The repository skill is a draft workflow guide versioned with LEAP 2.1.0. MCP
and Runtime retain all enforcement. Host discovery and activation are separate
from reading a file or connecting a server.

> 配置 MCP 与安装 Skill 的可照抄命令见 [[docs/host-config|宿主 MCP 配置与 Skill 安装]]；
> 本页说明支持范围、档位差异与验收方法。

## 使用与兼容范围

1. 先按 [[docs/host-config|配置页]] 配好 LEAP MCP，选择 `quickstart` 或 `full`。
   先用实际只读调用确认连接，如 `get_teaching_delivery_policy`；参数以当前 MCP
   schema 为准。
2. 在支持仓库技能的宿主中打开本仓库，确认宿主把 `leap-tutor` 显示为已发现且
   可调用。`.agents/skills/` 是跨客户端共享约定，但**是否扫描由宿主决定**；
   Claude Code 只扫描 `.claude/skills/`，需复制（见配置页 §3）。文件出现在仓库中
   不证明已安装或激活。
3. 触发方式：用明确的学习请求（例如“用 LEAP 学习线性方程”），或按宿主自己的
   显式语法调用（Claude Code 为 `/leap-tutor`）。**不要假定 `$leap-tutor` 这类
   写法在所有宿主可用**；各宿主语法以厂商文档为准。
4. 不支持 Skill 的宿主继续使用 [[docs/INTEGRATION_CN|中文接入指南]] /
   [[docs/INTEGRATION|English integration guide]]；指南按档位分成两份提示词，
   复制时选与当前工具面对应的那份。服务器仍提供核心边界和动态教学政策，
   不依赖 Skill 执行门禁。

## 宿主支持矩阵

| 宿主 | MCP 配置 | Skill 位置与发现 | 状态 |
|---|---|---|---|
| DSH | 通过设置/`plugin_manager` 添加 stdio MCP 条目 | 项目 `.agents/skills`、`.dsh/skills`、`~/.dsh/skills`、`~/.agents/skills`；`<name>/SKILL.md` | 宿主契约明确列出 `.agents/skills`（**已确认扫描规则**）；端到端触发未在本机实测 |
| Claude Code | 项目 `.mcp.json` | 仅 `.claude/skills/<name>/SKILL.md` 等位置；**不扫描 `.agents/skills`** | 按官方文档；需复制 Skill（未在本机实测触发） |
| Claude Desktop | `claude_desktop_config.json` | 不支持仓库 Skill | 用提示词路径 |
| Cursor | `.cursor/mcp.json` | 以 Cursor 当前版本为准 | **未验证** |
| Codex | 同类 stdio MCP 配置 | 仓库级 Skill 支持 | **未验证**（本仓库未取得真实加载证据） |
| WorkBuddy | 同类 stdio MCP 配置 | 仓库级 Skill 支持 | **未验证** |

任何"未验证"行都不得在发布说明中写成"支持"；需要实际加载日志才能升级状态。

## 档位差异（本次修复后）

| 档位 | 本次调整 | 保留的限制 |
|---|---|---|
| quickstart | 开放 `commit_assessment`、`resolve_misconception`、`assess_misconception`、`complete_session`、`find_session` 与建会话后的领域校准跳过记录工具 `set_domain_grounding_skip`；关闭会话后明确 `session_closed` / `next_call=null` | 无细粒度证据查询与页面 outbox 全套接口；需要时切到 full |
| full | 全部工具（本次新增 `set_domain_grounding_skip`） | 客户端仍须独立配置 MCP 和 Skill |

实际工具数与档位归属以 [[docs/mcp-tools|生成的工具参考]] 为准，不要按本节数字硬编码。

`next_call`、`follow_up` 和 `then` 需要核对真实目录。`submit_answer` 无分数或
评分失败后，保留 attempt_id，直接提交 commit_assessment；不重复保存原答。
`generate_final_report` 保存报告，`complete_session` 修改会话状态，二者不能互相
替代；关闭默认要求已有报告回执，重复关闭幂等（`already_applied`）且不再重复发出
完成事件，`completed→active` 需 `reopen=True`。`request_id` 可用于审计与幂等关联，
但仍以实际回执为准。`start_learning` 默认复用同一 learner+topic 的 active 会话；
`advance_lesson` 成功回包带 `next_unit_tag`/`has_next_unit`。遇超时先查询状态，无法确定具体写入时暂停该写入并补充读能力。

## 回包与上下文成本

本次修复后，工具回包只带紧凑的 `policy_version`（不再每次附完整 2.4 KB 交付
政策）；完整政策只在创作前调用一次 `get_teaching_delivery_policy()`。日常教学
优先 `continue_lesson()`，它默认返回紧凑摘要，只有需要完整教学上下文时才传
`verbose=True`；需要时再单独取 `get_teaching_delivery_policy()`。选 `quickstart`
还能缩小一次性工具 schema（约 26 KB vs full 约 54 KB）。

## 实施基线与复现

实施使用本地 HEAD `58b07a0135f2c9d03333f4f058ddfbac274ba897`，未对已有未提交
修改执行 pull。Python 3.12，MCP SDK 2.3.0。工具数与测试计数以实际运行输出为准：
`python -m pytest` 的输出与 `python scripts/generate_tool_reference.py --check` 是唯一
权威数字，本页不写死。

```bash
python -m pytest tests/test_skill_contract.py tests/test_tool_profiles.py tests/test_skill_mcp.py
python -m pytest
python scripts/generate_tool_reference.py --check
```

静态检查验证 frontmatter、版本、参考路径和工具存在性；真实 stdio 测试使用临时
SQLite 与明确标记的合成来源，验证 Runtime 契约，并覆盖校准跳过记录、误解记录、
复习评分、迁移、反思与关闭后行为。它们不证明宿主触发、真实来源阅读、语义评分
质量、浏览器效果或学习效果。

## 场景验收矩阵

| 场景 | 可复现证据 / 宿主检查 |
|---|---|
| E2E-01 新学习触发 | test_skill_mcp 验证真实建会话与校准；宿主触发待实测 |
| E2E-02 普通问题 | 新宿主只问“递归是什么”，确认不建 LEAP 会话；待实测 |
| E2E-03 MCP 未连接 | 断开测试连接后请求 LEAP，确认明确报告不可用且不编造回执；待宿主实测 |
| E2E-04 已有会话 | stdio 测试按 session_id 恢复快照，确认没有第二个会话 |
| E2E-05 缺领域证据 | stdio 测试拒绝诊断、保存 pending、补证据后通过 |
| E2E-06 用户选择跳过校准 | stdio 测试：显示 notice 后调用 `set_domain_grounding_skip`，会话不重开，诊断/教学继续 |
| E2E-07 DAG 无效 | stdio 测试拒绝悬空边，补节点后保存并重新校验 |
| E2E-08 包覆盖不足 | stdio 测试拒绝残缺 Markdown，补全后接受并标记未认证学科内容 |
| E2E-09 自由文本 | stdio 测试拒绝 rule 评分、接受 model 证据且原文不变；语义质量待宿主实测 |
| E2E-10 评分阶段失败 | stdio 测试 invalid_score 保留 attempt_id，修复后没有重复作答 |
| E2E-11 拒绝推进 | stdio 测试返回 remediation 且会话节点与状态版本不变 |
| E2E-12 工具隐藏 | 静态与目录测试覆盖必要工具；误解分支实际记录/解决；拼错档位仍拒绝 |
| E2E-13 报告/关闭 | stdio 测试报告失败不关闭；报告成功、关闭失败保留报告；关闭后 `session_closed` 且 `next_call=null` |
| E2E-14 复习与迁移 | stdio 测试走真实复习队列（rating 按真实回忆填写）、迁移结果与反思 |
| E2E-15 Skill 更新 | 静态测试绑定仓库版本、引用和工具契约；刷新与重新激活待宿主实测 |

## 本次验证记录

2026-11-08（修复后）：全量测试与技能契约测试结果见仓库测试输出；随本页更新的
`tests/test_skill_contract.py` 校验 frontmatter、版本、参考路径与双档位工具
存在性，`tests/test_skill_mcp.py` 在真实 stdio 上覆盖主流程、校准跳过、误解、
复习、迁移、反思与关闭后行为。知识库检查覆盖全部 Markdown；架构方案文档按
知识库格式维护，技能文件使用独立契约检查，不按教材格式验收。

## 宿主试用、指标和发布条件

用同一仓库版本、相同测试学习者和材料，在隔离数据库中分别启用/禁用 Skill
运行新学习、按 ID 续学、普通问答及上表失败案例。保留宿主加载记录、真实 MCP
调用与回执、来源读取记录。评阅开放式答案时加入否定句、等价表达、错误数字与
条件缺失案例；不只检查关键词。

每组记录模型输入/输出 Token、MCP 调用数、漏步数、恢复成功率、重复写入/建会话
次数、教学包失败率和错误完成宣称次数；与未加载 Skill 的基线对照。当前尚无
启用/禁用 Skill 的宿主对照或 Token 收益数据，不据此宣称稳定版或成本降低。

首轮支持范围是**仓库级 Skill + stdio MCP**；本仓库只在本地验证了文件契约、
档位契约与 stdio Runtime 流程，真实宿主发现与激活仍待新宿主会话验收。
Claude Code、Cursor、Codex、WorkBuddy 等宿主未在本机验证（见宿主支持矩阵）。
MCP Skills 扩展按方案暂缓，未实现 skills/list、skills/get 或扩展能力声明。

只有宿主触发、关键失败恢复、原文一致性和对照指标都有记录后，才调整 draft
状态。更新 Skill 时同步 metadata 中的仓库版本和相关测试；核对宿主刷新行为。
回滚可停用仓库 Skill、恢复接入指南提示词并继续使用 full；档位改变不涉及数据
迁移。保留已有评估和报告，不通过回滚删除学习记录。

> [!note]- Reading and verification sequence: LEAP repository Agent Skill host activation recovery acceptance
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[docs/host-config]] · [[docs/FACADE_CN]] · [[docs/INTEGRATION_CN]] · [[docs/FACADE]] · [[docs/INTEGRATION]]
