---
title: 示例 5 · 逻辑类：流程图基础
tags:
- leap
- engineering
aliases:
- 示例 5 · 逻辑类：流程图基础 guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `flowchart conditions branches execution trace foundations definitions workflow`
> Extension: `flowchart conditions branches execution trace failure cases examples comparison`
> Advanced: `flowchart conditions branches execution trace invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# 示例 5 · 逻辑类：流程图基础

**语言 / Language**：**简体中文** ｜ [[examples/05-logic-flowchart/README|English]]

- **产出文件名**：`leap-05-logic-flowchart.html`（放入本目录）
- **主题**：顺序、分支、循环三种基本控制结构
- **node_id**：`logic.control_flow.basics` ｜ **unit_tag**：`flowchart-basics`
- **必含交互组件**：
  1. 可拖拽节点流程图（开始 / 处理 / 判断 / 结束，节点可拖动 + 连线跟随）
  2. 流程图补全题（补缺失节点或判断条件）
  3. 执行流程动画（高亮当前执行节点，含分支走向）
  4. 三级渐进提示
  5. 逻辑结果输出（给定输入 → 执行结果，与学习者预测对比）
- **参考 Skill 思路**：React Flow / FlowGram（节点拖拽与贝塞尔连线交互模型）、纯 HTML Canvas 流程图
- **验收**：节点可拖拽；执行动画清晰；逻辑判断正确。

规范见 `../_shared/leap-web-spec.md`，JSON 契约见 `../_shared/interaction-output.schema.json`。

## 学习材料与建议路线

- [直接打开交互课程](leap-05-logic-flowchart.html)：单文件离线可用，无外部依赖。
- [[examples/05-logic-flowchart/knowledge|完整知识笔记]]：适合 Obsidian 阅读，覆盖全部网页教学并补充不变式证明、路径覆盖、更多流程设计题与完整解答。
- 顶部资源区提供核心、扩展、进阶的精确检索词。

建议用 35–50 分钟分段学习：变量赋值与真假条件 → 顺序状态表 → 奇偶判断两条完整路径 → 1 到 n 的累加循环 → 边界、错误与迁移。输入域须先明确；奇偶判断采用整数，累加采用非负整数。

## 页面中的实际交互

1. **新增循环逐步演示**：n=0–5，上一/下一步与重置同步改变 SVG 当前节点、箭头、i/s/输出和历史表；正确循环结束前保留最后一次假判断。
2. **遗漏更新实验**：n≥1 时 i 保持 1，展示三轮后说明“演示暂停不是算法结束”；n=0 则第一次判断为假，循环体零次。
3. **新增分层自测**：0 的奇偶分支、n=3 的 s/i/判断次数、连乘初值和 n=0 结果；错误反馈指出具体判断或更新步骤，答题事件只追加。
4. **原有自由图编辑器**：鼠标移动节点与端口连线；键盘 Tab 聚焦、方向键移动、Enter 或连线模式按钮完成连线，线随节点移动。
5. **流程图补全题**：条件写在菱形，是分支放输出偶数，否分支放输出奇数；支持拖拽或点选源卡再点槽位。
6. **执行与预测**：先填预测，再单步到判断。错误分支会留在判断框并解释；只有选择正确分支后才能走到结束，真实输出由输入确定。
7. **提示与后置解释**：三级提示依次展开，完整答案需要二次确认；保留原有评分、事件、宿主桥接与输出 JSON 契约。

SVG 都有可缩放的 viewBox；手机无横向溢出。原生按钮、输入与折叠说明可用键盘操作；减少动态效果时关闭过渡并保留文字状态。桌面内容最大宽度 1800px，侧栏 420px。

自由文本后置解释保留原文并标记 `host_semantic_review`，等待宿主语义核验；文字提交不代表解释正确或任务已完成。

## 验证

`leap-05-logic-flowchart.runtime.json` 声明实际场景与断言：SVG 节点和边高亮、n=0/3 循环结果、漏更新暂停、奇偶正确/错误分支、边界输入、流程图补全及桥接约束。仓库环境可执行：

```powershell
.venv\quality-runtime\Scripts\python.exe -X utf8 scripts/verify_example.py examples/05-logic-flowchart/leap-05-logic-flowchart.html
.venv\quality-runtime\Scripts\python.exe -X utf8 scripts/verify_example_runtime.py examples/05-logic-flowchart/leap-05-logic-flowchart.html
```

> [!note]- Reading and verification sequence: flowchart conditions branches execution trace
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/05-logic-flowchart/README]] · [[examples/05-logic-flowchart/knowledge]]
