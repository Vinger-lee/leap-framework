---
title: "LEAP MCP 与 Agent Skill 架构方案与实施指南"
tags: ["leap", "architecture", "agent-skill", "mcp"]
aliases: ["LEAP MCP 与 Agent Skill 架构方案 guide"]
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP MCP Agent Skill architecture implementation plan foundations definitions workflow`
> Extension: `LEAP MCP Agent Skill architecture failure cases examples comparison`
> Advanced: `LEAP MCP Agent Skill architecture invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/mcp-tools]]

> [!note]- 阅读与验证顺序
> 本文件是 2026-10-26 的架构评审与实施草案：分析基于当时的仓库与 MCP SDK 快照，不代表这些能力已经实现、测试或发布。
> 建议顺序：§0 执行摘要 → §1–§3 职责边界 → §5 Skill 草案 → §8 分发方案；动手实现前重新核对仓库当前状态与 SDK 版本。
> 现行入口见 [接入与验收](docs/agent-skill.md)、[交付政策](docs/teaching-delivery.md) 与 [工具目录](docs/mcp-tools.md)。

# LEAP MCP + Agent Skill 架构方案与实施指南

> **文档版本：** 1.0\
> **编写日期：** 2026-10-26\
> **适用仓库：**
> [Vinger-lee/leap-framework](https://github.com/Vinger-lee/leap-framework)\
> **建议方案：** 先交付仓库级 `leap-tutor` Skill，再验证并评估通过 MCP
> Skills 扩展分发\
> **文档性质：** 架构评审、实施计划、验收标准与可复制的 Skill 草案

------------------------------------------------------------------------

## 0. 执行摘要

### 核心结论

**建议 LEAP 将 MCP 与 Agent Skill 组合使用，但两者不能互相替代。**

-   **LEAP MCP**
    是可调用的能力接口：提供会话、知识图谱、教学包、诊断、作答评估、复习与状态管理等工具。
-   **`leap-tutor` Skill** 是 Agent 的工作流指南：告诉模型何时使用
    LEAP、如何安排调用顺序、怎样解释工具返回、遇到失败如何恢复，以及什么时候不能继续。
-   **LEAP Runtime**
    是权威状态层：负责持久化、状态约束、掌握度估计与状态迁移。Skill
    不能取代运行时校验，也不能自行判定服务端状态迁移是否合法。

LEAP 当前已有粗粒度教学 API、`quickstart`/`full` 工具档位、State
Guard、教学交付政策和集成文档。优先事项不是继续增加大量工具，而是把已有能力组织成一个可复用、可测试的
Agent 工作流，并修复快速工具档位中的流程缺口。

### 建议决策

1.  **P0：** 在仓库中创建
    `.agents/skills/leap-tutor/SKILL.md`，先覆盖完整学习生命周期。
2.  **P0：** 检查并修复 `quickstart` 档位的评估失败恢复与结课能力。
3.  **P1：** 将详细工作流从 MCP 全局指令和重复的接入提示词中逐步整理到
    Skill 与参考文件，服务端硬约束仍保留。
4.  **P1：** 为 Skill 建立静态检查、工具档位契约测试和端到端场景测试。
5.  **P2：** 在 Codex 等目标宿主中验证使用效果后，再决定是否通过官方 MCP
    Skills 扩展发布 Skill。

### 重要边界

本文件是架构建议和实施草案，不代表已经修改 LEAP 仓库、运行测试或发布
Skill。仓库事实基于本次会话此前读取的 `main`
分支文件内容；生成本文时没有重新核对最新提交。真正实施前，应重新检查仓库当前状态、SDK
版本与客户端兼容性。

------------------------------------------------------------------------

## 1. 目标、范围与非目标

### 1.1 目标

本方案要让 LEAP 在支持 Agent Skills 的宿主中更容易被正确使用，重点解决：

-   Agent 不知道从哪个工具开始；
-   工具顺序错误或遗漏必要步骤；
-   模型只看见工具说明，却未理解完整教学生命周期；
-   教学内容、正式题目、评估证据之间缺少可靠衔接；
-   `submit_answer` 部分失败后无法在当前工具档位中恢复；
-   结课时只生成报告，却没有确认会话状态；
-   详细系统提示词过长、重复规则多、不同文档容易漂移；
-   Skill、MCP 工具和运行时行为缺少统一验收标准。

### 1.2 非目标

本方案**不**试图：

-   用 Skill 代替 State Guard；
-   让模型自行写入或修改 LEAP 数据库；
-   让模型自行计算 `mastery_probability`；
-   把工具返回的结构校验结果描述成学科事实已经被证明；
-   保证任何宿主都能自动发现、安装或激活 Skill；
-   在没有真实连接的情况下模拟 MCP 工具调用；
-   一次性重写 LEAP 的状态机、教学策略或数据模型；
-   立即实现所有 MCP 客户端都支持的 Skill 分发系统。

------------------------------------------------------------------------

## 2. 当前架构审查

> 本节记录的是此前查阅到的仓库文件和行为。实施前请以最新代码为准，并运行对应测试。

### 2.1 已有能力

  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  能力                   仓库位置                                                              当前作用                                   对 Skill 方案的意义
  ---------------------- --------------------------------------------------------------------- ------------------------------------------ --------------------------------------------------
  MCP Server 与工具注册  `src/leap/server.py`                                                  注册 LEAP MCP 工具并提供 stdio 服务        Skill 可以复用现有工具，不需要重建运行时

  State Guard            `src/leap/runtime/state_guard.py`                                     约束诊断、教学与状态迁移等入口             服务端继续掌握权威状态决策

  工具档位               `src/leap/runtime/profiles.py`                                        `quickstart` 与 `full`                     Skill
                                                                                               控制客户端可见的工具集合                   必须适应实际暴露的工具，而不能假设所有工具都可用

  粗粒度门面 API         `src/leap/tools/facade.py`、`src/leap/server.py`                      将常见多步调用组合为更少的调用，并返回     Skill 应优先使用粗粒度 API，再按需要使用细粒度工具
                                                                                               `next_call`

  接入提示词与生命周期   `docs/INTEGRATION_CN.md`                                              提供 Host Agent 的职责边界、规则和标准流程 是提炼 `SKILL.md` 的主要来源之一

  门面与工具档位说明     `docs/FACADE_CN.md`                                                   解释 8                                     为 Skill 的调用策略与异常恢复提供依据
                                                                                               个门面工具、`next_call`、恢复方式和档位

  工具目录               `docs/mcp-tools.md`                                                   从实际注册工具生成的参考文档               应用自动化测试防止文档与工具注册漂移

  内容质量与验收         `docs/content-quality.md`                                             说明来源证据、教学包、题目检查和交付验证   应作为 Skill 的质量参考，而不是全部复制进主文件

  工具契约测试           `tests/test_tool_profiles.py`、`tests/test_contract_consistency.py`   验证工具档位与文档/注册目录的一致性        可扩展为 Skill 的契约测试和端到端验收
  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

### 2.2 目前值得保留的设计

1.  **粗粒度门面与细粒度工具共存。** 常见学习流程使用
    `start_learning`、`continue_lesson`、`submit_answer`、`advance_lesson`
    等门面；需要拆分评估或诊断操作时，再使用细粒度工具。
2.  **`next_call` 为 Agent 提供下一步线索。** Skill
    应将其视为运行时建议的重要来源，并检查实际工具目录是否支持该调用。
3.  **状态决策由服务端控制。** Skill
    只能解释拒绝原因、收集缺失证据并选择合法的后续操作。
4.  **内容结构校验与学科真实性区分。** 字段齐全、DAG
    合法、教学包成功保存，不代表知识内容已被外部权威认证。
5.  **工具目录有自动化契约测试。** Skill
    的新增不应破坏已有测试，应扩展测试而不是绕过它们。

### 2.3 需要优先验证的工具档位缺口

此前检查到的 `quickstart` 档位约包含 25 个工具，`full`
档位暴露完整工具目录。工具数可能随版本变化，实施时应以程序实际注册结果为准，而不是硬编码数字。

#### 缺口 A：`commit_assessment` 不在 `quickstart`

`tests/test_tool_profiles.py` 曾明确断言 `commit_assessment` 不属于
`quickstart`。

但 `docs/FACADE_CN.md` 说明：`submit_answer`
如果只记录作答而未提交评分，回包会给出下一步
`commit_assessment`；在第二阶段失败时，也需要根据已返回的 `failed_step`
和 `attempt_id` 进行恢复。

这造成潜在死路：Agent 按照门面 API
的恢复建议继续调用，但快速档位中并没有该工具。

**建议：** - 若 `quickstart` 要支持该恢复路径，就把 `commit_assessment`
纳入档位，并验证必要依赖工具是否同时可用； - 若不打算开放它，就必须在
`submit_answer` 的快速档位契约中提供另一条可执行的恢复路径，并明确告知
Agent； - 不要只通过修改 Skill 文本来掩盖工具目录的缺口。

#### 缺口 B：`complete_session` 不在 `quickstart`

此前检查到的 `docs/INTEGRATION_CN.md` 标准生命周期包含
`complete_session`，而 `QUICKSTART_SETUP_TOOL_NAMES` 没有列出它。

**建议：** - 明确最终报告生成和会话关闭是两个独立操作，还是某个 API
已经组合完成； - 若需要显式关闭，则将 `complete_session`
纳入快速档位； -
增加测试，确认结课报告失败、会话关闭失败和重复关闭分别如何处理； -
只有工具返回明确成功回执后，Agent 才能声称会话已关闭。

#### 档位兼容性原则

Skill 必须读取或遵循宿主实际暴露的工具目录。不得假设 `full` 与
`quickstart` 的工具可用性相同。若 `next_call`
指向不可用工具，应先检查当前档位、错误详情与替代流程；不得编造工具、绕过门禁或将失败描述成成功。

------------------------------------------------------------------------

## 3. MCP、Skill 与 Runtime 的职责边界

### 3.1 推荐分层

``` text
用户意图
   |
   v
Agent + leap-tutor Skill
  - 理解用户目标
  - 选择学习/复习/续学路径
  - 组织教学内容与问题
  - 按工作流调用 MCP
  - 处理返回结果与失败
   |
   v
LEAP MCP 工具层
  - start_learning / continue_lesson
  - submit_answer / advance_lesson
  - 知识结构、教学包、诊断、复习等工具
   |
   v
LEAP Runtime
  - State Guard
  - 权威状态与证据
  - 掌握度估计
  - 状态迁移与持久化
```

### 3.2 责任矩阵

  -------------------------------------------------------------------------------------------------------------------------------
  事项                         Skill / Agent                      MCP 工具层                     Runtime
  ---------------------------- ---------------------------------- ------------------------------ --------------------------------
  理解用户自然语言目标         主责                               不负责                         不负责

  组织工作流与决定下一步调用   主责，并参考返回的 `next_call`     提供建议与操作接口             提供策略/状态结果

  阅读外部教材或官方资料       使用宿主浏览器、搜索、文件等工具   保存证据记录                   检查证据结构与门禁

  生成解释、示例和练习         主责                               提供登记入口                   不负责通用学科内容生成

  维护会话与学习记录           不直接维护权威副本                 提供工具接口                   主责

  计算掌握度                   不得自行伪造                       不应接受宿主随意传入的概率     主责

  决定状态迁移是否合法         不得自行裁决                       请求推进                       State Guard 主责

  开放式回答语义评估           Agent 负责语义判断，并承认不确定性 接收评估证据                   校验记录与状态约束

  工具调用失败恢复             按错误详情选择可用的恢复流程       返回错误、部分成功信息和标识   保证状态一致性并暴露可恢复条件

  是否真的执行成功             读取实际回执后报告                 返回执行结果                   持久化操作并返回状态

  Skill 分发与激活             宿主决定是否加载、审批和激活       可选提供 Skill 资源            不因文件存在就自动视为已激活
  -------------------------------------------------------------------------------------------------------------------------------

### 3.3 三个必须坚持的原则

**原则 1：Skill 是工作流说明，不是安全边界。**\
模型可能忽略或误解提示词，因此关键约束必须由工具与 Runtime 继续执行。

**原则 2：工具回执优先于模型的主观判断。**\
Agent
不能仅凭"我已经调用了"或某个旧快照，就声称新评分已保存、状态已推进或会话已关闭。

**原则 3：结构完整不等于内容正确。**\
LEAP
可以验证记录结构和状态条件，但不能因此声称来源真实、学科结论正确或学习效果已被证明。

------------------------------------------------------------------------

## 4. 推荐的仓库目录结构

第一阶段建议把 Skill 放在仓库内，便于与代码、测试和文档同步版本管理。

``` text
leap-framework/
├── .agents/
│   └── skills/
│       └── leap-tutor/
│           ├── SKILL.md
│           └── references/
│               ├── lifecycle.md
│               ├── content-quality.md
│               └── recovery.md
├── src/
│   └── leap/
│       ├── server.py
│       ├── runtime/
│       └── tools/
├── docs/
│   ├── INTEGRATION_CN.md
│   ├── FACADE_CN.md
│   ├── content-quality.md
│   └── mcp-tools.md
└── tests/
    ├── test_tool_profiles.py
    ├── test_contract_consistency.py
    └── test_skill_contract.py  # 建议新增
```

### 为什么先做一个 Skill

先交付 `leap-tutor`，不要一开始就拆成
`leap-tutor`、`leap-authoring`、`leap-assessment`、`leap-review`
等多个技能。过早拆分会增加触发判断、维护成本和跨 Skill 的规则冲突。

满足以下条件后再考虑拆分：

-   核心 Skill 已经稳定运行；
-   真实任务表明内容创作与日常教学需要明显不同的触发条件；
-   某个子流程的规则或参考资料已大到影响主 Skill 的可读性；
-   子 Skill 可以独立测试，且不复制权威规则。

### 文件职责

  --------------------------------------------------------------------------------------------------------------
  文件                              内容                                               加载建议
  --------------------------------- -------------------------------------------------- -------------------------
  `SKILL.md`                        触发范围、职责边界、核心流程、调用原则、失败总则   激活 Skill 时读取

  `references/lifecycle.md`         新建、续学、诊断、教学循环、复习、结课详细步骤     需要执行完整流程时读取

  `references/content-quality.md`   来源证据、知识 DAG、教学包、题目复核、HTML         创建/更新教学内容时读取
                                    交付要求

  `references/recovery.md`          工具错误、部分成功、State Guard                    出现异常时读取
                                    拒绝、档位不匹配、恢复与断点续学
  --------------------------------------------------------------------------------------------------------------

不要将所有文档一次性塞进
`SKILL.md`。使用按需加载的参考文件，可以减少每次激活的上下文成本。

------------------------------------------------------------------------

## 5. `leap-tutor` Skill 完整草案

以下内容可作为 `.agents/skills/leap-tutor/SKILL.md`
的初始版本。它是实施草案，合并前需要与最新工具签名、策略和测试核对。

``` markdown
---
name: leap-tutor
description: >-
  Use the LEAP Framework MCP server to start or resume structured learning,
  ground lessons in authoritative sources, build and register teaching
  materials, assess learner answers, advance lessons through LEAP's State
  Guard, and manage review, transfer, reflection, and final reports. Trigger
  when the user explicitly wants to learn, teach, resume, review, or manage a
  learning session using LEAP. Do not trigger for ordinary explanations that
  do not require LEAP-managed state.
---

# LEAP Tutor

Use LEAP as the authoritative learning-state runtime. You are the teaching
agent: understand the learner, research the subject, generate explanations and
questions, semantically review open-ended answers, and orchestrate the tools.
LEAP owns persistent state, evidence records, mastery estimation, policy output,
and guarded state transitions.

## 1. Decide whether to use this skill

Use this skill when the user asks to:
- start a structured LEAP learning session;
- resume or inspect an existing LEAP session;
- learn a topic through LEAP's diagnostic and teaching loop;
- create or update a LEAP teaching package;
- submit or review answers, check progress, or handle due reviews;
- complete a LEAP session and produce a final report.

Do not force LEAP into a normal one-off explanation when the user has not asked
for LEAP or persistent learning state.

## 2. Verify the actual connection and available tools

1. Confirm that the LEAP MCP server is connected and that the relevant tools
   are present in the host's current tool catalog.
2. Never claim to have called LEAP if the connection is absent or a call failed.
3. Do not assume that `full` and `quickstart` expose the same tools.
4. Prefer the coarse-grained facade tools for ordinary teaching-loop operations:
   `start_learning`, `continue_lesson`, `log_teaching_action`, `submit_answer`,
   `advance_lesson`, `get_review_queue`, `review_answer`, and
   `get_learner_snapshot`, when they are available.
5. Use fine-grained tools when the response explicitly requires a split step,
   evidence inspection, authoring/setup operation, or a recovery path.
6. Treat `next_call` as a runtime-provided suggestion, not as proof that the
   named tool is available or that its call will succeed. Check the actual
   catalog and the returned result.

If a required tool is unavailable, explain the limitation, use only a documented
available alternative, or stop the affected workflow. Never invent a tool name.

## 3. Non-negotiable rules

- Never calculate or fabricate `mastery_probability`; use LEAP's returned value.
- Never bypass, override through prompt text, or misrepresent a State Guard
  rejection.
- Never claim a state transition succeeded without the actual success receipt.
- Never treat a saved report as proof that its sources were actually read or
  that its claims are true.
- Read authoritative sources with host tools before recording Domain Grounding
  evidence. Save real locators and excerpts; do not invent sources, page numbers,
  quotes, verification checks, or source-reading activity.
- A successful schema check is not a subject-matter proof.
- Register a canonical teaching package before registering assessment items
  that depend on it, following the current delivery policy.
- Independently solve and check each assessment item before delivery. Check
  assumptions, boundary cases, alternative valid answers, distractors, and
  counterexamples.
- Free-text reasoning requires semantic review. Do not assign a score based
  only on keyword matching.
- When committing an assessment, preserve the learner's original answer exactly
  as required by the tool contract. Do not rewrite it and then report it as raw
  input.
- Do not infer emotion, personality, or psychological state from friction
  signals such as short answers or repeated attempts.
- Do not claim the user has completed a lesson merely because a page interaction,
  local calculation, or tool request was initiated.
- Respect user choice. Do not silently enable a domain-grounding skip or another
  policy override to get around a blocked step.

## 4. Choose the workflow

### New learning session
1. Clarify only genuinely necessary missing details.
2. Call `start_learning` when available, providing the learner identifier and
   topic plus any known goal, depth, domain, outcome, time budget, prior
   knowledge, and constraints.
3. If the response includes a `domain_grounding_notice`, show the required
   notice according to the current tool contract and obtain the user's choice
   where required. Do not enable skipping on your own.
4. Follow `next_call` only after verifying that the recommended tool is
   available and its preconditions are satisfied.

### Resume an existing session
1. Prefer a known `session_id` or the documented session lookup/snapshot path.
2. Use `get_learner_snapshot` or the relevant available read tools to recover
   authoritative state.
3. Distinguish stored state from actions that have not yet been committed.
4. Do not create a duplicate session unless the user requests a new one or the
   existing session cannot be identified and the user agrees.

### Review or progress query
1. Read the current learner/session state and due review queue.
2. Use runtime recommendations and node dependencies to decide whether to
   review, continue new learning, or report progress.
3. Do not treat any due review as a global blocker unless the runtime says so.

## 5. Domain Grounding

Before entering a gated diagnostic or teaching stage:

1. Read relevant authoritative materials using host search, browser, or file
   tools. Prefer official documentation, primary sources, textbooks, or the
   applicable syllabus/version.
2. Record the actual source, source type, stable locator, and relevant excerpt.
3. Write a scoped benchmark report that identifies core claims, worked examples,
   independent checks, and limitations.
4. Call `save_benchmark_report` using the current schema.
5. Inspect the result. If grounding remains pending, read `missing_evidence`
   and fill the missing evidence rather than pretending the stage is complete.
6. State what was not checked. Do not claim latest-syllabus alignment, exam
   frequency, or official certification without evidence.

Runtime validation checks evidence structure and gating requirements; it does
not authenticate the truth of the source or claim.

## 6. Build the knowledge structure

1. Fetch `get_teaching_delivery_policy` and relevant `get_subject_catalog`
   information when available.
2. Use `decompose_topic` as a structural template, not as final authored content.
3. Generate useful knowledge nodes with explicit prerequisites, learning
   outcomes, unit tags, and appropriate granularity.
4. Save nodes and edges using the current tool schemas.
5. Call `validate_knowledge_dag`.
6. If validation fails, inspect the reported cycles, dangling edges, isolated
   nodes, or other errors. Correct the graph and validate again.
7. Do not begin a gated stage until the actual preconditions are met.

## 7. Create and register the teaching package

Read the current teaching delivery policy before authoring.

1. Write the complete canonical Markdown knowledge source first.
2. Derive the HTML learning experience from that canonical source; do not let
   the HTML silently contradict or replace the full source.
3. Include prerequisites, conditions, full worked steps, checked examples,
   common misconceptions, boundaries, comparisons, graduated exercises,
   transfer tasks, and meaningful visualizations where relevant.
4. Include real, relevant resource references or precise search queries; do not
   claim that a video was verified when it was not.
5. Check responsive layout, keyboard access, formulas, code examples, and each
   interactive control according to the current web-component specification.
6. Register the complete Markdown and HTML bodies with `save_teaching_package`
   and the required manifest. Do not send only a file path or a claim that a
   package exists.
7. Inspect the returned package identifier and validation result.
8. Independently solve and review each assessment item, then register it with
   `save_assessment_item`, linking the accepted teaching package and required
   source IDs.
9. If the package changes materially, follow the current versioning rules and
   register the updated package/items as required.

Acceptance by Runtime means the submitted record meets structural rules. It
does not independently prove that the subject content is correct.

## 8. Diagnose and teach

1. Generate a diagnostic blueprint and use registered items when the workflow
   requires formal diagnostic questions.
2. Record the learner's actual answer verbatim.
3. Summarize observed prerequisites and gaps without presenting uncertain
   inferences as facts.
4. Enter the teaching loop using `continue_lesson` or the documented fine-
   grained equivalent.
5. Use the returned state, recommended strategy, recommended actions, active
   misconceptions, evidence stage, and due-review information to choose the
   next teaching action.
6. Explain why a step matters. Use progressive disclosure: prompt, hint,
   strategic hint, partial derivation, then a complete worked solution when
   appropriate.
7. After an explanation, include a worked check and a follow-up question or
   transfer probe appropriate to the learning goal.
8. Record the teaching action actually taken using the available decision/log
   tool when required by the runtime contract.

Do not equate one correct answer with durable mastery.

## 9. Assess answers and update evidence

1. Preserve the learner's original response.
2. For objective questions, verify the answer against the registered item's
   assumptions and accepted alternatives.
3. For free-text reasoning, read and semantically evaluate the reasoning.
   Check definitions, conditions, negative statements, calculations, logical
   steps, and alternative valid formulations.
4. Use only scores supported by the observed answer. If evidence is insufficient,
   leave the relevant dimensions unscored where the schema permits or report
   uncertainty; do not fabricate certainty.
5. Use the current `submit_answer` contract when a combined call is appropriate.
6. If the workflow intentionally records an attempt without a score, follow the
   documented `commit_assessment` recovery path only if the tool is actually
   available.
7. Verify the returned receipt and authoritative post-assessment state before
   reporting that an assessment was committed.
8. Do not send a host-computed mastery probability.

## 10. Advance, roll back, or recover

1. Use `advance_lesson` when the facade is available; otherwise follow the
   documented fine-grained check-then-advance flow.
2. If the result rejects advancement, do not repeat the same request blindly.
3. Read the actual rejection reason and required repair action.
4. Provide prerequisite instruction, a worked example, a correction, another
   assessment item, or missing evidence as appropriate.
5. Re-read the state after material updates before attempting advancement again.
6. Use rollback only when supported by the current runtime and justified by
   the learner's actual prerequisite gap.
7. For a partial failure, preserve returned identifiers such as `attempt_id`,
   `package_id`, or other receipt IDs. Resume from the failed step rather than
   repeating successful writes unnecessarily.
8. If the required recovery tool is hidden by the active profile, report that
   the current profile lacks the needed capability. Do not invent success or
   bypass the server.

## 11. Review, transfer, reflection, and closure

- Use `get_review_queue` or the current due-review tool to inspect scheduled
  reviews.
- Record review ratings from the learner's actual recall performance.
- Use transfer probes to check near, variation, far, or integrated application
  when appropriate.
- Record reflection as the learner's reflection, not as a fabricated quote.
- Generate the final report and distinguish observations, estimates, and
  unverified assumptions.
- Call `complete_session` only when the current workflow requires it and the
  tool is available.
- Report the session as closed only after a successful close receipt.
- If report generation succeeds but closure fails, say exactly that; do not
  collapse the two states into one.

## 12. Tool-call and token efficiency

- Prefer one appropriate facade call over manually chaining several equivalent
  low-level calls.
- Use fine-grained tools only when the task requires split assessment, evidence
  inspection, setup, or a documented recovery path.
- Do not re-read large artifacts when a targeted status or snapshot tool gives
  sufficient authoritative information.
- Load reference files only when the corresponding workflow is needed.
- Avoid repeating the full teaching policy in every assistant message; fetch it
  at the point required by the workflow and apply it consistently.
- Do not batch unrelated state changes merely to reduce call count if doing so
  weakens auditability or violates tool preconditions.
- Minimize calls without sacrificing evidence, correctness, or recovery.

## 13. Completion checklist

Before reporting completion, verify all relevant items:

- [ ] The MCP connection was real and the required tools were available.
- [ ] Required Domain Grounding evidence was actually collected and saved.
- [ ] The knowledge DAG passed validation where required.
- [ ] The canonical teaching package was accepted by Runtime.
- [ ] Assessment items were independently checked and registered where required.
- [ ] Learner answers and assessment evidence were committed with matching raw
      answers and receipts.
- [ ] Any advancement was authorized by State Guard and confirmed by a success
      receipt.
- [ ] Review, transfer, and reflection results were recorded where applicable.
- [ ] The final report distinguishes observed evidence from estimates.
- [ ] Session closure was confirmed if the workflow requires it.
- [ ] Any blocked, unavailable, or unverified step is disclosed explicitly.

A checklist item is complete only when supported by the relevant tool result or
actual source evidence. Do not mark an item complete because the instruction
was attempted.
```

------------------------------------------------------------------------

## 6. 参考文件建议内容

### 6.1 `references/lifecycle.md`

应详细说明：

1.  新建会话：目标、深度、时间预算、先验知识与约束；
2.  Domain Grounding：权威来源、证据结构、限制声明；
3.  知识 DAG：节点粒度、边类型、校验和修复；
4.  教学包：Markdown 为规范知识源，HTML 为派生交互呈现；
5.  诊断：正式题目必须先登记，实际作答需要保存原文；
6.  教学循环：读取状态、选取策略、执行教学、收集作答、评估、更新；
7.  状态推进：检查、拒绝原因、修复与再次验证；
8.  复习、迁移、反思与结课。

该文件应以 `docs/INTEGRATION_CN.md`、`docs/FACADE_CN.md`
和最新工具契约为依据，不应创造与 Runtime 不一致的新规则。

### 6.2 `references/content-quality.md`

建议覆盖以下检查：

-   来源是否真的被读取，引用是否可定位；
-   论断是否带有适用范围和必要条件；
-   示例是否独立求解并复核；
-   定义域、参数范围、边界情况和反例是否检查；
-   单选题是否只有一个正确选项；
-   开放式答案是否支持同义表达；
-   教学包的 Markdown 与 HTML 是否一致；
-   交互组件是否真实存在且已测试；
-   `manifest`、资源、来源 ID 和包 ID 是否正确关联；
-   结构验收与学科内容审核是否分别报告。

### 6.3 `references/recovery.md`

至少列出下列恢复策略：

  --------------------------------------------------------------------------------------------------------
  情况                     应采取的动作                                   禁止动作
  ------------------------ ---------------------------------------------- --------------------------------
  MCP 未连接               说明未连接，指导配置或停止依赖 MCP 的流程      假装已调用工具

  工具不存在               检查当前 profile                               编造工具名
                           与真实目录，寻找文档化替代路径

  参数校验失败             按错误详情修正参数后再调用                     不加分析地重复同一请求

  `submit_answer` 部分失败 保留 `attempt_id`，按 `failed_step` 走恢复路径 重新生成或覆盖原始作答

  领域校准仍为 pending     按 `missing_evidence` 补齐真实证据             伪造来源或自行打开跳过开关

  DAG 校验失败             修复节点和边，再次校验                         继续进入被门禁阻止的阶段

  State Guard 拒绝         补前置、纠错或增加真实评估证据                 将拒绝当成可绕过的提示

  教学包校验失败           根据缺失字段或覆盖要求修订正文与 manifest      只换措辞、不补缺失内容

  报告生成成功但关闭失败   分别报告报告状态与会话状态                     声称整个结课流程成功

  工具超时或结果不确定     查询权威状态，确认是否已写入，再决定是否重试   盲目重复可能产生副作用的写操作
  --------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

## 7. MCP Server 全局指令的调整

### 7.1 现状与问题

此前查阅的 `src/leap/server.py` 中，MCP Server 的 `instructions`
已包含相当多的工作流细节：生命周期、领域校准、来源证据、题目登记、教学交付政策、掌握度和状态推进规则。

与此同时，`docs/INTEGRATION_CN.md` 又提供了较长的 Host Agent
系统提示词。重复内容容易导致：

-   同一规则在多个位置维护；
-   一处更新，另一处未更新；
-   每次连接都携带大量细节；
-   Skill 的触发与详细工作流加载难以独立控制。

### 7.2 建议的职责分配

  ----------------------------------------------------------------------------------------------------
  内容                     主要位置                           是否仍需服务端执行
  ------------------------ ---------------------------------- ----------------------------------------
  State Guard 的权威性     简短全局指令 + Runtime             是

  掌握度由 Runtime 估计    简短全局指令 + 工具校验            是

  不得伪造来源或评估证据   全局指令 + Skill + 证据校验        结构与门禁由服务端执行；真实性仍需审查

  完整教学生命周期         Skill 与 `references/lifecycle.md` 关键阶段门禁由服务端执行

  教学包制作细则           `get_teaching_delivery_policy` +   结构约束由服务端执行
                           参考文件

  工具参数和错误契约       工具签名、工具文档和测试           是

  宿主产品如何安装 Skill   各宿主文档                         不由 LEAP Runtime 假设或决定
  ----------------------------------------------------------------------------------------------------

### 7.3 可作为讨论起点的精简指令草案

以下只是概念草案，不应直接覆盖现有
`instructions`。实施时需要逐项对照现有约束、State Guard
测试和客户端实际行为。

``` text
LEAP is a state-driven tutoring runtime.

Use the current session state and runtime policy to guide the learning
lifecycle. Complete required Domain Grounding before entering gated stages.
Read authoritative sources with host tools and record actual evidence.
Register and independently review assessment items before delivery.
Semantically review free-text answers; never fabricate assessment evidence.
Mastery is estimated by LEAP Runtime and must not be supplied by the host.
Never bypass a State Guard rejection. Check tool results and recover from
failures without claiming success.
Fetch get_teaching_delivery_policy before creating teaching materials.
```

### 7.4 不要做的事情

-   不要删除服务端校验，只留下自然语言指令；
-   不要假设 Skill 一定会加载；
-   不要把动态策略硬编码进 Skill 后就不再读取 Runtime 返回值；
-   不要将全局指令缩短到丢失必要的安全边界；
-   不要在尚未建立契约测试前同时重构工具签名、状态机和提示词。

建议先新增 Skill 和测试，再逐步收敛重复指令，每一步都保留可回滚的提交。

------------------------------------------------------------------------

## 8. Skill 分发方案：仓库级 Skill 与 MCP Skills 扩展

截至 2026-10-26，MCP Skills 扩展已有官方规范，标识符为
`io.modelcontextprotocol/skills`。该扩展允许 MCP Server
与工具、资源和提示模板一起发布 Skill。它使用 MCP Resources
读取技能文件，并定义 `skills/list`、`skills/get`，以及可选的
`resources/directory/read`。

**这并不意味着所有 MCP 客户端都自动支持该扩展，也不意味着读取 `SKILL.md`
就等于 Skill 已被激活。** 是否发现、审批、校验并加载
Skill，仍取决于宿主实现。

### 路线 A：仓库级 Skill（建议第一阶段）

位置：

``` text
.agents/skills/leap-tutor/SKILL.md
```

优点：

-   改动最小；
-   与代码和测试共用 Git 版本；
-   便于在 Codex 中试用；
-   不要求 MCP Server 立即支持新扩展；
-   可以先验证 Skill 对工作流正确性、工具调用次数和恢复能力的实际影响。

注意：仓库中有 Skill
文件不代表每个客户端都会自动安装它。每个目标宿主都需要独立验证 Skill
的发现目录、激活方式和工具连接方式。

### 路线 B：通过 MCP Skills 扩展分发（第二阶段候选）

官方扩展文档： - https://skills.extensions.modelcontextprotocol.io/ -
https://skills.extensions.modelcontextprotocol.io/specification/stable/skills -
https://github.com/modelcontextprotocol/ext-skills

扩展规定的关键点包括：

1.  Server 声明 `io.modelcontextprotocol/skills` 扩展能力；
2.  Server 实现 `skills/list` 和 `skills/get`；
3.  Skill 文件通过标准 `resources/read` 读取；
4.  Skill 必须符合 Agent Skills 规范，至少包含带 YAML frontmatter 的
    `SKILL.md`；
5.  Skill manifest 为资源提供摘要与大小信息，宿主读取后应验证内容；
6.  读取资源与激活 Skill 是两件事；激活由宿主的 Skill 加载路径完成；
7.  目标客户端必须真正支持该扩展，才能获得完整的一体化体验。

### 路线 A 与路线 B 对比

  ------------------------------------------------------------------------------
  维度                    仓库级 Skill            MCP Skills 扩展
  ----------------------- ----------------------- ------------------------------
  实现复杂度              低                      中至高

  与仓库版本同步          原生支持                需要构建资源分发与版本机制

  Codex 本地开发体验      适合先行验证            取决于客户端扩展支持

  跨客户端分发            需要各客户端单独安装    对支持扩展的客户端更统一

  内容完整性              由仓库与 Git 供应链管理 还需实现
                                                  manifest、摘要校验和更新处理

  激活行为                由本地宿主 Skill        仍由宿主决定，不是 MCP Server
                          机制决定                单方面强制

  当前建议                **先做**                验证后再做
  ------------------------------------------------------------------------------

### 推荐决策

先用路线 A 建立可靠的
`leap-tutor`，并确认它确实改善工作流质量。只有当用户明确需要"连接 LEAP
MCP 后即可发现并加载 LEAP Skill"，且目标客户端支持相应扩展时，再实施路线
B。

------------------------------------------------------------------------

## 9. 测试策略与验收标准

Skill
不能只通过检查文件存在来验收。应把它当作一个具有触发条件、流程分支、工具依赖和失败恢复要求的工作流组件。

### 9.1 静态检查

建议新增 `tests/test_skill_contract.py`，至少检查：

-   `SKILL.md` 存在且 YAML frontmatter 可解析；
-   `name` 与目录名一致，符合 Agent Skills 命名约束；
-   `description` 非空，并明确使用场景；
-   所有引用的参考文件存在；
-   Skill 引用的工具名与工具目录或明确的可选工具表一致；
-   没有要求模型自行计算 `mastery_probability`；
-   没有要求绕过 State Guard；
-   不将结构校验描述为学科真实性认证；
-   主文件没有把全部参考文档完整复制进来；
-   工具档位调整后，测试与文档同步更新。

### 9.2 工具档位契约测试

建议在现有 `tests/test_tool_profiles.py` 中增加：

-   `quickstart` 包含完成规定核心流程所需的工具；
-   若支持评估部分失败恢复，则 `commit_assessment`
    必须可用，或存在另一条经过测试的恢复路径；
-   若结课需要显式关闭会话，则 `complete_session` 必须可用；
-   `next_call` 指向的关键后续操作，在该 profile
    下必须可执行，或者返回清楚的可恢复错误；
-   不依赖硬编码的总工具数来推断功能完整性；
-   profile 配置拼写错误仍然失败关闭，不可静默扩大工具面。

### 9.3 端到端场景矩阵

  ---------------------------------------------------------------------------------------------------------------
  编号              输入/故障                  预期结果                              通过条件
  ----------------- -------------------------- ------------------------------------- ----------------------------
  E2E-01            用户要求按 LEAP 学新知识   触发                                  真实工具回执可追踪
                                               Skill，确认工具连接，开始会话与校准

  E2E-02            用户只问一个普通知识问题   不强制进入 LEAP 状态工作流            不创建多余会话

  E2E-03            MCP 未连接                 明确告知未连接                        没有伪造调用

  E2E-04            已有会话 ID                恢复当前权威状态                      不无故创建重复会话

  E2E-05            领域证据缺失               保持门禁，补充证据                    未伪造来源，未擅自跳过

  E2E-06            DAG 校验失败               修复并重新校验                        未进入不允许的阶段

  E2E-07            教学包缺少必需覆盖         按错误反馈补全                        只有通过实际校验才报告接受

  E2E-08            自由文本答案               语义评估并提交证据                    没有关键词打分替代推理

  E2E-09            `submit_answer`            保留 attempt，使用可用恢复路径        不丢失或改写原始作答
                    第二阶段失败

  E2E-10            State Guard 拒绝推进       解释拒绝并补充证据                    没有绕过状态守卫

  E2E-11            `quickstart` 隐藏必要工具  明确识别能力缺口                      没有虚构调用成功

  E2E-12            结课报告成功、关闭失败     分别报告两种状态                      没有声称整个流程完成

  E2E-13            运行时返回不确定或超时     查询权威状态再决定是否重试            不盲目重复有副作用的写操作

  E2E-14            Skill 内容更新             版本和测试同步更新                    旧规则不会无声漂移
  ---------------------------------------------------------------------------------------------------------------

### 9.4 建议的发布门槛

在以下条件满足之前，不建议把 Skill 标记为稳定版：

-   [ ] Skill frontmatter 和引用路径通过静态检查；
-   [ ] 当前支持的工具档位通过契约测试；
-   [ ] 所有关键端到端场景均有可复现的测试记录；
-   [ ] 没有任何已知流程要求调用当前 profile 不提供的工具而无替代方案；
-   [ ]
    领域校准、教学包、开放式评估、状态推进和结课的硬边界仍由服务端执行；
-   [ ] 失败恢复不会造成原始作答、评估证据或会话状态不一致；
-   [ ] 文档明确区分结构校验、来源关联、学科正确性和学习效果；
-   [ ] 目标宿主已实际加载 Skill，并确认真实 MCP 工具调用可用；
-   [ ] 发布说明包含适用版本、已知限制和回滚方式。

------------------------------------------------------------------------

## 10. Token 与上下文成本控制

Skill
的价值不只是提高流程正确性，还在于把详细规则按需加载，减少无关上下文。

### 建议做法

1.  **主文件保持短而完整。** 主 `SKILL.md`
    放触发条件、硬边界、工作流摘要、恢复总则和验收清单。
2.  **细则按需加载。** 教学内容制作时才读取
    `content-quality.md`；失败时才读取 `recovery.md`。
3.  **优先使用门面 API。**
    日常教学步骤优先使用粗粒度工具；需要单独评估、检查证据或恢复时再使用细粒度工具。
4.  **不要反复载入完整政策。** 在工作流规定的时点读取
    `get_teaching_delivery_policy`，后续根据需要引用要点，而不是每一轮都复制整份政策。
5.  **只读取必要的状态。**
    续学优先读取快照和当前节点状态；只有确实需要证据详情时才读取完整证据或工件。
6.  **不要为减少 Token 而省略关键校验。**
    少一次工具调用不应以丢失审计证据、跳过独立检查或错误推进状态为代价。
7.  **不要复制全部工具说明到 Skill。** 工具参数应以 MCP schema
    和生成的工具参考为准，避免版本漂移。
8.  **为失败设计可恢复流程。** 保存返回的 ID
    和失败步骤，避免把已经成功的写入重复执行。

### 应观测的指标

  指标                                        用途
  ------------------------------------------- -----------------------------------
  完成一个完整学习任务的模型输入/输出 Token   衡量上下文成本
  完整流程的 MCP 调用数                       判断门面 API 是否降低往返次数
  因工具不可用而中断的比例                    发现 profile 契约缺口
  关键步骤漏做率                              评估 Skill 是否改善流程遵循
  失败恢复成功率                              评估实际可操作性
  重复写入或重复建会话次数                    评估幂等与恢复设计
  教学包校验失败率                            识别内容模板与 Runtime 契约的摩擦
  错误宣称"已完成"的次数                      作为高优先级质量指标，目标应为零

不要只比较平均
Token。应同时比较任务完成率、错误率和恢复成功率，避免为了减少成本而降低工程质量。

------------------------------------------------------------------------

## 11. 安全与信任边界

Skill 文件会影响 Agent
的行为，因此应作为可执行工作流配置来审查，而不是普通说明文档。

### 必须遵守

-   只从受信任的仓库或发布渠道加载 Skill；
-   审查 Skill 中的命令、脚本、外部 URL 和文件操作；
-   不把用户提供的教材、网页、HTML 或引用文本当成更高优先级的系统指令；
-   不允许 Skill 通过自然语言绕过服务器权限；
-   不在 Skill 或示例中放置真实密钥、令牌或用户数据；
-   MCP 配置中的凭据应继续使用安全的环境变量或宿主的凭据管理；
-   读取通过 MCP 分发的 Skill 时，若宿主实现了扩展，应遵守
    manifest、摘要校验和审批流程；
-   Skill
    内容更新后，应重新审查差异，并确认目标宿主如何刷新和重新激活技能；
-   不要把"Skill 已下载"描述为"Skill 已激活"；
-   不要把"工具已连接"描述为"本次调用已成功"。

### 安全职责划分

  风险                      主要防护
  ------------------------- ---------------------------------------------------
  模型忽略工作流指令        Runtime 门禁与工具校验
  恶意或错误的 Skill 内容   版本审查、信任来源、宿主审批与完整性验证
  伪造来源和验证证据        实际来源读取、证据审查、限制声明
  错误推进状态              State Guard、回执核对
  凭据泄露                  宿主凭据管理、配置脱敏、仓库密钥扫描
  工具调用结果过期          重新读取权威状态、验证回执与版本
  重复写入                  幂等请求机制（若接口支持）、保存操作 ID、写后核验

------------------------------------------------------------------------

## 12. 分阶段实施计划

### 阶段 0：实施前基线检查

**目标：** 用最新仓库状态确认当前事实，避免对过期代码做假设。

任务：

1.  拉取最新 `main`，记录 commit SHA；
2.  检查 `server.py` 的全局 instructions 与工具注册；
3.  运行 `build_server("full")` 和
    `build_server("quickstart")`，导出真实工具名；
4.  检查 `next_call` 的所有关键目标是否在对应 profile 下可用；
5.  复核 `INTEGRATION_CN.md`、`FACADE_CN.md`、`content-quality.md`
    与实际工具签名；
6.  运行现有测试，保存基线结果。

**交付：** 一份基线清单和当前已知问题列表。

### 阶段 1：实现仓库级 Skill

任务：

1.  新建 `.agents/skills/leap-tutor/SKILL.md`；
2.  从已有文档提炼生命周期、内容质量与恢复参考文件；
3.  确认 `name` 与目录名一致；
4.  检查主 Skill 没有引入新的业务规则或与 Runtime 冲突；
5.  在目标 Codex 环境验证 Skill 的发现与触发；
6.  用新会话、续学和普通非 LEAP 问题进行最小试用。

**交付：** 可加载的仓库级 Skill 草案。

### 阶段 2：修复快速档位契约

任务：

1.  决定 `commit_assessment` 的暴露策略；
2.  决定 `complete_session` 的暴露策略；
3.  若某工具不开放，提供明确且可测试的替代恢复路径；
4.  更新 `QUICKSTART_SETUP_TOOL_NAMES` 与相关测试；
5.  对关键 `next_call` 进行档位可用性验证；
6.  更新 `docs/FACADE_CN.md`、`docs/INTEGRATION_CN.md` 和工具参考。

**交付：** 没有已知关键流程死路的 `quickstart`。

### 阶段 3：补齐测试和评估

任务：

1.  新建 Skill 静态契约测试；
2.  新建工具档位与恢复路径测试；
3.  将上述端到端矩阵转成可重复的测试或人工验收脚本；
4.  测量 Token、MCP 调用数、漏做率和恢复成功率；
5.  与不加载 Skill 的基线进行对照；
6.  根据失败案例调整规则，而不是仅仅不断加长提示词。

**交付：** 有测试证据支撑的 Skill 版本。

### 阶段 4：整理全局 instructions

任务：

1.  列出服务器 instructions、Skill 和集成文档中的重复规则；
2.  将工作流细节迁移到 Skill 与参考文件；
3.  保留关键运行时边界和必要使用说明；
4.  每次只改动一个可独立验证的部分；
5.  对照现有状态守卫、证据门禁和工具契约测试。

**交付：** 更清晰、重复更少的指令架构。

### 阶段 5：评估 MCP Skills 扩展

任务：

1.  确认目标 MCP SDK 与目标客户端是否支持该扩展；
2.  设计 Skill 资源目录、URI、manifest 和摘要计算；
3.  实现 `skills/list`、`skills/get` 和标准 `resources/read`；
4.  声明正确的能力，并测试不支持扩展的客户端退化行为；
5.  验证资源摘要、大小、更新、审批与重新加载；
6.  发布兼容性矩阵与使用说明。

**交付：** 仅在确有跨客户端分发价值时发布的扩展实现。

------------------------------------------------------------------------

## 13. 风险、未决问题与决策记录

### 13.1 风险清单

  --------------------------------------------------------------------------------------------
  风险                         影响                     缓解措施
  ---------------------------- ------------------------ --------------------------------------
  Skill 与工具签名漂移         调用失败                 自动从工具目录检查引用，统一版本发布

  `quickstart` 缺工具          教学流程中断             测试关键 `next_call` 与恢复路径

  主 Skill 过长                上下文成本上升           参考文件按需加载

  全局指令过度精简             Agent 在 Skill           保留核心硬边界与服务端门禁
                               未加载时误用工具

  过度依赖 Skill               约束可被模型忽略         Runtime 继续强制校验

  扩展客户端支持不一致         Skill 无法自动发现或激活 先采用仓库级 Skill，维护兼容矩阵

  测试只检查文件而不检查行为   产生虚假信心             使用真实 MCP 子进程和失败场景测试

  只追求少 Token               证据不足、内容质量下降   同时评估质量、正确率和恢复成功率
  --------------------------------------------------------------------------------------------

### 13.2 实施前需要确认的问题

-   目标首先是 Codex，还是还要覆盖 Claude Code、Cursor、WorkBuddy
    等其他宿主？
-   `quickstart`
    的产品目标是"新手入门"还是"完成一整节教学的最小完整工具集"？
-   `complete_session`
    是否必须显式调用，还是存在已经确认的等价关闭流程？
-   `submit_answer` 部分失败的推荐恢复方式，是否要求在 `quickstart`
    中原生支持？
-   MCP Skills
    扩展是否已被目标客户端实现？不能只凭扩展规范存在就假定客户端支持。
-   当前 MCP Python SDK
    是否能以兼容方式实现所需的能力声明与方法？实施前应查阅该版本的 SDK
    文档和测试。
-   是否需要为 Skill 采用独立版本号，还是与 LEAP
    发布版本绑定？建议第一阶段与仓库版本同步。

### 13.3 推荐决策记录

  ------------------------------------------------------------------------------------------
  决策                    建议                    理由
  ----------------------- ----------------------- ------------------------------------------
  是否采用 Skill          采用                    LEAP 是多步骤、有状态的工作流，适合 Skill
                                                  编排

  是否替换 MCP            不替换                  Skill 不能提供 Runtime 的持久化与权威状态

  首个 Skill 数量         一个                    降低触发、维护与测试复杂度

  首个 Skill 名称         `leap-tutor`            聚焦核心教学生命周期

  初始分发方式            仓库级                  成本低，适合先在 Codex 验证
                          `.agents/skills/`

  是否立即实现 MCP Skills 暂缓                    先确认价值和客户端兼容性
  扩展

  是否调整 `quickstart`   是，先做契约检查        避免必要恢复操作无法调用

  是否精简全局            是，但后置              先建立 Skill 与测试，避免丢失硬约束
  instructions

  是否追求最少工具数      否                      目标应是最小完整工具集，而非单纯数字最小
  ------------------------------------------------------------------------------------------

------------------------------------------------------------------------

## 14. 实施检查清单

### 架构与代码

-   [ ] 重新检查最新仓库 commit；
-   [ ] 导出 `full` 和 `quickstart` 实际工具目录；
-   [ ] 核对门面工具的所有 `next_call` 分支；
-   [ ] 明确 `commit_assessment` 的恢复契约；
-   [ ] 明确 `complete_session` 的结课契约；
-   [ ] 保留 State Guard 和权威状态校验；
-   [ ] Skill 不直接操作 LEAP 数据库。

### Skill 内容

-   [ ] `SKILL.md` 使用标准 YAML frontmatter；
-   [ ] 触发描述足够明确，避免普通问答时过度触发；
-   [ ] 规定真实连接检查；
-   [ ] 规定 Domain Grounding 和证据限制；
-   [ ] 规定知识 DAG、教学包与题目登记顺序；
-   [ ] 规定开放式回答的语义评估；
-   [ ] 规定失败恢复与状态推进；
-   [ ] 规定复习、迁移、反思与结课；
-   [ ] 详细内容按需拆入 `references/`；
-   [ ] 规则与最新工具契约一致。

### 测试与发布

-   [ ] Skill 静态检查通过；
-   [ ] 工具档位契约测试通过；
-   [ ] 关键失败路径可重复测试；
-   [ ] 在真实宿主中验证 Skill 已被加载；
-   [ ] 记录 Token、工具调用数和流程质量基线；
-   [ ] 文档和版本同步更新；
-   [ ] 明确已知限制和回滚方式；
-   [ ] 未将尚未测试的功能描述为已完成。

------------------------------------------------------------------------

## 15. 参考资料

### LEAP 仓库

1.  [LEAP Framework ---
    README](https://github.com/Vinger-lee/leap-framework/blob/main/README.md)
2.  [LEAP MCP Server ---
    `src/leap/server.py`](https://github.com/Vinger-lee/leap-framework/blob/main/src/leap/server.py)
3.  [Tool profiles ---
    `src/leap/runtime/profiles.py`](https://github.com/Vinger-lee/leap-framework/blob/main/src/leap/runtime/profiles.py)
4.  [Facade implementation ---
    `src/leap/tools/facade.py`](https://github.com/Vinger-lee/leap-framework/blob/main/src/leap/tools/facade.py)
5.  [Host Agent integration guide ---
    Chinese](https://github.com/Vinger-lee/leap-framework/blob/main/docs/INTEGRATION_CN.md)
6.  [Facade and tool profiles ---
    Chinese](https://github.com/Vinger-lee/leap-framework/blob/main/docs/FACADE_CN.md)
7.  [Content quality and integration
    acceptance](https://github.com/Vinger-lee/leap-framework/blob/main/docs/content-quality.md)
8.  [Tool profile
    tests](https://github.com/Vinger-lee/leap-framework/blob/main/tests/test_tool_profiles.py)
9.  [Contract consistency
    tests](https://github.com/Vinger-lee/leap-framework/blob/main/tests/test_contract_consistency.py)

### Agent Skills 规范

10. [Agent Skills ---
    Specification](https://agentskills.io/specification)
11. [OpenAI developer documentation --- Skills
    concepts](https://developers.openai.com/plugins/concepts/skills)
12. [OpenAI developer documentation --- Building
    Skills](https://developers.openai.com/plugins/build/skills)

### MCP Skills 扩展

13. [MCP Skills Extension ---
    Overview](https://skills.extensions.modelcontextprotocol.io/)
14. [MCP Skills Extension --- Stable
    specification](https://skills.extensions.modelcontextprotocol.io/specification/stable/skills)
15. [MCP Skills Extension
    repository](https://github.com/modelcontextprotocol/ext-skills)
16. [Accepted MCP Skills extension
    proposal](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/seps/2640-skills-extension.mdx)

------------------------------------------------------------------------

## 最终结论

LEAP 的下一阶段不应只是继续扩大 MCP 工具集合，而应让 Agent
更稳定地使用已有能力。

**推荐路径是：先建立一个标准、可测试、按需加载的 `leap-tutor`
Skill；修复 `quickstart` 中必要的恢复与结课契约；保留 Runtime
的权威状态约束；最后再决定是否通过 MCP Skills 扩展实现一体化分发。**

这样既能提升 LEAP
的可用性，也能避免把工作流、安全边界、工具接口和客户端分发混成一个难以维护的单体系统。
