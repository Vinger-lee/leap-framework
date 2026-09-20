# Example 2 · Mathematics: Linear Equations

**Language**: English ｜ [中文](README_CN.md)

- **Output file**: `leap-02-math-linear-equation.html` (place in this directory)
- **Topic**: Solving linear equations and equivalent transformations
- **node_id**: `math.algebra.linear_equation` · **unit_tag**: `linear-equation`
- **Required interaction components**:
  1. Native MathML formula rendering (KaTeX CDN forbidden)
  2. Interactive parameter calculator (sliders for a/b/c, solution updates live)
  3. Drag-and-order item (order the transformation steps; scored on drop)
  4. Step-by-step solving practice with three-level hints
  5. SVG number-line visualisation
- **Reference approaches**: Interactive math calculator, LiaScript DragAndDrop Template
- **Acceptance**: Formulas render correctly; parameter changes recompute live; drag scoring is accurate.

Structural spec: `../_shared/leap-web-spec.md`. JSON contract: `../_shared/interaction-output.schema.json`.
