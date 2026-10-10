---
title: 条件概率与基率示例使用说明
tags:
- leap/examples
- statistics/probability
aliases:
- 条件概率示例说明
---

> [!info] 学习资源
> 核心：`conditional probability independence Bayes definitions beginner`
> 拓展：`conditional probability independence Bayes examples conditions`
> 进阶：`conditional probability independence Bayes proof transfer`

# 示例 6 · 条件概率、基率与独立性

语言：简体中文 · [[examples/06-statistics-probability/README|English guide]]

直接打开 `leap-06-statistics-probability.html`，离线可运行，不需要服务器、构建或外部资源。MathML公式、SVG概率树和条件频数条都在文件内；完整正文、练习、解答与推导见 [[examples/06-statistics-probability/knowledge|知识稿]]。

建议35–50分钟，先修是分数、百分比、交集与补集。先读条件范围 → 看四格表 → 切换阳性/病人/全体/阴性条件 → 六步推导 → 改基率 → 看独立与空组 → 固定离散题 → 语义解释。顶部核心/拓展/进阶关键词可复制检索，不声称核验了推荐视频。

默认假想模型：10,000人、1%基率、90%敏感度、9%假阳性率；真阳性90、假阴性10、假阳性891、真阴性9009。阳性后有病概率90/981≈9.17%，病人阳性比例90/100=90%。假阳性率与特异度都以无病者为条件；数字是模型频数。跨人群比较固定检测参数是明确假设，不能直接用于个体诊断。

交互包括：

- 三个0–100整数百分比滑块，同步更新2×2表、树、条件条形和概率。
- 四种条件范围高亮，明确切换分母。
- 1%/10%基率、独立模型、零阳性预设。
- 六步频数推导，可前进、倒退与归零。
- 零条件显示“无定义”，0%/100%基率空分支单独说明。
- 三项整数客观题、独立题与零分母题；保存重试、部分计分。
- 解释题完整原文采集，宿主语义审阅，页面不按关键词判分。
- 主动递进提示；完整答案二次确认后仍须做新变式。

宿主接口为 `window.LEAP.hydrate/getInteractionResult/peekOutbox/drainOutbox`；队列按钮只预览。新评估保持 `provisional`，掌握度与证据阶段来自Runtime；客观验证结束只请求 `check_advance_unit`。标识：`stats.probability.conditional` / `statistics` / `conditional-probability`。滑块探索不计为已作答证据，提交才保存答案。

`leap-06-statistics-probability.runtime.json`覆盖所有数值/预设、滑块、条件方向、同步图形、独立与退化条件、分步控制、部分分和重试、语义采集、答案确认、后置验证及队列/JSON。仓库根目录执行：

```powershell
.venv/quality-runtime/Scripts/python.exe scripts/verify_example.py examples/06-statistics-probability/leap-06-statistics-probability.html
.venv/quality-runtime/Scripts/python.exe scripts/verify_example_runtime.py examples/06-statistics-probability/leap-06-statistics-probability.html --chromium <path-to-chromium>
```

浏览器检查不等于真实MCP联调或独立学科审校。更多解答见 [[examples/06-statistics-probability/knowledge#十、完整练习、提示与解答|练习知识稿]]，流程见 [[docs/content-quality|内容质量流程]]。返回 [[examples/README_CN|示例索引]]。

> [!note]- 复核记录
> 逐项核对条件、原始输入、推导和回执；使用新输入完成迁移，不能把答案揭示作为掌握证据。


Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/06-statistics-probability/README]] · [[examples/06-statistics-probability/knowledge]]
