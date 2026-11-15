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

**Language**: English ｜ [中文示例索引](../examples/README_CN.md)

Eight single-file teaching pages. They are **reference implementations**, not the product: each one
shows how a real teaching page talks to the LEAP runtime.

| # | Directory | Subject |
|---|---|---|
| 1 | [`examples/01-python-recursion/`](../examples/01-python-recursion/) | Programming — Python recursion |
| 2 | [`examples/02-math-linear-equation/`](../examples/02-math-linear-equation/) | Mathematics — linear equations |
| 3 | [`examples/03-cs-osi-model/`](../examples/03-cs-osi-model/) | Computer science — OSI model |
| 4 | [`examples/04-physics-free-fall/`](../examples/04-physics-free-fall/) | Physics — free fall |
| 5 | [`examples/05-logic-flowchart/`](../examples/05-logic-flowchart/) | Logic — flowcharts |
| 6 | [`examples/06-statistics-probability/`](../examples/06-statistics-probability/) | Statistics — conditional probability |
| 7 | [`examples/07-chemistry-stoichiometry/`](../examples/07-chemistry-stoichiometry/) | Chemistry — stoichiometry |
| 8 | [`examples/08-electronics-ohms-law/`](../examples/08-electronics-ohms-law/) | Electronics — Ohm law |

The linear-equations example includes an offline A4 [combined edition](../print-examples/linear-equations/combined.html)
and a separate [answer key](../print-examples/linear-equations/answers.html). The other examples use the host bridge
for on-demand print materials. See the [printing guide](printing.md) for the course-to-print workflow.

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

## Static checks and design tokens

`scripts/verify_example.py` is the static gate (CI runs `python scripts/verify_example.py --all`).
Checks have stable IDs; run with `--verbose` to list every one:

| Prefix | Scope |
|---|---|
| `A1`–`A6` | single file and offline: no CDN, external script, network call or external image |
| `B1`–`B6` | output contract: `#leap-interaction-output`, `window.LEAP`, append-only events |
| `C*`/`D*` | the three required zones and the practice/console components |
| `E1`–`E7` | payload identity: `leap_version`, `example_id`, learner/session placeholders |
| `F1`–`F17` | visual rules: tokens, fonts, spacing, motion, no gradients/images/emoji |
| `G0` | subject-specific component presence |
| `H1`–`H9` | host bridge: hydration, outbox, no locally computed mastery |
| `I1` | every `#id` referenced from script or CSS exists in the page |

The design tokens the gate requires in `:root` (a media query may override them). These are the
values every shipped example uses, and the executable checks remain the source of truth:

| Token | Value | Token | Value |
|---|---|---|---|
| `--paper` | `#FAF9F6` | `--surface-sunk` | `#F3F1EC` |
| `--ink` | `#191B20` | `--hairline` | `#E8E4DC` |
| `--accent` | `#2B4AC4` | `--ok` | `#2E7D5B` |
| `--warn` | `#B3861A` | `--err` | `#B4432F` |
| `--fs-display` | `32px` | `--fs-h2` | `22px` |
| `--fs-h3` | `17px` | `--fs-body` | `15.5px` |
| `--fs-small` | `13px` | `--fs-micro` | `11.5px` |

Evidence-stage colours (`--ev-estimated` `#9AA1AD` … `--ev-transferred` `#B3861A`), hint-ladder
colours (`--hint-1` … `--hint-4`) and the 4pt spacing grid (`--s-1` `4px` … `--s-20` `80px`) are
checked as warnings. Layout rules: wide desktop containers up to 1800px, a 320–420px side rail,
no horizontal overflow at 375px.

## Verification

Do not check these by eye — the checklist is encoded as executable checks:

Run the checks in [[CONTRIBUTING|the contributing guide]], which includes browser setup and the complete verification sequence.

`scripts/apply_leap_bridge.py --check` verifies **completeness, not just presence**: a regenerated page can keep the bridge
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

[[Knowledge_Index]] · [[README]] · [[README_CN]] · [[examples/README_CN]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]] · [[docs/i18n/README.ru]]
