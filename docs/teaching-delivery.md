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

## 图解教学：Anatomy 创作方式

图解用来解释结构、机制、过程、数据与反例。一个教学点可组合剖面/拆解图、因果图、带单位的数据图和静态分镜；数量取决于要解释的问题。先写真实对象与概念的对应关系，再设计部件、相互遮挡、图例与控件。物理实验可画成可拆解实验台；编程用真实状态与执行轨迹，电路用连接与电流路径，数学用几何变换与数量关系，化学用粒子和守恒。不为了追求立体效果编造机构或科学事实。

作者参考 [Anatomy skill](https://github.com/wheresryan22/anatomy)，固定参考版本 `1482e8469b0a9e0d8cc18ea2740a01423d29ae80`（MIT）。它是可选的创作工具。交付仍是离线内联 SVG/Canvas/HTML，框架运行时不依赖该技能或其 JavaScript kit。自由落体示例的几何为项目原创，构建脚本可重现图形。

每个会动的部件、图中曲线与读数必须由同一个领域模型驱动。说明哪些量按比例绘制、哪些只是示意、哪些数据来自计算。默认静止，主动播放，可暂停、后退、前进或拖动时间并重置；控件有键盘操作和焦点状态。离屏、隐藏标签页时暂停；减少动态效果时保留静态帧与数值探索。连续读数不逐帧向屏幕阅读器播报。

新建或修改的图解教学包采用 `visual_contract.profile: anatomy.v1`。旧包未声明此字段时继续兼容。契约示例：

```json
{
  "visual_contract": {
    "profile": "anatomy.v1",
    "figures": [{
      "id": "free-fall-rig",
      "role": "mechanism",
      "selector": "#fallRigFigure",
      "caption": "自由落体实验塔：看清部件，再追踪运动",
      "labels": ["释放头", "光门", "承接盘"],
      "static_frame": "#fallRig",
      "animated": true,
      "model_binding": {
        "source": "同一运动状态驱动小球位置与读数。",
        "quantities": [{"name": "elapsed time", "unit": "s", "selector": "#rigElapsed"}]
      },
      "controls": {"play_pause": "#btnPlay", "reset": "#btnReset", "scrub": "#fallScrub"},
      "states": ["释放：位移和速率为零。", "碰地前：位移等于初始高度。"]
    }]
  }
}
```

所有 selector 指向唯一实际 `#id`。静态帧必须是 SVG、图片或表格；动画另需共享模型来源、输出量与单位、播放/暂停、重置，以及可逆步骤、拖动或参数控件之一。标题、图例在 HTML 与规范笔记中都有解释，模型与状态说明保存在笔记中。Runtime 只验证结构与说明记录；它不执行宿主代码，也不判断 SVG 画得是否正确、控件是否真正联动或公式是否真实。

浏览器检查各观察方式、开始/中间/结束、前进/后退/重置、暂停后不再变化、键盘、无 JavaScript 静态可读、减少动态效果，以及 1440/1920/375px 布局。放大到 4 倍检查机构和对象的遮挡、连接、刻度与标签。针对已知参数独立计算，然后同时核对图形位置、曲线、表针和读数，不能只断言元素存在。完整实现见 [[examples/04-physics-free-fall/knowledge]] 与其交互页面；可运行 `build_figure.py --check` 和对应的浏览器场景。

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

[[CHANGELOG]] · [[CODE_OF_CONDUCT]] · [[CONTRIBUTING]] · [[Knowledge_Index]] · [[README]] · [[README_CN]] · [[SECURITY]] · [[docs/ARCHITECTURE]] · [[docs/ARCHITECTURE_CN]] · [[docs/EXAMPLES]] · [[docs/INTEGRATION]] · [[docs/INTEGRATION_CN]] · [[docs/LOCALIZATION]] · [[docs/LOCALIZATION_CN]] · [[docs/content-quality]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]] · [[docs/i18n/README.ru]] · [[docs/mcp-tools]] · [[docs/quality-audit-2026-10-10]] · [[docs/subject-knowledge-map]] · [[docs/subject-notes/biology]] · [[docs/subject-notes/chemistry]] · [[docs/subject-notes/economics]] · [[docs/subject-notes/electronics]] · [[docs/subject-notes/language]] · [[docs/teaching-upgrade-plan]] · [[examples/01-python-recursion/README]] · [[examples/01-python-recursion/README_CN]] · [[examples/01-python-recursion/knowledge]] · [[examples/02-math-linear-equation/README]] · [[examples/02-math-linear-equation/README_CN]] · [[examples/02-math-linear-equation/knowledge]] · [[examples/03-cs-osi-model/README]] · [[examples/03-cs-osi-model/README_CN]] · [[examples/03-cs-osi-model/knowledge]] · [[examples/04-physics-free-fall/README]] · [[examples/04-physics-free-fall/README_CN]] · [[examples/04-physics-free-fall/knowledge]] · [[examples/05-logic-flowchart/README]] · [[examples/05-logic-flowchart/README_CN]] · [[examples/05-logic-flowchart/knowledge]] · [[examples/06-statistics-probability/README]] · [[examples/06-statistics-probability/README_CN]] · [[examples/06-statistics-probability/knowledge]] · [[examples/07-chemistry-stoichiometry/README]] · [[examples/07-chemistry-stoichiometry/README_CN]] · [[examples/07-chemistry-stoichiometry/knowledge]] · [[examples/07-chemistry-stoichiometry/sources]] · [[examples/08-electronics-ohms-law/README]] · [[examples/08-electronics-ohms-law/README_CN]] · [[examples/08-electronics-ohms-law/knowledge]] · [[examples/README]] · [[examples/README_CN]] · [[examples/_shared/leap-bridge]] · [[examples/_shared/leap-web-spec]]
