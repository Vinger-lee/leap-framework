---
title: 理想自由落体：从条件与图像到完整计算
tags:
- leap
- engineering
aliases:
- 理想自由落体：从条件与图像到完整计算 guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `free fall reference axis units motion foundations definitions workflow`
> Extension: `free fall reference axis units motion failure cases examples comparison`
> Advanced: `free fall reference axis units motion invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# 理想自由落体：从条件与图像到完整计算

本例从速度、加速度、平方与平方根讲起，用参考轴和v–t三角形面积逐行推导理想自由落体公式，再检验落地时间、速率、等时段距离、质量结论与模型边界。

- 打开 [交互课程](leap-04-physics-free-fall.html)。单文件包含SVG、Canvas、原生MathML与脚本，无需联网依赖。
- 完整复习：[[examples/04-physics-free-fall/knowledge|规范知识笔记]]；普通Markdown阅读器可打开 [[examples/04-physics-free-fall/knowledge|知识笔记]]。它完整包含网页教学及所有折叠解答，还补充精确符号、单位、误差、区间运动、初速度非零与空气阻力的解释。
- 代数基础：[[examples/02-math-linear-equation/knowledge|等式性质与方程]]。

## 建议学习路线

1. 核心30分钟：分清H、累计位移s与距地高度z；选择坐标轴，跟公式推导及速度图面积。
2. 实验10分钟：设置H与g，用时间滑块、单步或播放观察。切换参考轴，只改符号，不改真实位置与速率。
3. 扩展20分钟：独立解落地、反求高度、最后一秒、倍率迁移题，然后展开完整解答。
4. 边界10分钟：讨论H=0、g=0、初速度非零、空气阻力与碰撞；说明公式能用到哪一刻。

## 图示与学习目标

| 组件 | 学习目标 |
|---|---|
| 参考轴SVG、正负速度读数 | 坐标原点、方向、速率与速度 |
| v–t SVG面积、六步推导、高亮及错误比较 | ½的来源、斜率、面积与选根 |
| 原有Canvas落球与s–t图、时间滑块 | 同一参数与时刻联动，不靠动画也能探索 |
| 每秒位移5/15/25m的SVG | 累计值与区间值、1:3:5条件 |
| 真空/空气的作用示意 | 质量结论的适用条件，空气图不做阻力数值预测 |
| 原有Q1与新分层练习 | 数值、方向、单位与边界核验 |

核心检索词：`自由落体 初速度为零 重力加速度 匀加速 速度时间图像面积`。扩展：`落地时间 速度位移关系 竖直坐标轴 SI单位 最后一秒位移`。进阶：`真空落体 质量与加速度 空气阻力 终端速度 重力随高度变化 初速度非零`。没有列未经核验的视频推荐。

## 物理与运行边界

默认H≥0、g>0、v₀=0、只受重力、g近似恒定，计算到首次碰地前。g是正的大小，带方向的a可为−g；H与s不能混用。H=0为初始落地边界，g=0且H>0、v₀=0时不会自行落地。空气按钮只说明阻力作用，无阻力系数与数值轨迹。模拟器默认H=50m，固定Q1为H=45m，做题必须读题。

数值输入采用完整字段核验；时间允许纯数或s/秒，速率允许纯数或m/s，错误单位与额外文本不能靠提取其中数字过关。原有变式仍是H=80m、g=10，对应4s与40m/s。数值正确不自动证明推导与概念完整，应完成独立解释。

window.LEAP原有hydrate、getInteractionResult及outbox接口保留。demo作答是provisional，掌握度由宿主Runtime注入。新探索写入reflection事件，新题作答保留原始答案与待提交评分。

用Tab进入按钮与折叠解答，Enter/Space执行，方向键调整滑块。减少动效时播放改为单步，数值探索仍完整可用；控件获得焦点时保留原生键盘行为。

runtime.json覆盖正确/错误/部分正确评分、原始答案关联、方向切换、图解控制、质量条件、时间滑块、所有原有模拟控制及单位错误。验证入口在scripts/verify_example.py与scripts/verify_example_runtime.py。

> [!note]- Reading and verification sequence: free fall reference axis units motion
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/04-physics-free-fall/README]] · [[examples/04-physics-free-fall/knowledge]]
