---
title: 化学计量示例内容依据与阅读记录
tags:
- leap/sources
- chemistry/stoichiometry
aliases:
- Stoichiometry Source Review
---

> [!info] 学习资源
> 核心：`化学方程式 配平 原子守恒 mol 摩尔质量`。
> 拓展：`限制反应物 理论产量 实际产量 百分产率`。
> 进阶：`OpenStax Chemistry 2e 4.4 reaction yields`；`BIPM mole Avogadro constant`。
> 此处关键词供继续学习；下表记录实际读取的标准与教材，不作视频推荐。

# 化学计量内容依据与阅读记录

本示例编写时于2026-10-10实际读取以下公开权威资料；页名、链接与校准范围如下。它们是文字教材/标准，不是未核验视频推荐。

| 来源 | 本次读取的内容 | 对本课的约束 |
|---|---|---|
| [BIPM：SI base unit — mole](https://www.bipm.org/en/si-base-units/mole) | mol是物质的量单位；1mol精确含6.02214076×10²³指定基本实体，实体可为原子、分子、离子等；常数单位mol⁻¹ | 区分1mol H₂分子与2mol H原子；NA的数值精确，课堂近似摩尔质量不是精确自然常数 |
| [OpenStax Chemistry 2e §3.1 Formula Mass and the Mole Concept](https://openstax.org/books/chemistry-2e/pages/3-1-formula-mass-and-the-mole-concept) | 分子/式量、mol与摩尔质量；同一mol粒子数相同、质量不同；g/mol含义 | n=m/M与质量换算先修，不能把系数比直接当克数比 |
| [OpenStax Chemistry 2e §4.1 Writing and Balancing Chemical Equations](https://openstax.org/books/chemistry-2e/pages/4-1-writing-and-balancing-chemical-equations) | 按每种元素原子守恒核对；原子数=系数×下标；可改系数，不可改下标，因为下标定义物质身份 | 2H₂+O₂→2H₂O的配平；4:2:4守恒但非最简；不能把H₂O变H₂O₂来“配平” |
| [OpenStax Chemistry 2e §4.4 Reaction Yields](https://openstax.org/books/chemistry-2e/pages/4-4-reaction-yields) | 限制反应物、化学计量量、理论产量、实际产量与百分产率；实际量受副反应、不完全反应、回收损失等影响 | 比较n/系数；产物与过量剩余；理论不等于必然实得，零理论产量百分比无定义 |

教材的水示例包含水分解方向；本课采用反向写法讨论水生成，原子配平与计量比例对应同一守恒关系，不据此推断反应机理或实验条件。计算使用教学给定M(H₂)=2.00、M(O₂)=32.0、M(H₂O)=18.0 g/mol，与H≈1、O≈16统一；网页和题目均明确这个假设。

## 逐题复核

| 题目 | 明确答案 / 评估边界 | 复核 |
|---|---|---|
| CP系数含义 | 指定粒子数或mol比例；质量要乘各自M | 2mol/1mol/2mol对应4g/32g/36g |
| Q1配平 | 最简2:1:2；倍数守恒给部分分 | H4=4、O2=2；4:2:4约分 |
| Q2默认限制物 | O₂；水36g；H₂剩2g | n3/1，份数1.5/1；38=36+2 |
| Q3mol/质量比 | mol2:1:2，质量1:8:9 | 4:32:36；不改下标 |
| Q4解释 | g→mol→n/系数，理想假设与实际边界 | 仅保存原文，宿主语义评估，无关键词分数 |
| 新变式 | H₂限制；水36g；O₂剩32g | n2/2，份数1/2；68=36+32 |

## 模型边界

原子小球是整数计数示意，不是碰撞/键断裂机理。宏观mol连续量不向下取整。网页不模拟平衡、速率、温度、压力、点火、能量或实验操作。固定方程和理想完全转化/回收假设下计算理论量，实际应用需要相应化学与实验信息。

相关：[[examples/07-chemistry-stoichiometry/knowledge|完整知识稿]] · [[examples/07-chemistry-stoichiometry/README_CN|使用说明]] · [[docs/content-quality|内容质量流程]]。

> [!note]- 来源与验证的区别
> 来源阅读校准定义和模型边界；独立算术与浏览器场景核对给定题目。两者都不能由“引用了链接”代替，也不能据教学配平推断现实反应条件或实验安全。

English guide: [[examples/07-chemistry-stoichiometry/README]]。

Related: [[Knowledge_Index]]


Related: [[docs/teaching-delivery]]

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/07-chemistry-stoichiometry/README]] · [[examples/07-chemistry-stoichiometry/README_CN]] · [[examples/07-chemistry-stoichiometry/knowledge]]
