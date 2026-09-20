# 示例 5 · 逻辑类：流程图基础

**语言 / Language**：**简体中文** ｜ [English](README.md)

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
