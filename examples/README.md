# Teaching Page Examples

**Language**: English ｜ [中文](README_CN.md)

Five single-file teaching pages, produced by a host agent from the engineering-side task book.
They are the reference for structure, components, interaction and visuals when a host agent
generates pages later.

> The visual design system is maintained by the project author separately and is **not** in this
> repository; every page here follows it.

## Layout

```
examples/
├── README.md                     # this file
├── README_CN.md                  # 中文
├── _shared/
│   ├── leap-web-spec.md          # structural spec (authoritative for structure)
│   ├── leap-bridge.md            # page ↔ runtime interface
│   ├── interaction-output.schema.json
│   └── design-references/        # four visual reference images
├── 01-python-recursion/          # programming
├── 02-math-linear-equation/      # mathematics
├── 03-cs-osi-model/              # computer science
├── 04-physics-free-fall/         # physics
└── 05-logic-flowchart/           # logic
```

`leap-web-spec.md` defines *which three zones must exist and which JSON fields are required*;
the visual specification defines *what those zones look like*.

## Naming and placement

Each example is **one single-file HTML**. Names and locations are fixed:

| # | Subject | File | Directory |
|---|---|---|---|
| 1 | Programming — Python recursion | `leap-01-python-recursion.html` | `01-python-recursion/` |
| 2 | Mathematics — linear equations | `leap-02-math-linear-equation.html` | `02-math-linear-equation/` |
| 3 | Computer science — OSI model | `leap-03-cs-osi-model.html` | `03-cs-osi-model/` |
| 4 | Physics — free fall | `leap-04-physics-free-fall.html` | `04-physics-free-fall/` |
| 5 | Logic — flowcharts | `leap-05-logic-flowchart.html` | `05-logic-flowchart/` |

When a page is produced in several parts, concatenate them **in order** before saving under the
name above. Do not leave fragment files.

## Automated verification

Run these before reviewing by eye:

```bash
# 1) static spec compliance
python scripts/verify_example.py --all

# 2) runtime behaviour (headless Chromium + authoritative JSON Schema validation)
python scripts/verify_example_runtime.py --all

# 3) privacy scan (this directory is scanned too)
python scripts/security_scan.py --root .

# 4) host-bridge completeness
python scripts/apply_leap_bridge.py --check
```

- `verify_example.py` covers structure, contract, design tokens, anti-patterns, subject
  components, the host bridge, and **DOM reference integrity** (a renamed element id with a stale
  script reference only fails at runtime).
- `verify_example_runtime.py` covers what only a real run can prove: whether
  `getInteractionResult()` is callable, whether its return value validates against the schema,
  whether `events` is append-only, whether `created_at` is Unix seconds, whether 375/1280px
  overflow horizontally, and whether the bridge actually works.
- **Static success does not mean runtime-usable. Run both.**

If a page is missing the bridge, or a regeneration dropped part of it:

```bash
python scripts/apply_leap_bridge.py --all       # inject (idempotent)
python scripts/apply_leap_bridge.py --repair    # restore a dropped part
python scripts/apply_leap_bridge.py --check     # completeness, not just presence
```

`verify_example_runtime.py` needs `playwright` and a Chromium build; point at one with
`--chromium <path>` and export captures with `--screenshots <dir>`.

## Acceptance checklist

- [ ] Single file, zero external CDN / requests / images; opens offline
- [ ] All three zones present: teaching + practice + agent output
- [ ] Output container `id="leap-interaction-output"` and `window.LEAP.getInteractionResult()`
- [ ] JSON matches `_shared/interaction-output.schema.json` exactly; field names unchanged
- [ ] **Host bridge complete**: `LEAP.hydrate()` accepts state, `LEAP.drainOutbox()` emits calls
- [ ] **Every interaction produces the corresponding MCP call**, and `commit_assessment` carries a
      non-empty `raw_answer`
- [ ] **The page never computes `mastery_probability`**, and never sends one in a call
- [ ] Three-level progressive hints work and record `hint_level` (0–4)
- [ ] Feedback distinguishes `answer_error` / `reasoning_error` / `misconception`
- [ ] Partial credit is supported (not just right/wrong)
- [ ] Formulas use native MathML or SVG (**no** KaTeX / MathJax)
- [ ] All graphics are inline SVG / Canvas (no external images)
- [ ] Every interaction component required by the subject is implemented
- [ ] Layout holds at 1280px desktop and 375px mobile

### Visual checklist

- [ ] The `:root` token block is present in full; no bare hex, no off-grid spacing
- [ ] A persistent progress spine (five-segment evidence rail + mastery + next review)
- [ ] All three zones separated by the five-part zone header
- [ ] The hint ladder is a bottom-aligned, height-increasing figure — not three flat buttons
- [ ] Level 4 requires a second confirmation and forces post-verification
- [ ] Feedback is three-part, with the colour bar following `error_type`
- [ ] The evidence rail gains a point on every interaction
- [ ] The agent output zone is a collapsed status bar with an expandable recorder (**not a bare
      black `<pre>`**)
- [ ] No gradients, no glassmorphism, no emoji icons

## Relationship to the framework design

| Item here | Framework concept |
|---|---|
| Progressive answer disclosure (3 levels) | Progressive Answer Disclosure |
| Multi-dimensional feedback and error types | Multi-dimensional assessment, partial credit |
| JSON output contract fields | MCP tool contract, database design |
| Interaction event types | Core events |
| The page as the primary teaching surface | Web: interactive learning layer |
