---
title: "A4 打印资料"
tags: ["leap", "printing"]
aliases: ["LEAP print guide", "A4 PDF"]
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> 查询 Playwright Python page.pdf、CSS Paged Media @page 和 CSS Fragmentation break-inside。

Related: [[Knowledge_Index]]

# A4 打印资料

LEAP 为个人学习生成独立的讲义册、题目册和答案解析。课程 HTML 用于交互。
四种打印版式使用可离线打开的 HTML，题目册与答案解析共享题号和版本。

| 版本 | 内容 |
|---|---|
| `combined` | 默认合订册。讲义在前，练习另起一页。 |
| `handout` | 自学讲义，从具体问题起步，配有图解、逐步例题、易错分析和自检。 |
| `workbook` | 题干、配图、选项和答题区。 |
| `answers` | 与题目册同版本的答案和解析，单独导出。 |

## 从交互课程到纸上自学

1. 打开[一元一次方程交互课程](../examples/02-math-linear-equation/leap-02-math-linear-equation.html)，
   用天平观察 `3x + 5 = 20` 如何通过两边同减 5、同除以 3 得到 `x = 5`。
2. 阅读[配图讲义](../print-examples/linear-equations/handout.html)。讲义沿用同一道例题解释每步理由，
   接着讲括号、去分母、零系数与交点，最后用计价与计数情境练习检查实际取值。
3. 独立完成[题目册](../print-examples/linear-equations/workbook.html)的八道新题，再用
   [同版本答案与解析](../print-examples/linear-equations/answers.html)核对。也可以打开
   [合订册](../print-examples/linear-equations/combined.html)一次打印讲义与练习。

下载仓库并保留目录结构后，可以直接用浏览器打开课程 HTML。选择「打印资料」和方向，
点「导出 PDF」会打开相应的独立打印页，并调起浏览器打印。选择 A4 和「另存为 PDF」即可。
仓库自带的离线配套打印稿对应一元一次方程，其余示例可由连接了 LEAP MCP 的宿主 Agent 按需生成。

> [!tip]- 安装与验收
> 安装 `.[print]` 后运行 `python -m playwright install chromium`。
> 如打印中文，请确保渲染机器安装了中文字体，例如 Noto Sans CJK。用实际 PDF 检查字形、配图、页边距和分页。

## 命令行

```sh
pip install -e ".[print]"
python -m playwright install chromium
leap-print print-examples/linear-equations/combined.html
leap-print my-handout.html -o handout.pdf --orientation landscape --margins-mm 12 12 14 12
```

默认 A4 纵向，四边 16 mm。边距顺序是上、右、下、左。
可通过 `--chromium` 或进程环境变量 `LEAP_PRINT_CHROMIUM` 选择已安装的 Chromium。
再次写入同名 PDF 时，显式传 `--overwrite`。自编 HTML 使用 UTF-8，内联 CSS、SVG
或嵌入的 raster 图片，可用静态 MathML 表达公式。导出过程使用隔离的浏览器上下文，
不运行页面脚本，也不加载网络或本地文件资源。网页脚本生成的内容需要先保存成静态 HTML。

## 宿主 Agent 和 MCP

1. 调用 `get_print_materials(session_id, node_id)` 查找已保存版本。默认复用最新打印稿。
   用户要求更新或换题时，通过 `include_source=True` 取得课程 Markdown、教学点和学习证据。
2. 根据讲义重新出题。覆盖核心教学点，用已有作答和薄弱点调整题量、难度与比重。
   无作答证据时按讲义组卷。独立解题，核对条件、边界、干扰项、答案和解析。
3. 调用 `save_print_materials` 保存讲义 HTML 片段和题目。用返回的
   `uncovered_point_ids` 检查覆盖缺口，并逐节核对讲义与课程中的符号、模型和前置知识。
   按需保存新版本，旧版本可由 `material_id` 找回。
4. 调用 `export_print_pdf`。默认将合订册写入 `artifact_root`，返回文件路径。可指定
   `edition`、`orientation`、`margins_mm`，也可传 `include_pdf=True` 取得下载字节。
   对编辑过的 HTML，可保存为新打印稿版本或用命令行直接导出。
5. 打包离线课程时，用 `get_print_materials` 的 `html_directory` 保存四份 HTML。
   给课程页的 `[data-leap-print]` 元素配置四个 `data-print-<edition>` 相对路径。
   打开课程页可离线跳转到独立打印稿，再由浏览器另存为 PDF。

宿主页面桥接沿用 `LEAP.hydrate`、`LEAP.drainOutbox` 和 `LEAP.applyToolResults`。
课程页发出 `export_print_pdf`。如回执为 `needs_authoring`，宿主按回执读取授课资料并完成
上述创作和保存步骤，然后重新导出同一版式，将最终下载回执映射到原 `call_id`。
如果宿主没有接出队和回执，离线发放时使用独立打印 HTML。答案册由用户在课程页主动选择，
也可通过宿主 Agent 按需导出。课程页会为当前页面里最近下载的题目册或合订册使用同版本答案。
保存个人题稿时，记录返回的 `material_id` 和封面版本号。以后补打答案册时，
用该 `material_id` 和 `edition="answers"` 导出原版解析。

`include_source=True` 会把当前会话的学习状态和评估摘要交给宿主。个性化讲义和题稿可能含有个人学习记录，
导出物宜保存在用户本地。仓库中的静态样例使用公开课程内容。

## 自学讲义的排版

先解释要解决的问题和第一次出现的符号，再演示每步操作、原因、常见错误和检验方法。
用单独的练习册检验能否独立做出来。讲义的 HTML 和 PDF 共用一套彩色样式。
现成的样式包括 `lesson-chapter`、`lesson-figure`、`lesson-steps` 以及
`lesson-callout try` 和 `lesson-callout caution`。具体用法见
[一元一次方程的讲义 HTML 片段](../print-examples/linear-equations/handout.fragment)。

## 题目格式

必填 `point_ids`、`kind`、`prompt_html`、`answer_html`。`title` 可为这道题命名，
题目册和答案册显示同一个标题。选择和判断题可提供 `options_html`。每题可用 `answer_area` 指定类型、`height_mm` 和 `lines`，
用 `new_page: true` 另起一页。

- 选择、判断、填空、简答可使用 `choices`、`blank`、`lines` 答题区。
- 计算、推导、证明和综合题默认为 `space`，几何和作图使用 `grid` 或 `axes`。
- 编程题使用 `code`，可设 `line_numbers: true`。实验题使用 `table`，在
  `columns` 填列名及单位，`lines` 指定数据行数。
- 用 `continuations` 提供需要人工指定的续页 HTML 片段。自动分页优先保留整题，
  长答题区和数据表分页后重复题号或表头。任意长的单个 HTML 段落由浏览器分页，
  需要确定续页位置时由作者显式分段。

完整组卷样例见 [lesson.json](../print-examples/linear-equations/lesson.json)。
Runtime 校验结构、版本和教学点关联。配图表达、题目正确性和讲义覆盖由宿主 Agent 复核。
