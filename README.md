---
title: 🎓 LEAP Framework
tags:
- leap
- engineering
aliases:
- 🎓 LEAP Framework guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP 🎓 LEAP Framework foundations definitions workflow`
> Extension: `LEAP 🎓 LEAP Framework failure cases examples comparison`
> Advanced: `LEAP 🎓 LEAP Framework invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/github/v/release/Vinger-lee/leap-framework" alt="Release">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-62%20tools-22bb33" alt="MCP Tools">
  [![Tests](https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml)
  <img src="https://img.shields.io/badge/中文-支持-ff6600" alt="中文支持">
  <br>
  <b>🤖 Give your AI agent a real tutoring engine — not just a prompt.</b>
</p>

<p align="center">
  [[README|English]] ·
  [[README_CN|中文]] ·
  [[docs/i18n/README.ja|日本語]] ·
  [[docs/i18n/README.ko|한국어]] ·
  [[docs/i18n/README.fr|Français]] ·
  [[docs/i18n/README.es|Español]] ·
  [[docs/i18n/README.ru|Русский]] ·
  [[docs/i18n/README.ar|العربية]]
</p>

---

## 🚀 What is LEAP?

**LEAP (Learning Evolution & Adaptation Pipeline) is a state-driven tutoring runtime for AI
agents.** It gives an agent a persistent, auditable learning loop instead of a one-shot
"explain then quiz" prompt.

Your agent keeps doing what it is good at — understanding the learner, generating explanations,
writing questions, judging open answers. LEAP owns everything that must be consistent:

- **learner state** and mastery estimation
- **prerequisites** and whether a topic may be entered
- **assessment sufficiency** and evidence quality
- **review scheduling** and long-term retention
- **state transitions** — nothing advances without passing the server-side State Guard

```bash
# Your agent asks LEAP what to do next
get_teaching_context(session_id, "py.recursion.base_case")
# 👉 strategy: Retrieval Practice · action: Generate Practice
#    evidence_stage: practiced · mastery: 0.62 · hint_dependency: 0.25
#    due_reviews: 2 · active_misconceptions: 1
```

## ⚡ Quick Start

```bash
git clone https://github.com/Vinger-lee/leap-framework.git
cd leap-framework
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest -q        # inspect the current test result
```

Start the MCP server:

```bash
python -m leap.server      # or: leap-mcp
```

Verify the bundled teaching pages:

```bash
python scripts/verify_example.py --all          # static spec compliance
python scripts/verify_example_runtime.py --all  # headless runtime + JSON Schema
```

## 🧠 The learning loop

```
1. Goal Specification
2. Domain Grounding          ← the agent studies the topic before teaching it
3. Learner Diagnostic
4. Knowledge Representation  ← DAG of knowledge nodes
5. Learner State Initialisation
6. Dynamic Teaching Loop     ← Read State → Policy → Action → Attempt → Assessment → Update
7. Retention                 ← FSRS spaced review
8. Transfer                  ← near → variation → far → integrated
9. Reflection & Persistence
```

### 🔒 State Guard

The State Guard is the only component that may authorise a transition. When a tool returns
`REJECT`, the agent adapts to the reason instead of pushing harder through prompt text.
A failed tool call never becomes a silent state update.

### 📊 Mastery is estimated server-side

`mastery_probability` is a **model estimate, not ground truth**. It is computed by a built-in
forgetting-aware BKT model, never emitted by the host agent's LLM — that keeps it numerically
stable and auditable. Each update runs four steps: time decay → evidence update → state
transition → spontaneous forgetting.

Partial credit and low-confidence discounting are supported. Uncertainty is never written in as
`mastery = 0`.

### 🪜 Evidence stages (and they can regress)

`estimated → practiced → demonstrated → retained → transferred`

One correct answer produces one piece of evidence — not mastery. Stages **regress** when a
learner has been away too long or fails in a new scenario. The criteria live in the Policy layer
and are fully configurable.

### ⏰ Retention and transfer

Due reviews do **not** block everything. Whether to insert, prioritise or block is decided per
node. Retention (FSRS, rating 1–4) and transfer (near / variation / far / integrated) are two
complementary long-term evidence dimensions.

## 🔧 MCP tools

62 tools over stdio, grouped by domain:

| Group | Examples |
|---|---|
| Session & goal | `create_session`, `save_learning_goal`, `set_learning_configuration` |
| Diagnostic | `generate_diagnostic`, `submit_diagnostic`, `save_diagnostic_result` |
| Knowledge | `decompose_topic`, `save_knowledge_nodes`, `validate_knowledge_dag` |
| Policy | `get_teaching_context`, `evaluate_pedagogical_policy`, `commit_pedagogical_decision` |
| Assessment | `generate_assessment`, `save_assessment_item`, `submit_attempt`, `commit_assessment`, `assess_response` |
| Retention | `schedule_review`, `get_due_reviews`, `submit_review` |
| State Guard | `start_unit`, `check_advance_unit`, `advance_unit`, `rollback_unit` |
| Evidence | `save_benchmark_report`, `get_evidence`, `validate_claim` |
| Teaching delivery | `get_teaching_delivery_policy`, `get_subject_catalog`, `save_teaching_package` |
| Artifacts | `save_artifact`, `get_obsidian_structure`, `get_web_component_spec` |
| Reflection | `record_reflection` |
| Reporting | `generate_final_report`, `get_learning_metrics` |

The table shows examples, not the complete catalog. The [[docs/mcp-tools|generated tool reference]] lists every registered tool and its exact parameters; CI checks it against the MCP catalog.

Domain Grounding now requires source locators, excerpts, linked claims, checked examples and limitations in `save_benchmark_report(verification=...)`. Text alone remains pending; teaching entry points are guarded too. Hosts must read sources themselves and register checked questions with `save_assessment_item` before delivery. Free-text reasoning needs host semantic review: LEAP validates submitted records and estimates state; it does not prove subject-matter correctness.

See the [[docs/content-quality|content-quality and integration workflow]] and [[docs/quality-audit-2026-10-10|audit of the reported delivery]]. Browser scenario checks and real MCP integration checks are separate from content review.

Every mode uses the permanent depth, controllable diagrams, wide layout, complete Obsidian source and precise resource policy. Register the actual Markdown/HTML pair with `save_teaching_package` before registering questions. See [[docs/teaching-delivery]], the 11-domain catalog in [[docs/subject-knowledge-map]], and the reproducible calculus chapter in [[curricula/math1-2028-ch01/README]].

## 🧩 Pluggable by design

Six components are resolved through a plugin registry, so an implementation can be swapped from
`config/default.yaml` without touching call sites:

| Seam | Default | Alternatives |
|---|---|---|
| State estimation | `simplified_bkt` | PFA, DKT, Bayesian, hybrid |
| Score aggregation | `weighted` | rubric, model-based |
| Pedagogical policy | `rule_based` | LLM, hybrid, learned |
| Review scheduler | `py-fsrs` | any scheduler |
| Storage | `sqlite` | PostgreSQL, distributed |
| Artifact store | `local` | object storage, knowledge base |

## 🌍 Internationalisation

Learner-facing text comes from a message catalogue (`zh-CN` / `en`). Tool names, field names and
enum values are deliberately **not** translated — translating them would break host-agent
integrations. Set `locale` in `config/default.yaml`, or override with `LEAP_LOCALE`.

## 📦 Configuration

Every parameter lives in `config/default.yaml` and is an engineering heuristic the Policy engine
may override:

| Parameter | Default | Meaning |
|---|---|---|
| `mastery_threshold` | `0.80` | Mastery threshold |
| `max_hint_level` | `3` | Hint ceiling |
| `max_retry_before_example` | `3` | Failures before a worked example |
| `hint_dependency_high` | `0.7` | High hint-dependency cutoff |
| `overall_score_weights` | `0.4/0.3/0.2/0.1` | correctness / conceptual / reasoning / application |
| `review_scheduler` | `py-fsrs` | Spaced-repetition backend |
| `interleaving_enabled` | `conditional` | Interleaved practice |
| `locale` | `zh-CN` | Language of learner-facing text |

## 📚 Examples

Eight single-page teaching demos, each verified statically and in headless Chromium:

| Example | Subject |
|---|---|
| `examples/01-python-recursion/` | Programming — Python recursion |
| `examples/02-math-linear-equation/` | Mathematics — linear equations |
| `examples/03-cs-osi-model/` | Computer science — OSI model |
| `examples/04-physics-free-fall/` | Physics — free fall |
| `examples/05-logic-flowchart/` | Logic — flowcharts |
| `examples/06-statistics-probability/` | Statistics — conditional probability |
| `examples/07-chemistry-stoichiometry/` | Chemistry — stoichiometry |
| `examples/08-electronics-ohms-law/` | Electronics — Ohm law |

Every page is a **reference implementation**: zero CDN, zero network requests, and it demonstrates
the real page ↔ runtime bridge — `LEAP.hydrate(context)` for state in, `LEAP.drainOutbox()` for
MCP calls out.

## 🗂 Repository layout

```
leap-framework/
├── config/default.yaml      # every engineering parameter
├── src/leap/
│   ├── i18n.py              # message catalogue
│   ├── server.py            # MCP server (stdio)
│   ├── runtime/             # decision core
│   │   ├── contracts.py     #   the plugin seams
│   │   ├── plugins.py       #   implementation registry
│   │   ├── bkt.py           #   mastery estimation
│   │   ├── policy.py        #   pedagogical policy
│   │   ├── scheduler.py     #   FSRS review scheduling
│   │   ├── state_guard.py   #   transition authority
│   │   └── ...
│   ├── storage/             # SQLite schema + migrations
│   ├── tools/               # tool implementations
│   └── specs/               # Obsidian / web component specs
├── examples/                # eight teaching pages + shared specs
├── docs/                    # architecture, integration, i18n
├── scripts/                 # verifiers, scanner, auditors
└── tests/                   # inspect the current test result
```

## 🔍 Quality gates

```bash
pytest -q                                        # inspect the current test result
python scripts/security_scan.py --root .         # secrets & PII (CI gate)
python scripts/verify_example.py --all           # example static compliance
python scripts/verify_teaching_repository.py     # canonical notes, reciprocal links and full paired bodies
python scripts/verify_mcp_bridge.py              # actual stdio Runtime + shipped page
python scripts/verify_example_runtime.py --all   # example runtime compliance
python scripts/spec_coverage.py                  # spec vs. code coverage
python scripts/apply_leap_bridge.py --check      # host-bridge completeness
```

Exit codes are `0` clean / `1` blocking / `2` warnings only. The first four run in CI on every
push.

AI assistant workspaces (`.workbuddy*/`, `.claude*/`, `.cursor*/`, `agent-state/`, …) and local
scratch directories are excluded from publication by `.gitignore`, scanner rule `AI001`, and a CI
test that asserts the index and full history contain zero such files.

## 📖 Documentation

| Document | Contents |
|---|---|
| [[README_CN|README_CN.md]] | 中文说明 |
| [[docs/ARCHITECTURE|docs/ARCHITECTURE.md]] | Architecture and design decisions |
| [[docs/INTEGRATION|docs/INTEGRATION.md]] | Host-agent integration guide |
| [[docs/EXAMPLES|docs/EXAMPLES.md]] | The eight teaching pages and their contract |
| [`docs/i18n/`](docs/i18n/) | Translations |
| [[CHANGELOG|CHANGELOG.md]] | Release history |
| [[CONTRIBUTING|CONTRIBUTING.md]] | How to contribute |
| [[SECURITY|SECURITY.md]] | Reporting a vulnerability |

> The authoritative framework design specification and visual design system are maintained by the
> project author separately and are **not** part of this repository. The implementation here
> follows those documents.

## 🤝 Contributing

Issues and pull requests are welcome. Please read [[CONTRIBUTING|CONTRIBUTING.md]] first.

## 📄 License

[MIT](LICENSE) © Vinger-lee

> [!note]- Reading and verification sequence: LEAP 🎓 LEAP Framework
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README_CN]] · [[docs/ARCHITECTURE]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]] · [[docs/i18n/README.ru]]
