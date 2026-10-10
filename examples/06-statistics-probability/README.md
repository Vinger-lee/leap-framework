---
title: Conditional Probability Example — English Guide
tags:
- leap/examples
- statistics/probability
aliases:
- Probability Example Guide
---

> [!info] 学习资源
> 核心：`conditional probability independence Bayes definitions beginner`
> 拓展：`conditional probability independence Bayes examples conditions`
> 进阶：`conditional probability independence Bayes proof transfer`

# Example 6 · Conditional Probability, Base Rates and Independence

Language: English · [[examples/06-statistics-probability/README_CN|中文说明]]

Open `leap-06-statistics-probability.html` directly in a browser. It is a complete offline page with inline CSS, JavaScript, MathML and SVG. Teaching text is in Chinese. The canonical [[examples/06-statistics-probability/knowledge|knowledge manuscript]] includes all teaching, tasks, hints and solutions, plus derivations and further examples.

Allow 35–50 minutes. Prerequisites are fractions, percentages, intersections and complements. Identify the condition's denominator, then derive conditional probability, total probability and Bayes' rule. Distinguish sensitivity, specificity, false-positive rate and positive predictive value; explain independence, mutual exclusion and zero denominators.

The default model has 10,000 people, a 1% disease base rate, 90% sensitivity and a 9% false-positive rate: TP90, FN10, FP891, TN9009. Thus `P(A|B)=90/981=10/109≈9.17%`, while `P(B|A)=90/100=90%`. Integer-percent sliders update the full 2×2 table, probability tree, conditional frequency strip and values together. Presets compare a 10% base rate, independent results and a zero-positive group. Empty condition groups display “undefined.” Counts are model frequencies, not observed medical records.

Practice uses fixed data independent of sliders: three exact integer answers, independence and zero-denominator choices, one explanation collected for semantic review, and a new objective task after revealing solutions. Every retry retains its raw answer. Explanations never receive keyword-generated scores. Solutions use L1/L2/L3 hints followed by a confirmed L4 answer.

`window.LEAP` exposes hydration, the interaction result and outbox preview/drain APIs. New local assessments remain provisional; Runtime supplies mastery and evidence stages. Local verification requests `check_advance_unit`. Identifiers: `stats.probability.conditional` / `statistics` / `conditional-probability`.

Browser scenarios cover arithmetic, all controls/presets, conditional direction, degenerate probabilities, independent/zero-positive models, partial credit, retries, semantic collection, answer confirmation, verification and queue behavior. Run from the repository root:

```powershell
.venv/quality-runtime/Scripts/python.exe scripts/verify_example.py examples/06-statistics-probability/leap-06-statistics-probability.html
.venv/quality-runtime/Scripts/python.exe scripts/verify_example_runtime.py examples/06-statistics-probability/leap-06-statistics-probability.html --chromium <path-to-chromium>
```

Browser checks establish behavior and contract validity, not actual MCP integration or domain review. See [[examples/README|the example index]] and [[docs/content-quality|the content quality workflow]].

> [!note]- 复核记录
> 逐项核对条件、原始输入、推导和回执；使用新输入完成迁移，不能把答案揭示作为掌握证据。


Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/06-statistics-probability/README_CN]] · [[examples/06-statistics-probability/knowledge]]
