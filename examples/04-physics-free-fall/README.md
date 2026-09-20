# Example 4 · Physics: Free Fall

**Language**: English ｜ [中文](README_CN.md)

- **Output file**: `leap-04-physics-free-fall.html` (place in this directory)
- **Topic**: Free-fall formulas and displacement simulation
- **node_id**: `physics.mechanics.free_fall` · **unit_tag**: `free-fall`
- **Required interaction components**:
  1. Native MathML formula rendering (h = ½gt², v = gt)
  2. Canvas physics simulation (falling ball + ground + height scale)
  3. Parameter sliders (initial height h, gravity g — updates live)
  4. Calculation completion with feedback
  5. Live displacement–time (h‑t) chart synced with the animation
- **Reference approaches**: Interactive calculator, Canvas animation (requestAnimationFrame)
- **Acceptance**: Simulation is smooth; parameter changes take effect live; chart and values stay in sync.

Structural spec: `../_shared/leap-web-spec.md`. JSON contract: `../_shared/interaction-output.schema.json`.
