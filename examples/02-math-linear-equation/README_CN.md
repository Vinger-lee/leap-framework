---
title: 一元一次方程：从等式性质到完整解法
tags:
- leap
- engineering
aliases:
- 一元一次方程：从等式性质到完整解法 guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `linear equations equivalent transformations foundations definitions workflow`
> Extension: `linear equations equivalent transformations failure cases examples comparison`
> Advanced: `linear equations equivalent transformations invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# 一元一次方程：从等式性质到完整解法

本例是一份零依赖中文课程与交互实验。它从未知数、负数和等号讲起，逐行推导 ax+b=c；处理负系数、括号、分母、两边未知数和零系数，最后把结果带回原式及实际情境检查。

- 打开 [交互课程](leap-02-math-linear-equation.html)。桌面浏览器直接打开即可，全部公式、SVG和交互脚本在单文件中。
- 完整复习：[[examples/02-math-linear-equation/knowledge|规范知识笔记]]；在普通Markdown阅读器中可用 [[examples/02-math-linear-equation/knowledge|知识笔记]]。笔记包含网页全部学习段落与解答，并额外解释可逆运算、参数方程、定义域与更多完整例题。
- 延伸迁移：[[examples/04-physics-free-fall/knowledge|自由落体]] 中求时间也要同乘、同除，但多出平方根与物理取值域。

## 建议学习路线

1. 核心25分钟：读前置知识，跟天平图逐步操作，自己解释3x+5=20为何变为3x=15及x=5。
2. 扩展20分钟：先独立解负系数、括号与分母题，再展开对应完整解答。
3. 边界10分钟：把参数计算器的a调为0，分别让b=c、b≠c，看直线重合与平行分离，写出解集。
4. 迁移10分钟：列实际问题方程，给未知量写单位与范围，再检验答案是否可行。

## 可以探索的图示与任务

| 组件 | 学习目标 |
|---|---|
| 天平五步、双边高亮、错误移项比较 | 同步操作、可逆性与代入反证 |
| 参数计算器、SVG数轴、两条直线交点 | 唯一解、无解与所有实数解 |
| 原有排序和q2分步输入 | 按指定两步练习3x+5=20 |
| 新分数题与边界分类题 | 数值检验和解集判断 |
| 分层折叠解答、计价与整数情境 | 过程自查与实际范围 |

核心检索词：`一元一次方程 等式性质 等价变形 两边同减 系数化为1 代入检验`。扩展：`去括号 分配律 去分母 最小公倍数 实际问题 单位`。进阶：`参数方程 系数为零 无解 无穷多解 解集 可逆运算 直线交点`。这些是检索方向，不是未经核验的视频清单。

## 教学与运行边界

未知数允许多次出现，也可在两边出现；合法等价操作并不只有一种顺序。q2针对指定步骤核验。a=0不适用除法求解式，页面显示无解或恒等。数值题只核验提交的数值，不能自动证明纸上推导质量；读过完整解答后应做新的独立自测。

页面保留window.LEAP的hydrate、getInteractionResult、peekOutbox与drainOutbox等接口，原有q2、step1、step2不变。作答产生待宿主处理的MCP调用；demo评分为provisional，本页不自行更新掌握度。新图示探索写入reflection事件，不把探索操作当作已掌握证据。

使用键盘Tab、Enter/Space访问按钮与原生折叠解答，方向键调整滑块。窄屏合为单列，减少动效偏好会关闭过渡。

本目录的runtime.json覆盖原有桥接与评分，以及新逐步图解、高亮、比较、参数边界、分数题与零系数题。验证入口位于scripts/verify_example.py与scripts/verify_example_runtime.py，真实MCP整合夹具仍使用本例q2。

> [!note]- Reading and verification sequence: linear equations equivalent transformations
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/02-math-linear-equation/README]] · [[examples/02-math-linear-equation/knowledge]]
