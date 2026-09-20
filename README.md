# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/github/v/release/Vinger-lee/leap-framework" alt="Release">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-58%20tools-22bb33" alt="MCP Tools">
  <img src="https://img.shields.io/badge/tests-260%20passing-22bb33" alt="Tests">
  <img src="https://img.shields.io/badge/中文-支持-ff6600" alt="中文支持">
  <br>
  <b>🤖 Give your AI agent a real tutoring engine — not just a prompt.</b>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README_CN.md">中文</a> ·
  <a href="docs/i18n/README.ja.md">日本語</a> ·
  <a href="docs/i18n/README.ko.md">한국어</a> ·
  <a href="docs/i18n/README.fr.md">Français</a> ·
  <a href="docs/i18n/README.es.md">Español</a> ·
  <a href="docs/i18n/README.ru.md">Русский</a> ·
  <a href="docs/i18n/README.ar.md">العربية</a>
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
pytest -q        # 260 passed
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

58 tools over stdio, grouped by domain:

| Group | Examples |
|---|---|
| Session & goal | `create_session`, `save_learning_goal`, `set_learning_configuration` |
| Diagnostic | `generate_diagnostic`, `submit_diagnostic`, `save_diagnostic_result` |
| Knowledge | `decompose_topic`, `save_knowledge_nodes`, `validate_knowledge_dag` |
| Policy | `get_teaching_context`, `evaluate_pedagogical_policy`, `commit_pedagogical_decision` |
| Assessment | `generate_assessment`, `assess_response`, `assess_misconception` |
| Retention | `schedule_review`, `get_due_reviews`, `submit_review` |
| State Guard | `start_unit`, `check_advance_unit`, `advance_unit`, `rollback_unit` |
| Evidence | `save_benchmark_report`, `get_evidence`, `validate_claim` |
| Artifacts | `save_artifact`, `get_obsidian_structure`, `get_web_component_spec` |
| Reporting | `generate_final_report`, `get_learning_metrics` |

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

Five single-page teaching demos, each verified statically and in headless Chromium:

| Example | Subject |
|---|---|
| `examples/01-python-recursion/` | Programming — Python recursion |
| `examples/02-math-linear-equation/` | Mathematics — linear equations |
| `examples/03-cs-osi-model/` | Computer science — OSI model |
| `examples/04-physics-free-fall/` | Physics — free fall |
| `examples/05-logic-flowchart/` | Logic — flowcharts |

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
├── examples/                # five teaching pages + shared specs
├── docs/                    # architecture, integration, i18n
├── scripts/                 # verifiers, scanner, auditors
└── tests/                   # 260 tests
```

## 🔍 Quality gates

```bash
pytest -q                                        # 260 tests
python scripts/security_scan.py --root .         # secrets & PII (CI gate)
python scripts/verify_example.py --all           # example static compliance
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
| [`README_CN.md`](README_CN.md) | 中文说明 |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Architecture and design decisions |
| [`docs/INTEGRATION.md`](docs/INTEGRATION.md) | Host-agent integration guide |
| [`docs/EXAMPLES.md`](docs/EXAMPLES.md) | The five teaching pages and their contract |
| [`docs/i18n/`](docs/i18n/) | Translations |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute |
| [`SECURITY.md`](SECURITY.md) | Reporting a vulnerability |

> The authoritative framework design specification and visual design system are maintained by the
> project author separately and are **not** part of this repository. The implementation here
> follows those documents.

## 🤝 Contributing

Issues and pull requests are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) first.

## 📄 License

[MIT](LICENSE) © Vinger-lee
