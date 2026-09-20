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
3. **展示完整答案 ≠ 任务完成**：必须追加后置验证（同类变式题或简短自我解释）才标记 `completed = true`。
4. 提示文案为引导口吻，不得写成"答案是……"。

对应 LEAP‑V2 文档 §12。

## 4. 多维度反馈与错误类型

1. 必须区分错误类型：`answer_error`（答案错误）、`reasoning_error`（推理错误）、`misconception`（概念误解）。
2. 必须支持部分正确：完全正确 / 部分正确 / 方法正确但计算错误 / 结论正确但依据错误 / 概念正确但表达不完整 / 思路正确但未完成 / 关键步骤错误 / 完全错误。
3. 必须输出多维评分（0–1）：`correctness`、`conceptual_understanding`、`reasoning_quality`、`application`、`transfer`、`hint_dependency`、`confidence`、`overall_score`。
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
4. 未调用 `hydrate()` 时保持 `ui_state.mode === "demo"`，本地推算值必须标记 `assessment.provisional = true`，界面明确标注为演示数据；
5. 调用队列、`ui_state.mode`、`assessment.provisional` 的字段名与取值以 `interaction-output.schema.json` 为准。

## 6. 视觉与可访问性

> **视觉细节以仓库根目录的 `../../（作者维护的视觉规范，不在本仓库）` 为权威版。**
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
