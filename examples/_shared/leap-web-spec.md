---
title: LEAP‑V2 网页规范总纲（LEAP Web Spec v2.0）
tags:
- leap
- engineering
aliases:
- LEAP‑V2 网页规范总纲（LEAP Web Spec v2.0） guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP LEAP‑V2 网页规范总纲（LEAP Web Spec v2.0） foundations definitions workflow`
> Extension: `LEAP LEAP‑V2 网页规范总纲（LEAP Web Spec v2.0） failure cases examples comparison`
> Advanced: `LEAP LEAP‑V2 网页规范总纲（LEAP Web Spec v2.0） invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# LEAP‑V2 网页规范总纲（LEAP Web Spec v2.0）

> 本文件是 LEAP‑V2 前端教学网页的**硬性规范权威版**。所有 `examples/` 下的分学科示例、以及后续宿主 Agent 生成的教学网页，都必须遵守本规范。
>
> 配套机器可读契约：`interaction-output.schema.json`。

---

## 1. 单文件、零依赖

1. 每个教学网页是**一个完整 `.html` 单文件**，所有 JS / CSS / SVG / 图形 / 字体样式全部内联。
2. **零外部 CDN、零网络请求、零后端依赖**，双击即可离线运行。
3. 因禁止 CDN，以下三者必须用替代方案：
   - **Tailwind** → 不得引入 CDN；在内联 `<style>` 手写等效 CSS，视觉风格对齐 Tailwind 的克制审美。
   - **KaTeX / MathJax** → 不得引入；公式使用**原生 MathML（`<math>`）**或**内联 SVG** 渲染。
   - **Pyodide 等运行时** → 不得引入；编程示例改用**纯 JS 受控模拟执行引擎**，仅覆盖该题型范围，并在界面注明适用范围。

## 2. 页面三段式结构

| 区块 | 名称 | 职责 |
|---|---|---|
| 第一区 | 教学内容区（Teaching） | 概念讲解、公式 / 语法、示例、≥1 个可视化；须插入 ≥1 次「理解检查」 |
| 第二区 | 交互练习区（Practice） | 承载该学科要求的全部交互组件，全部有即时反馈 |
| 第三区 | Agent 数据输出区（Agent Output） | 固定 `id="leap-interaction-output"`，实时展示符合契约的 JSON |

补充要求：
- 提供全局方法 `window.LEAP.getInteractionResult()`，返回与输出区一致的 JSON 对象。
- 每次交互（提交答案 / 使用提示 / 拖拽判分 / 运行代码）后，输出区自动刷新。
- `events` 数组**只追加，不覆盖**。

## 3. Progressive Answer Disclosure（渐进式答案揭示）

固定三级递进，**不得直接展示答案**：

```text
第 1 级  Guiding Question      引导问题，只给方向
第 2 级  Strategy Hint         策略提示，给思路或关键步骤方向
第 3 级  Partial Worked Example 部分示范，给出前半段
仍无法完成 → Full Answer       完整答案
```

约束：
1. 每级提示必须由学习者**主动点击**展开。
2. 使用后记录 `hint_level`（0 = 未用；1/2/3 = 对应级别；4 = 已展示完整答案）。
3. **展示完整答案 ≠ 任务完成**：必须追加后置验证（同类变式题或简短自我解释），保留独立作答与提示等级。后置活动结束只请求 `check_advance_unit`；guard 允许且 `advance_unit` 实际成功的匹配回执才确认 `completed = true`。
4. 提示文案为引导口吻，不得写成"答案是……"。

对应 LEAP‑V2 文档 §12。

## 4. 多维度反馈与错误类型

1. 必须区分错误类型：`answer_error`（答案错误）、`reasoning_error`（推理错误）、`misconception`（概念误解）。
2. 必须支持部分正确：完全正确 / 部分正确 / 方法正确但计算错误 / 结论正确但依据错误 / 概念正确但表达不完整 / 思路正确但未完成 / 关键步骤错误 / 完全错误。
3. 评分维度包括 `correctness`、`conceptual_understanding`、`reasoning_quality`、`application`、`transfer`、`hint_dependency`、`confidence`、`overall_score`。已观察到的维度使用 0–1；未观察到的维度为 `null` 或按 schema 省略，界面显示“未评估”。客观选择/数值答案不能凭空产生概念、推理、应用、迁移分；自由文本采集原文等待宿主语义审阅。
4. `overall_score` 默认加权：correctness 0.4 / conceptual_understanding 0.3 / reasoning_quality 0.2 / application 0.1；`transfer` 与 `hint_dependency` **不参与聚合**。
5. 反馈文本为中文教学口吻：先肯定正确部分 → 定位错误点 → 给出下一步建议。

对应 LEAP‑V2 文档 §10.3、§10.4、§10.3‑1。

## 5. Agent 数据输出契约

- 输出位置：`<pre id="leap-interaction-output">`（或同 id 的 `readonly textarea`）。
- 结构以 `interaction-output.schema.json` 为准，**字段名不得改动**。
- 顶层字段：`leap_version` / `example_id` / `subject` / `node` / `learner` / `events` / `assessment` / `ui_state` / `outbox`。
- `learner_id`、`session_id` 在示例中保留占位符，由宿主 Agent 注入。
- `created_at` 使用 Unix 秒（`Math.floor(Date.now()/1000)`）。

## 5.1 宿主桥接（Host Bridge）—— 页面必须真的调用接口

> 页面是**参考示例**，必须演示清楚"页面 ↔ LEAP Runtime"的接口，不能是一个自娱自乐的封闭页面。
> 完整契约见 `leap-bridge.md`。

双向接口，缺一不可：

**输入**：`window.LEAP.hydrate(context)` —— 宿主把 `get_teaching_context` 的返回值注入页面。

**输出**：
1. `window.LEAP.getInteractionResult()` —— 契约对象；
2. `window.LEAP.drainOutbox()` —— **待执行的 MCP 调用队列**。

硬性要求：

1. 学习者的每次交互（作答 / 拖拽 / 运行代码 / 反思）都必须**翻译成一条 MCP 调用**入队；
2. `commit_assessment` 调用必须带非空 `raw_answer`（对齐 LEAP‑V2 §22.8）；
3. 页面**不得**自行推算 `mastery_probability`、**不得**自行判定 `evidence_stage` 升级、**不得**把 `mastery_probability` 放进调用入参（对齐 §10.2‑1）；
4. 未调用 `hydrate()` 时保持 `ui_state.mode === "demo"`，掌握度与证据阶段不得本地升级；本地评分标记 `assessment.provisional = true`，界面明确标注为待核验。进入 hosted 也不代表新评分已确认；
5. 调用队列、`ui_state.mode`、`assessment.provisional` 的字段名与取值以 `interaction-output.schema.json` 为准。

6. 出题前宿主须按 [[docs/content-quality|内容质量流程]] 完成来源阅读和逐题复核，通过 `save_assessment_item` 登记题目；自由文本必须由宿主语义评估，不得以关键词存在代替推理正确。
7. `item_completed` 产生 `check_advance_unit`，不能把本地活动完成描述为 Runtime 已批准节点完成。浏览器检查、真实 MCP 联调和学科审校必须分开报告。

## 6. 视觉与可访问性

> **视觉细节以项目作者另行维护的视觉设计规范为权威版 —— 该文档不在本仓库。**
> 本节只保留不可让渡的底线；颜色、字阶、间距、组件尺寸一律以设计理念为准，不得自行发明。

1. 教学柔和风格：浅色暖纸背景、低饱和主色、清晰层级、足够留白。
2. 图形一律使用**内联 SVG 或 Canvas**，不得使用外部图片。
3. 中文字体使用系统字体栈，不引入 webfont。
4. 关键交互元素带 `aria-label`，键盘可达。
5. 自适应：桌面 1280px 与移动 375px 均不错位。
6. **禁止**：渐变背景 / 渐变按钮 / 玻璃拟态 / emoji 图标 / `transition: all`。
7. 必须先内化设计理念（含 `design-references/` 四张参考图）再写代码；提交时附设计理念 §8 视觉自检清单。
8. 冲突裁决：结构以本规范为准，视觉以设计理念为准。

## 7. 长内容分段输出

1. 单页代码过长时主动分 2～3 段输出。
2. 每段均为**完整可拼接片段**，不重复、不遗漏。
3. 每段开头标注：`【这是第 X 段，共 X 段，请全部复制拼接后再保存为 .html 文件】`。
4. 按 HTML 结构自然切分（如：第 1 段到 `</style>`，第 2 段到 `<body>` 中部，第 3 段含剩余结构 + `<script>` + `</html>`），**不得在标签或 JS 函数中间切断**。

---

## 学科交互组件速查

| 学科 | 必含交互组件 | 参考 Skill 思路 |
|---|---|---|
| 编程（Python 递归） | 调用栈动画、代码运行器、三级提示、拖拽连线、代码填空 | LiaScript CodeRunner、DragAndDrop Template |
| 数学（一元一次方程） | MathML 公式、参数计算器、拖拽排序、分步求解、数轴 | 交互式数学计算器、DragAndDrop Template |
| 计算机基础（OSI） | 七层 SVG 示意、拖拽连线、封装动画、选择题 | Canvas 流程图、DragAndDrop Template |
| 物理（自由落体） | MathML 公式、Canvas 模拟、参数滑块、计算填空、h‑t 曲线 | 交互式数学计算器、Canvas 动画 |
| 逻辑（流程图） | 可拖拽节点流程图、补全题、执行动画、三级提示、结果输出 | React Flow / FlowGram、Canvas 流程图 |
| 概率统计 | 条件概率面积图、样本空间切换、频数树、分步贝叶斯、独立性反例 | 标签清晰的 SVG、条件参数与分步控制 |
| 化学 | 原子计数与配平、反应前后粒子图、限量试剂对比、计量单位换算 | 守恒图示、分步配平、模型边界说明 |
| 基础电路 | 串并联结构图、电压电流控制、功率分配、开路与理想短路边界 | 参数 SVG、电路状态高亮、完整原始作答 |

## 永久教学交付政策 3.0

所有学科与学习模式遵循 [[docs/teaching-delivery]]；本节补充网页契约，完整政策通过 `get_teaching_delivery_policy` 获取。每点均包含前置补习、原理与条件、完整步骤、例题与核对、误解修正、边界、比较、梯度练习与迁移；能可视化的内容应有标注图和可控制推演。

先写完整 Obsidian Markdown，再派生页面；头部使用经核验的视频或明确标记的核心/拓展/进阶检索词。调用 `save_teaching_package` 提交双方正文与覆盖记录，接受后才登记题目。包校验只核对结构和记录，不替代来源阅读或内容审校。

1440/1920px 桌面实际内容宽度不少于屏幕的 88%，超宽屏总容器上限 1800px；375px 页面无横向溢出。键盘可操作，动画可暂停/重置并支持减弱动画。行为场景须覆盖错误、边界、揭示、重试和实际判分路径，不能仅证明按钮存在。

> [!note]- Reading and verification sequence: LEAP LEAP‑V2 网页规范总纲（LEAP Web Spec v2.0）
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[docs/teaching-delivery]] · [[docs/teaching-upgrade-plan]]
