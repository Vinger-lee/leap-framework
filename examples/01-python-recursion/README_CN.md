---
title: 示例 1 · 编程类：Python 递归入门
tags:
- leap
- engineering
aliases:
- 示例 1 · 编程类：Python 递归入门 guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `Python recursion call stack base case foundations definitions workflow`
> Extension: `Python recursion call stack base case failure cases examples comparison`
> Advanced: `Python recursion call stack base case invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# 示例 1 · 编程类：Python 递归入门

**语言 / Language**：**简体中文** ｜ [[examples/01-python-recursion/README|English]]

- **产出文件名**：`leap-01-python-recursion.html`（放入本目录）
- **主题**：阶乘递归函数讲解与练习
- **node_id**：`py.recursion.factorial` ｜ **unit_tag**：`python-recursion`
- **必含交互组件**：
  1. 递归执行过程动画（调用栈可视化，可单步 / 重置）
  2. 内嵌代码运行器（可编辑 + 运行 + 控制台输出，纯 JS 受控模拟执行）
  3. 三级渐进提示
  4. 拖拽连线题（递归步骤 ↔ 执行阶段）
  5. 代码填空题 + 即时反馈
- **参考 Skill 思路**：LiaScript CodeRunner、LiaScript DragAndDrop Template
- **验收**：代码可编辑运行；调用栈动画清晰展示递归深度；反馈能指出概念错误。

规范见 `../_shared/leap-web-spec.md`，JSON 契约见 `../_shared/interaction-output.schema.json`。

## 学习材料与建议路线

- [直接打开交互课程](leap-01-python-recursion.html)：单文件离线可用，无外部依赖。
- [[examples/01-python-recursion/knowledge|完整知识笔记]]：适合 Obsidian 阅读，覆盖网页全部知识并补充输入验证、证明、更多反例与完整练习解答。
- 顶部资源区给出核心、扩展、进阶的精确检索词，便于按基础选择资料。

从函数参数、局部变量和 `return` 的先修例子开始，再从阶乘定义推导基线、子问题和组合；用纸笔跟踪 `factorial(3)` 的每层参数与返回值后，完成边界预测、步长排错和累加迁移。建议分 35–50 分钟学习；输入约定为非负整数。

## 页面中的实际交互

1. **新增逐行推演器**：输入 0–6，切换 factorial / sum_to；前进、后退、重置同步改变代码行高亮、SVG 栈帧、局部 n、待算式和返回值。
2. **新增分层自测**：0! 与 4! 预测、n−2 最小反例、sum_to 的 0 基线与结果；每次提交记录正确或错误事件，反馈给出具体步骤。
3. **原有 9 步调用栈**：单步、播放、重置，最外层返回后真正清空栈。
4. **代码填空与匹配**：Q1 补关键表达式，Q2 支持拖拽或先点卡片再点槽位。
5. **提示与后置验证**：三级提示逐步展开；完整答案需二次确认，并检验只写 n==1 对输入 0 的问题。
6. **受控运行器**：运行指定递归语法形式，显示每一次模拟调用与返回；输入检查拒绝负数、小数和带文字的值。改 n−1 为 n+1 可观察 120 层的演示上限。

运行器不是完整 Python 解释器：删除基线会被解析器拒绝，完整异常输入检查要在真实 Python 环境运行；运算结果超出 JavaScript 安全整数范围会明确提示。知识笔记分别解释真实 Python 与课堂模拟器的边界。

自由文本自我解释仅记录原文并标记 `host_semantic_review`，等待宿主语义核验；不会凭关键词给分或自动完成。

新自测只追加学习证据，保留已有 `window.LEAP` 桥接、原题评分权重、输出 JSON 和宿主推进契约。按钮可通过 Tab + Enter/空格操作；细节使用原生折叠说明；减少动态效果模式关闭动画而保留状态信息。桌面内容最大宽度 1800px，侧栏 420px，手机布局不横向溢出。

## 验证

本目录的 `leap-01-python-recursion.runtime.json` 声明实际交互与结果断言，包括正确/错误答案、代码行与 SVG 栈变化、边界输入、迁移结果及桥接约束。仓库环境可执行：

```powershell
.venv\quality-runtime\Scripts\python.exe -X utf8 scripts/verify_example.py examples/01-python-recursion/leap-01-python-recursion.html
.venv\quality-runtime\Scripts\python.exe -X utf8 scripts/verify_example_runtime.py examples/01-python-recursion/leap-01-python-recursion.html
```

> [!note]- Reading and verification sequence: Python recursion call stack base case
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/01-python-recursion/README]] · [[examples/01-python-recursion/knowledge]]
