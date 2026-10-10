---
title: Examples
tags:
- leap
- engineering
aliases:
- Examples guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP Examples foundations definitions workflow`
> Extension: `LEAP Examples failure cases examples comparison`
> Advanced: `LEAP Examples invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# Examples

**Language**: English ｜ Chinese version: see [[examples/README_CN|../examples/README_CN.md]]

Eight single-file teaching pages. They are **reference implementations**, not the product: each one
shows how a real teaching page talks to the LEAP runtime.

| # | Directory | Subject |
|---|---|---|
| 1 | [`examples/01-python-recursion/`](../examples/01-python-recursion/) | Programming — Python recursion |
| 2 | [`examples/02-math-linear-equation/`](../examples/02-math-linear-equation/) | Mathematics — linear equations |
| 3 | [`examples/03-cs-osi-model/`](../examples/03-cs-osi-model/) | Computer science — OSI model |
| 4 | [`examples/04-physics-free-fall/`](../examples/04-physics-free-fall/) | Physics — free fall |
| 5 | [`examples/05-logic-flowchart/`](../examples/05-logic-flowchart/) | Logic — flowcharts |
| 6 | `examples/06-statistics-probability/` | Statistics — conditional probability |
| 7 | `examples/07-chemistry-stoichiometry/` | Chemistry — stoichiometry |
| 8 | `examples/08-electronics-ohms-law/` | Electronics — Ohm law |

## What every page must do

- **Single file**, zero CDN, zero network requests, zero external images — opens offline.
- **Three zones**: teaching content, interactive practice, agent output.
- Output container `id="leap-interaction-output"` with `window.LEAP.getInteractionResult()`.
- JSON matches [`_shared/interaction-output.schema.json`](../examples/_shared/interaction-output.schema.json)
  exactly; field names unchanged.

## The host bridge

A page that only renders is a closed simulation. Each page demonstrates the real two-way
interface — see [[examples/_shared/leap-bridge|_shared/leap-bridge.md]].

**In** — `LEAP.hydrate(context)` accepts the object returned by `get_teaching_context`:

```js
const ctx = await mcp.call("get_teaching_context", { session_id, node_id });
window.LEAP.hydrate(ctx);
```

**Out** — `LEAP.drainOutbox()` returns the pending MCP calls for the agent to execute:

```js
const calls = window.LEAP.drainOutbox();
for (const call of calls) {
  const result = await mcp.call(call.tool, resolve(call.args));
}
```

Every learner action becomes a queued call (`submit_attempt`, `commit_assessment`,
`record_reflection`). A page never computes `mastery_probability` itself and never sends one in a
call argument — mastery is decided server-side.

Before injection the page runs in `demo` mode: locally derived numbers are flagged
`assessment.provisional = true` and labelled as unconfirmed feedback. Demo mode never advances mastery or evidence stage; hosted mode alone does not confirm a new assessment.

## Verification

Do not check these by eye — the checklist is encoded as executable checks:

```bash
python scripts/verify_example.py --all          # static spec compliance
python scripts/verify_example_runtime.py --all  # headless Chromium + JSON Schema
python scripts/apply_leap_bridge.py --check     # host-bridge completeness
```

`--check` verifies **completeness, not just presence**: a regenerated page can keep the bridge
banner while dropping a required field, which is invisible to a presence check and only surfaces
at runtime. Use `--repair` to restore a dropped part.

The runtime check needs `playwright` and a Chromium build (`--chromium <path>`), and
`--screenshots <dir>` exports full-page captures for visual review.

## Shared specifications

| File | Purpose |
|---|---|
| `_shared/leap-web-spec.md` | Structural requirements: the three zones and the data contract |
| `_shared/leap-bridge.md` | The page ↔ runtime interface |
| `_shared/interaction-output.schema.json` | Machine-readable output contract |
| `_shared/design-references/` | Four visual reference images |

> The visual design system itself is maintained by the project author separately and is not part
> of this repository; every page here follows it.

> [!note]- Reading and verification sequence: LEAP Examples
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README]] · [[README_CN]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]] · [[docs/i18n/README.ru]]
