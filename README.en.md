# LEAP Framework V2.0

> This repository does **not** include the full framework design or visual specification.
> Those authoritative documents are maintained by the project author separately and are **not**
> published in this repo. The code in `src/leap/` and the examples in `examples/` follow them;
> contact the author if you need access.


> This repository does **not** include the full framework design or visual specification.
> Those authoritative documents are maintained by the project author separately and are **not**
> published in this repo. The code in `src/leap/` and the examples in `examples/` follow them;
> contact the author if you need access.


**Learning Evolution & Adaptation Pipeline** — the foundation for an **Agentic Intelligent Tutoring System** built for AI agents.

**Language**: [简体中文](README.md) ｜ **English**

> LEAP is not about making a large model "act more like a teacher". It gives an agent an
> **executable, persistent, auditable and iterable** learning loop:
> **understand the goal → calibrate the domain → diagnose the learner → build the knowledge
> structure → estimate learner state → choose a teaching strategy → act → collect assessment
> evidence → update state → schedule retention and transfer → decide again**

```
Learner
   ↓
Host Agent (reasoning / generation / interaction / multimodality)
   ↓  MCP (stdio)
LEAP MCP Server (tool interface / request validation)
   ↓
LEAP Learning Runtime
   Goal · Diagnostic · Knowledge DAG · State Estimation
   Policy · Assessment · Retention/Transfer · State Guard
   ↓
Persistence (SQLite / Artifact Store / Event Log)
```

---

## 1. Core design principles

| Principle | What it means |
|---|---|
| **Three-layer separation** | Evidence-backed principles (Level 1) → pedagogical policies (Level 2) → engineering parameters (Level 3). Every threshold is a configurable heuristic, never a claimed scientific optimum |
| **State-driven** | The session is only a container; **learner state is the primary input to teaching decisions**. There is no hard-coded "explain for 10 minutes, then quiz" rhythm |
| **Prompts guide behaviour, the server guarantees consistency** | Mastery, prerequisites, assessment sufficiency, transfer evidence, review state and whether a unit may end are all finally validated by the **server-side State Guard** |
| **"Answered correctly" ≠ "learned"** | One correct answer produces one piece of evidence. The internal model is `estimated → practiced → demonstrated → retained → transferred`, and it **may regress** |
| **Progressive answer disclosure** | An answer is a teaching resource, not a permanently forbidden output. Protect thinking space → detect difficulty → support moderately → demonstrate when justified → **verify afterwards** |
| **Retention and transfer are the final evidence** | Success in the current task is not the outcome. Retention and transfer are **two complementary long-term evidence dimensions**, not a strict sequence |
| **Model-agnostic** | Not tied to GPT, Claude, Gemini, Qwen or any specific model |

---

## 2. Quick start

### Requirements

- Python ≥ 3.11
- No external services (P0 runs as a purely local process)

### Install

```bash
git clone <repo-url>
cd LEAP_Framework
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Run the tests

```bash
pytest
```

### Start the MCP server (stdio)

```bash
python -m leap.server
# or, after installation
leap-mcp
```

### Privacy self-check before publishing

```bash
python scripts/security_scan.py --root . --md reports/security-scan.md
```

Exit codes: `0` clean / `1` has P0+P1 (blocks release) / `2` only P2. Suitable as a CI gate.

> **Never published**: AI assistant workspaces (`.workbuddy-ai/`, `.claude/`, `.cursor/`, ...),
> the local archive (`_archive/`), caches and local runtime data. Guarded by `.gitignore`,
> scanner rule `AI001` and the `TestAiWorkspaceIsolation` tests.
> See [`docs/README.en.md`](docs/README.en.md).

### Verify the front-end examples

```bash
python scripts/verify_example.py --all                    # static spec compliance
python scripts/verify_example_runtime.py --all            # runtime behaviour + JSON Schema
```

The first checks structure and contract with no dependencies. The second actually executes
each page in headless Chromium and validates the object returned by
`window.LEAP.getInteractionResult()` against `interaction-output.schema.json`. It needs
`playwright` and a Chromium build; point at one with `--chromium <path>`.

---

## 3. Repository layout

```
LEAP_Framework/
├── config/default.yaml          # every engineering parameter (Policy may override)
├── src/leap/
│   ├── config.py                # configuration loading (YAML + env + overrides)
│   ├── i18n.py                  # message catalogues (zh-CN / en)
│   ├── server.py                # MCP server (stdio), 58 tools
│   ├── runtime/                 # server-side decision core
│   │   ├── contracts.py         #   §35 the six pluggable protocols
│   │   ├── plugins.py           #   implementation registry (config selects)
│   │   ├── bkt.py               #   simplified forgetting-aware BKT estimator
│   │   ├── scoring.py           #   multi-dimensional score aggregation (§10.3-1)
│   │   ├── evidence.py          #   Evidence Stage promote/regress heuristics
│   │   ├── scheduler.py         #   py-fsrs review scheduling
│   │   ├── state_guard.py       #   the only component that may authorise a transition
│   │   ├── policy.py            #   pedagogical policy engine (incl. §31 interleaving)
│   │   ├── learning_modes.py    #   §32 custom learning modes and policy overrides
│   │   ├── metrics.py           #   §26 learning-outcome indicators
│   │   └── events.py            #   event log
│   ├── storage/                 # SQLite schema + connection/transaction/idempotency
│   ├── tools/                   # tool implementations, split by domain
│   └── specs/                   # static Obsidian / web-component specifications
├── tests/                       # 244 tests
├── scripts/
│   ├── security_scan.py         # privacy & secret scanner (CI gate)
│   ├── verify_example.py        # static spec compliance for examples
│   ├── verify_example_runtime.py# runtime check (headless + JSON Schema)
│   ├── apply_leap_bridge.py     # inject/repair the host bridge (idempotent, reversible)
│   └── spec_coverage.py         # mechanically diff the spec against the code
├── examples/                    # front-end interaction examples
└── reports/                     # staged implementation reports
```

---

## 4. Learning lifecycle

```
1. Goal Specification
2. Domain Grounding            ← mandatory by default
3. Learner Diagnostic          ← protected by the State Guard
4. Knowledge Representation (DAG)
5. Learner State Initialization
6. Dynamic Teaching Loop
   Read State → Policy → Action → Attempt → Assessment → State Update
7. Retention (FSRS scheduling)
8. Transfer (near → variation → far → integrated)
9. Reflection & Persistence
```

### Domain Grounding (mandatory by default)

Before any teaching begins, the host agent must study the target topic and produce an internal
knowledge baseline report.

- **Benefit**: sharply reduces hallucination; content is far more likely to be factually correct
- **Cost**: more tokens and some waiting time up front
- **Skippable**: `allow_skip_domain_grounding=true` (**per-session**), but it raises the risk of
  incorrect content, so the user must be told before it is enabled

Until grounding is complete and skipping is not enabled, `generate_diagnostic` is rejected by the
State Guard.

---

## 5. Key mechanisms

### 5.1 `mastery_probability` is computed server-side

Mastery is a **model estimate, not ground truth**. In P0 the runtime computes it with a built-in
simplified forgetting-aware BKT; the **host agent's LLM never emits a probability** (which would
be numerically unstable and unauditable).

Each update has four steps: time decay → evidence update (guess/slip posterior) → transition →
spontaneous forgetting.

- **Partial credit** is supported: `s·P(correct) + (1-s)·P(incorrect)`
- **Low-confidence discounting**: when the assessor is unsure, the observation is pulled back
  toward the prior — uncertainty is **never written in as `mastery = 0`**

### 5.2 Evidence stages may regress

| Stage | Reference default criteria |
|---|---|
| `estimated` | Inferred only from the DAG / diagnostic; no answer evidence for this node |
| `practiced` | ≥1 effective attempt with `hint_dependency < 0.9` |
| `demonstrated` | `mastery ≥ 0.8`, `hint_dependency ≤ 0.5`, and at least one low-hint success |
| `retained` | Already `demonstrated`, and still passing after the configured spacing interval |
| `transferred` | At least one completed transfer probe scoring `≥ 0.7` |

Regression: a long absence → back to `practiced` and re-enters the review queue; failure in a new
scenario → back to `demonstrated`.

> The criteria live in the **Policy layer and are configurable**. The State Guard only reads the
> resulting `evidence_stage`; it never re-derives the promotion conditions.

### 5.3 `advance_unit` is a batch wrapper

- **The only data-layer entity is `knowledge_node`.** A `unit` is a business aggregation label
  (`knowledge_nodes.unit_tag`) — there is deliberately **no unit table**
- `advance_unit` walks every node carrying that `unit_tag` and runs the node-level State Guard on
  each; **a single failure rejects the whole request**
- Seven checks: `prerequisites_met` / `assessment_sufficient` / `evidence_sufficient` /
  `transfer_required` / `transfer_completed` / `current_state_version_valid` / `manual_override`

### 5.4 Authoritative sources vs. caches

| Meaning | Authoritative source | Cache column |
|---|---|---|
| Misconceptions | `misconceptions` table | `learner_knowledge_state.misconception_state` |
| Review state | `review_items` table | `learner_knowledge_state.next_review_at` |
| Evidence stage | `learner_knowledge_state.evidence_stage` | `assessment_results.evidence_stage` (immutable per-attempt snapshot) |

Cache columns are refreshed by the runtime; **business code must never write them directly**.

### 5.5 Due reviews do not block everything

A non-empty review queue **does not** mean all new learning must stop. Whether to insert,
prioritise or block is decided per node by Policy + State Guard.

---

## 6. Engineering parameters

`config/default.yaml` holds every parameter. **Each one is an engineering heuristic and the Policy
engine may override all of them.** Common entries:

| Parameter | Default | Meaning |
|---|---|---|
| `mastery_threshold` | `0.80` | Mastery threshold (initial engineering value) |
| `max_hint_level` | `3` | Hint ceiling |
| `max_retry_before_example` | `3` | Failures before a worked example |
| `friction_window` | `3` | Friction observation window, **unit = attempts** |
| `reasoning_quality_low` | `0.5` | Below this counts as significantly low |
| `hint_dependency_high` | `0.7` | Above this counts as high hint dependency |
| `overall_score_weights` | `0.4/0.3/0.2/0.1` | correctness / conceptual / reasoning / application |
| `review_scheduler` | `py-fsrs` | Review scheduler, rating 1–4 |
| `mcp_transport` | `stdio` | P0 is a local process only |
| `auth_enabled` | `false` | P0 assumes a single trusted machine |
| `locale` | `zh-CN` | Language of learner-visible text (`zh-CN` / `en`) |

`transfer` and `hint_dependency` are **excluded** from the `overall_score` aggregate and are fed to
the Policy engine as separate inputs.

---

## 6.1 Internationalisation

The runtime ships an i18n layer. Everything a **learner or operator actually reads** comes from a
message catalogue rather than a hard-coded string:

| Localised | Deliberately not localised |
|---|---|
| State Guard rejection reasons | Code comments, logs, exception types |
| Domain Grounding notice | Tool names, field names, enum values |
| Learning mode names and descriptions | Policy rationale (internal audit trail) |
| Closing report headings and section names | |

```yaml
locale: zh-CN          # supported: zh-CN | en
```

Override with the environment: `LEAP_LOCALE=en`. Language affects text only — it **never changes a
state transition**. See [`docs/i18n.md`](docs/i18n.md) for adding a language. Tests enforce that the
two catalogues have **identical key sets**, so a missing translation can never leak a raw key.

---

## 7. P0 delivery boundary

### ✅ Delivered

1. LEAP MCP server (stdio) + SQLite
2. Complete tool set (58 tools)
3. Server-side State Guard
4. Built-in simplified forgetting-aware BKT
5. FSRS (`py-fsrs`) review scheduling
6. Event log and decision log
7. Artifact storage
8. Static specification output (web-component spec, Obsidian vault spec)
9. Privacy scanner, example verifiers and a test suite

### ❌ Not delivered in P0

> Web front-end pages, real Obsidian vault read/write code, a complete reference agent.
> **The MCP layer only emits specifications; the host agent produces the files.**

### Later phases

- **P1**: minimal reference host agent, external estimator (mode B), extended multi-dimensional rubrics
- **P2**: HTTP / SSE transport, authentication, multi-tenancy, teacher dashboard

---

## 8. Documentation

| Document | Contents |
|---|---|
| （作者维护的框架设计文档，不在本仓库） | Full framework design, 42 sections (authoritative document is not in this repo) |
| （作者维护的视觉规范，不在本仓库） | Visual specification for teaching pages (authoritative, Chinese) |
| [`docs/README.md`](docs/README.md) | Documentation index |
| [`docs/host-agent-system-prompt.md`](docs/host-agent-system-prompt.md) | Host agent integration guide (Chinese) |
| [`docs/host-agent-system-prompt.en.md`](docs/host-agent-system-prompt.en.md) | Host agent integration guide (English) |
| [`docs/i18n.md`](docs/i18n.md) | Internationalisation guide |
| [`examples/`](examples/README.md) | Five subject examples, specifications and verification scripts |
| [`reports/`](reports/) | Staged implementation reports |

---

## 9. Licence

[MIT](LICENSE)
