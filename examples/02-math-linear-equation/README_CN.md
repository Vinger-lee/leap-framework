# 示例 2 · 数学类：一元一次方程

**语言 / Language**：**简体中文** ｜ [English](README.md)

- **产出文件名**：`leap-02-math-linear-equation.html`（放入本目录）
- **主题**：一元一次方程的解法与等价变形
- **node_id**：`math.algebra.linear_equation` ｜ **unit_tag**：`linear-equation`
- **必含交互组件**：
  1. 原生 MathML 公式渲染（禁止 KaTeX CDN）
  2. 交互式参数计算器（滑块调 a/b/c，实时看解变化）
  3. 拖拽排序题（方程变形步骤排序，松手即判分）
  4. 分步求解练习 + 三级提示
  5. SVG 数轴可视化
- **参考 Skill 思路**：交互式数学计算器、LiaScript DragAndDrop Template
- **验收**：公式渲染正确；参数修改实时计算；拖拽判分准确。

规范见 `../_shared/leap-web-spec.md`，JSON 契约见 `../_shared/interaction-output.schema.json`。
