---
title: 'Example 5 · Logic: Flowchart Basics'
tags:
- leap
- engineering
aliases:
- 'Example 5 · Logic: Flowchart Basics guide'
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `flowchart conditions branches execution trace foundations definitions workflow`
> Extension: `flowchart conditions branches execution trace failure cases examples comparison`
> Advanced: `flowchart conditions branches execution trace invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# Example 5 · Logic: Flowchart Basics

**Language**: English ｜ [[examples/05-logic-flowchart/README_CN|中文]]

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

> [!note]- Reading and verification sequence: flowchart conditions branches execution trace
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/05-logic-flowchart/README_CN]]
