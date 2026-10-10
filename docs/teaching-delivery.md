---
title: 永久教学交付规范
tags:
- leap
- engineering
aliases:
- 永久教学交付规范 guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP 永久教学交付规范 foundations definitions workflow`
> Extension: `LEAP 永久教学交付规范 failure cases examples comparison`
> Advanced: `LEAP 永久教学交付规范 invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# 永久教学交付规范

此规范同时约束所有学科、教学模式、宿主生成器和后续产物。Runtime 返回 `teaching_delivery_policy`；`get_teaching_delivery_policy` 提供完整 3.0 规范。会话模式可改变节奏与题量，不能删除前置知识、推理、边界或验证。

## 先读领域资料，再做教学

宿主必须实际读取资料，保存来源、定位、原文节录、版本或访问日期，并先独立完成代表性例题与反例检查。`save_benchmark_report` 只检查证据记录，不会替宿主学习数学，也不能认证虚构摘录。没有对应年份大纲，就只说明实际参考范围。

## 从完整笔记到可交互页面

每一个具体教学点须包含前置知识、原理与条件、至少两步带理由的推导、完整例题、误解修正、边界情况、对比、基础/变式/挑战练习与解析、迁移任务、有效图示或不配图的具体原因。先写完整 Obsidian 笔记，再选择其中的简短内容投影成 HTML。

MD 必须覆盖全部实际 HTML 文本节点，包括折叠解析和图示标注；另外提供真实的扩展推导或额外案例。源码长度、CSS 长度、重复文案、填充字数都不是教学深度。动态生成的提示/反馈和用户输入不在静态解析器里，须通过浏览器和人工审校另行核对。

图示要标明对象、输入、方向、单位、适用条件。分步控件保留中间状态，用户能暂停、前进、后退和重置。缩小运动模式给出静态步骤。PC 容器最大宽 1800px，侧栏 420px；1440/1920px 屏幕内容使用率至少 88%，375px 不出现整页横向溢出。

## 教学包注册与不可绕过的门禁

`save_teaching_package` 接收 `session_id, node_id, subject, markdown, html, manifest` 的实际内容。manifest 的 `teaching_points` 保存每个必需字段；`resources` 保存核验视频或三层关键词；`html_segments` 标明正文，`markdown_extensions` 标明扩展推导，`source_ids` 关联本会话真实阅读记录。可视化 selector 必须匹配实际 HTML id/class。

Runtime 不读取任意宿主路径，也不能在只有路径、标题和“已检查”声明时授予质量通过。成功后再调用 `save_assessment_item`，同节点习题关联已接受的教学包。`save_artifact` 的教学 HTML/MD 必须关联包，并在提供正文时匹配其内容哈希。代码/图表等非教学产物保持独立用途。

## 资源与双向关系

视频须逐项记录实际 URL、标题、发布者、访问日期、定位、核验原文、可访问且相关的结果；来源不确定就使用精确核心词、拓展词、进阶词。关键词同时出现在笔记和页面头部。外部来源链接允许点击，但页面运行不依赖 CDN、外部脚本或联网请求。

内部链接采用 vault 根路径 `[[wikilinks]]`，避免重名 README 的歧义。每一条关系在目标笔记或真实索引中提供反向链接；链接路径必须存在。[[Knowledge_Index]] 是全仓入口，[[docs/subject-knowledge-map]] 组织学科路线，[[docs/mcp-tools]] 从服务端真实注册函数生成。

## 作答与证据闭环

页面逐题保存原始作答和对应 `submit_attempt` call_id。不能借最近一次别题作答提交评分。规则只评明确客观答案；论证、代码说明、概念解释等待宿主语义评阅，不使用关键词命中、长度或包含“因为”等标记作为正确证据。未判断维度为 null，不能填 0 或 1 装作评估过。

`item_completed` 仅表示本地活动结束，产生 `check_advance_unit`；成功检查仍不是完成回执。Runtime 的 `advance_unit` 真正成功后，页面通过对应回执显示已推进。`provisional` 只表示缺少本次评估回执，始终不能授权本地升级 mastery/evidence_stage。`hydrate` 表示最近一次状态快照，不证明实时连接。

> [!example]- 宿主执行的依赖顺序
> 第一个调用是 `submit_attempt`。宿主保存返回的 attempt_id，然后替换同题 commit 的 `{{call_1.attempt_id}}`，调用 `commit_assessment`。成功回执须同时匹配调用 id、作答原文和 attempt_id。之后检查 guard，符合条件才请求 advance；最后刷新上下文。失败保留原请求和错误，不能当作成功清空证据。

## 发布前可复现检查

1. 运行 pytest、工具文档生成一致性、schema 与注册工具一致性。
2. 全仓 Obsidian 路径/元数据/双向关系校验、每个教学包 100% 正文覆盖校验。
3. 浏览器执行每个声明控件路径、正确与错误答案、揭示后验证、参数边界、键盘和窄屏/宽屏布局。
4. 实际 stdio MCP 进程 + 临时 SQLite + Chromium 联调，核对评分只写测试库。
5. 独立审校数学、科学及学科原理；结构门禁通过不能代替语义正确。

Related: [[docs/INTEGRATION]] · [[docs/INTEGRATION_CN]] · [[docs/content-quality]] · [[examples/_shared/leap-bridge]] · [[examples/_shared/leap-web-spec]] · [[docs/teaching-upgrade-plan]]

> [!note]- Reading and verification sequence: LEAP 永久教学交付规范
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[CHANGELOG]] · [[CODE_OF_CONDUCT]] · [[CONTRIBUTING]] · [[Knowledge_Index]] · [[README]] · [[README_CN]] · [[SECURITY]] · [[curricula/math1-2028-ch01/README]] · [[docs/ARCHITECTURE]] · [[docs/ARCHITECTURE_CN]] · [[docs/EXAMPLES]] · [[docs/INTEGRATION]] · [[docs/INTEGRATION_CN]] · [[docs/LOCALIZATION]] · [[docs/LOCALIZATION_CN]] · [[docs/content-quality]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]] · [[docs/i18n/README.ru]] · [[docs/mcp-tools]] · [[docs/quality-audit-2026-10-10]] · [[docs/subject-knowledge-map]] · [[docs/subject-notes/biology]] · [[docs/subject-notes/chemistry]] · [[docs/subject-notes/economics]] · [[docs/subject-notes/electronics]] · [[docs/subject-notes/language]] · [[docs/teaching-upgrade-plan]] · [[examples/01-python-recursion/README]] · [[examples/01-python-recursion/README_CN]] · [[examples/01-python-recursion/knowledge]] · [[examples/02-math-linear-equation/README]] · [[examples/02-math-linear-equation/README_CN]] · [[examples/02-math-linear-equation/knowledge]] · [[examples/03-cs-osi-model/README]] · [[examples/03-cs-osi-model/README_CN]] · [[examples/03-cs-osi-model/knowledge]] · [[examples/04-physics-free-fall/README]] · [[examples/04-physics-free-fall/README_CN]] · [[examples/04-physics-free-fall/knowledge]] · [[examples/05-logic-flowchart/README]] · [[examples/05-logic-flowchart/README_CN]] · [[examples/05-logic-flowchart/knowledge]] · [[examples/06-statistics-probability/README]] · [[examples/06-statistics-probability/README_CN]] · [[examples/06-statistics-probability/knowledge]] · [[examples/07-chemistry-stoichiometry/README]] · [[examples/07-chemistry-stoichiometry/README_CN]] · [[examples/07-chemistry-stoichiometry/knowledge]] · [[examples/07-chemistry-stoichiometry/sources]] · [[examples/08-electronics-ohms-law/README]] · [[examples/08-electronics-ohms-law/README_CN]] · [[examples/08-electronics-ohms-law/knowledge]] · [[examples/README]] · [[examples/README_CN]] · [[examples/_shared/leap-bridge]] · [[examples/_shared/leap-web-spec]]
