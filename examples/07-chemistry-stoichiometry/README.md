---
title: Stoichiometry Example — English Guide
tags:
- leap/examples
- chemistry/stoichiometry
aliases:
- Chemistry Example Guide
---

> [!info] Learning resources
> Core: `chemical equation balancing coefficient subscript beginner`; `mole molar mass grams to moles`.
> Extension: `limiting reactant n divided by coefficient theoretical yield`.
> Advanced: `OpenStax Chemistry 2e reaction yields reaction extent`; `BIPM mole Avogadro constant`.
> These are search queries. Authoritative texts actually read are documented in [[examples/07-chemistry-stoichiometry/sources|the source record]].

# Example 7 · Balancing and the Limiting Reactant

Language: English · [[examples/07-chemistry-stoichiometry/README_CN|中文说明]]

Open `leap-07-chemistry-stoichiometry.html` directly in a browser. It contains inline CSS, JavaScript, MathML, SVG and the shared LEAP bridge kernel; no server, build or network is needed. Teaching text is Chinese. The canonical [[examples/07-chemistry-stoichiometry/knowledge|knowledge manuscript]] covers all teaching and solutions, with derivations and additional examples. [[examples/07-chemistry-stoichiometry/sources|Sources]] records the BIPM and OpenStax materials actually read.

Allow 35–50 minutes with basic chemical formulas, ratios and unit conversion. The lesson distinguishes subscripts from coefficients, counts conserved atoms, converts grams into moles, compares `n/coefficient`, and calculates products and leftovers. It states the fixed school approximations `M(H2)=2.00`, `M(O2)=32.0`, `M(H2O)=18.0 g/mol` and the complete-reaction/recovery assumptions.

Two tools use different scales: an integer molecule demonstration consumes 2H2 and 1O2 per full batch, while a macroscopic calculator uses continuous moles. The default 6 g H2 / 32 g O2 model yields 36 g water with 2 g H2 remaining. Sliders, play/pause, forward/backward/reset, hydrogen-limiting and stoichiometric presets, invalid input and zero-theoretical-yield boundaries are covered.

Fixed tasks include minimal balancing, limiting-reactant outputs, coefficient-versus-mass choices, one explanation collected for semantic review, and a new exact task after confirmed full solutions. Every retry retains the original answer. Objective correctness does not establish reasoning, transfer or confidence. The page uses `window.LEAP=createLeapBridge(config)` with inline `examples/_shared/bridge-kernel.js`, provisional assessments, item-specific attempt references and Runtime receipts. Local completion requests the guard; Runtime owns actual advancement.

Identifiers: `chem.stoichiometry.limiting` / `chemistry` / `stoichiometry`. Run from the repository root:

```powershell
.venv/quality-runtime/Scripts/python.exe scripts/verify_example.py examples/07-chemistry-stoichiometry/leap-07-chemistry-stoichiometry.html
.venv/quality-runtime/Scripts/python.exe scripts/verify_example_runtime.py examples/07-chemistry-stoichiometry/leap-07-chemistry-stoichiometry.html --chromium <path-to-chromium>
```

`leap-07-chemistry-stoichiometry.runtime.json` exercises all 117 particle parameter combinations and all their reaction batches, mass conservation, continuous-mole calculations, exact/partial/revised answers, semantic collection and bridging. These are browser and contract checks, not real MCP integration or an actual experiment. See [[examples/README|all examples]] and [[docs/content-quality|the quality workflow]].

> [!note]- Review boundary
> Browser checks verify arithmetic and interaction behavior for the declared ideal model. They do not establish a reaction mechanism, experimental procedure or real MCP execution; Runtime receipts remain authoritative for learning progress.

Related: [[Knowledge_Index]]


Related: [[docs/teaching-delivery]]

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/07-chemistry-stoichiometry/README_CN]] · [[examples/07-chemistry-stoichiometry/knowledge]] · [[examples/07-chemistry-stoichiometry/sources]]
