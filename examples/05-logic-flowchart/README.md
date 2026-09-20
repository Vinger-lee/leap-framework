# Example 5 · Logic: Flowchart Basics

**Language**: English ｜ [中文](README_CN.md)

- **Output file**: `leap-05-logic-flowchart.html` (place in this directory)
- **Topic**: The three basic control structures: sequence, branch, loop
- **node_id**: `logic.control_flow.basics` · **unit_tag**: `flowchart-basics`
- **Required interaction components**:
  1. Draggable-node flowchart (start / process / decision / end, nodes move with their edges)
  2. Flowchart completion item (fill in a missing node or decision condition)
  3. Execution animation (highlights the current node, shows the branch taken)
  4. Three-level progressive hints
  5. Logic result output (given input → result, compared with the learner's prediction)
- **Reference approaches**: React Flow / FlowGram (node drag and bezier-edge interaction), Canvas flow diagrams
- **Acceptance**: Nodes are draggable; the execution animation is clear; logical decisions are correct.

Structural spec: `../_shared/leap-web-spec.md`. JSON contract: `../_shared/interaction-output.schema.json`.
