# 示例 4 · 物理类：自由落体运动

- **产出文件名**：`leap-04-physics-free-fall.html`（放入本目录）
- **主题**：自由落体公式与位移模拟
- **node_id**：`physics.mechanics.free_fall` ｜ **unit_tag**：`free-fall`
- **必含交互组件**：
  1. 原生 MathML 公式渲染（h = ½gt²、v = gt）
  2. Canvas 物理模拟（小球下落动画 + 地面 + 高度标尺）
  3. 参数滑块（调整初始高度 h、重力加速度 g，实时更新）
  4. 计算填空题 + 反馈
  5. 位移–时间（h‑t）图实时绘制，与动画同步
- **参考 Skill 思路**：交互式数学计算器、Canvas 动画（requestAnimationFrame 逐帧）
- **验收**：模拟流畅；参数改变实时生效；图像与数值同步。

规范见 `../_shared/leap-web-spec.md`，JSON 契约见 `../_shared/interaction-output.schema.json`。
