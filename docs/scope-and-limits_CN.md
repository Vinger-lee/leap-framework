---
title: "范围与边界"
tags: ["leap", "engineering", "scope"]
aliases: ["范围与边界 guide"]
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP 范围 边界 保证 证据 foundations definitions workflow`
> Extension: `LEAP 范围 边界 保证 证据 failure cases examples comparison`
> Advanced: `LEAP 范围 边界 保证 证据 invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/FACADE_CN]] · [[docs/INTEGRATION_CN]] · [[docs/mcp-tools]] · [[docs/scope-and-limits]] · [[README_CN]]

# 范围与边界：LEAP 不做保证的事情

本文明确写出框架的边界，避免接入决策建立在对 README 的乐观解读上。下面依次说明 runtime 真正负责
什么、什么仍由宿主 Agent 承担、以及哪些说法目前没有证据支持。

## 1. Runtime 负责的部分

- **状态一致性**：学员状态、证据阶段、掌握度估计与复习排程都持久化、带版本号，并可由事件日志复现。
- **迁移裁决权**：任何推进都必须通过 State Guard；被拒的迁移是结构化拒绝，绝不静默写入。
- **掌握度估计**：`mastery_probability` 由服务端按配置的估计器从提交的证据计算，宿主无法传入。
- **复习排程**：按节点与卡片计算 FSRS 间隔与可提取度。
- **交付结构**：Domain Grounding 需要来源定位、摘录、关联声明、实际核验与局限；教学包必须把
  canonical Markdown 与其投影配对并包含必需章节，之后才能登记题目。
- **审计性**：每次状态变更都是带 request id 的事件，拒绝也会记录原因。

## 2. 仍由宿主 Agent（及其 LLM）承担的部分

- **学科正确性**：LEAP 校验你提交内容的*结构*，不验证证明是否成立、推导是否正确、来源是否可靠。
  结构通过不等于内容正确，仓库的门禁脚本自己也这样声明。
- **题目质量**：难度、歧义、边界覆盖与干扰项质量由宿主负责，runtime 只记录题目已复核并登记。
- **讲解质量与语言层面的教学法**：策略引擎选择策略与动作，但措辞、例题与图示由宿主生成。
- **开放题评判**：自由文本必须由宿主做语义评审；对 `assessor_scope=host_semantic_review` 的题目
  规则判分会被拒绝，runtime 不会替你产出语义评分。
- **知识图谱设计**：分解质量决定后续所有门禁与估计的前提。`validate_knowledge_dag` 只检查结构
  （环、悬空边、前置顺序），不判断分解在学科上是否合理。

## 3. 本版本的工程限制

- **单机单学员（P0）**：传输为 stdio，`auth_enabled` 为 false，没有学员账号体系、多租户、权限与
  内容审核。面向学校/机构的部署需要这些，LEAP 不提供。
- **每个可插拔缝隙只有一种实现**：六个缝隙都已接通，但默认实现是简化 BKT、加权聚合、规则策略、
  `py-fsrs`、SQLite 与本地产物存储；替代实现是增量的，尚未在生产验证。
- **运维足迹**：宿主需要运行 MCP stdio 进程、SQLite 文件与 YAML 配置。`python -m leap.doctor`
  可自检这些前提，`quickstart` 档位可缩小 Agent 需要面对的工具目录，但进程本身仍需像本地服务一样
  看护。
- **单个教学回合的成本**：粗粒度 API 减少调用次数，但不减少宿主撰写内容所需的 token 成本。

## 4. 目前没有证据支持的说法

直说：框架不应该借用架构的可信度。

- **没有对照实验**：没有公开的、与"只用长提示词"基线的学习效果对比研究，仓库中任何表述都不应被
  当作这类结论。
- **没有规模化真实数据**：示例与课程配方是合成或作者自制的样本，它们证明流程可跑通，不证明教得更好。
- **没有第三方课程评审**：内置学科笔记与数学一章节由仓库自己的脚本做结构核验与来源比对，属于内部
  检查，不是独立评审。
- **没有"某个宿主模型一定能用好这套工具"的证明**：工具选择可靠性取决于宿主 Agent。粗粒度门面层与
  `next_call` 提示把正确顺序显式化，但不会把弱的工具使用者变成强的。

## 5. 如何判断仓库中的一句话

两个问题即可区分"实现主张"与"效果主张"：

1. 如果这句话是错的，哪条命令或测试会失败？（README 给出的校验脚本与 CI 会执行它们。）
2. 这句话描述的是 runtime 的行为，还是模型用它产出的内容质量？

回答不了第一个问题的句子只能当作设计意图；滑入第二个问题范畴的说法不属于本框架的范围——遇到时应当
在文档中更正，而不是复制到宣传文案里。

> [!note]- Reading and verification sequence: LEAP 范围 边界 保证 证据
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

