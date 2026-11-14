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

Related: [Knowledge_Index](Knowledge_Index.md) · [docs/teaching-delivery](docs/teaching-delivery.md)

# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/github/v/release/Vinger-lee/leap-framework" alt="Release">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-71%20tools-22bb33" alt="MCP Tools">
  [![Tests](https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml)
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
pytest -q        # run the full suite
```

Start the MCP server:

```bash
python -m leap.server      # or: leap-mcp
```

### 📦 Install as a package

```bash
pip install "leap-framework"          # add [examples] only if you verify teaching pages
leap-doctor                           # installation self-check
leap-mcp --tool-profile quickstart    # stdio MCP server (default profile: full)
```

A package install ships the same defaults inside the wheel (`leap/config/default.yaml`), so
`leap-doctor` and the server work without a checkout. Configuration is layered, lowest first:

- the YAML file — the repository `config/default.yaml`, otherwise the packaged copy;
- environment overrides such as `LEAP__DATABASE_PATH`, `LEAP__ARTIFACT_ROOT` and
  `LEAP__TOOL_PROFILE` (nested keys use a double underscore);
- tool profile — `--tool-profile`, `LEAP_TOOL_PROFILE`, or `tool_profile` in the configuration.

`database_path` and `artifact_root` are resolved against `LEAP_HOME` when it is set, otherwise
against the current working directory — never against the installed package, so `data/leap.db` and
`artifacts/` cannot land inside `site-packages`. Set `LEAP_HOME` to a writable directory for a
stable deployment:

```bash
LEAP_HOME=/var/lib/leap leap-mcp --tool-profile quickstart
```

**Tool profiles**: `full` exposes the complete tool catalogue (default); `quickstart` exposes the
coarse teaching path for small hosts. `leap-doctor` prints the counts for the installed version.

**Agent Skill (optional)**: hosts that load repository skills can open
`.agents/skills/leap-tutor/` (see [host configuration](docs/host-config.md)); hosts without skill
support follow the integration guide. The runtime enforces the same gates either way — the skill
changes how the agent is guided, not what the server allows.

For teaching-page verification dependencies, commands and acceptance criteria, see
[the contributing guide](CONTRIBUTING.md).

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

Names, parameters, host descriptions and profile membership are maintained in the
[generated MCP tool reference](docs/mcp-tools.md).

The coarse API composes teaching steps server-side and returns `next_call` in each response.
The State Guard decides transitions; refused advances write no state, failed assessments preserve
the stored attempt, and mastery is estimated server-side. New integrations can explicitly select
`--tool-profile quickstart`; the default remains `full`. See [the coarse API and profiles](docs/FACADE.md)
and [the framework's boundaries](docs/scope-and-limits.md).

Hosts supporting repository skills can load
[leap-tutor](.agents/skills/leap-tutor/SKILL.md) for the learning workflow and
conditional recovery guidance. See [setup and acceptance](docs/agent-skill.md) and
[host configuration](docs/host-config.md) for copy-paste `mcpServers` samples and the per-host
discovery matrix (Claude Code, for example, scans `.claude/skills`, not `.agents/skills`).
The skill is a draft; host discovery, activation and the MCP connection still need separate
verification. Quickstart is a complete teaching path: it records new misconceptions
(`assess_misconception`), records a learner's informed decision to skip domain grounding
(`set_domain_grounding_skip`), recovers split assessments and closes sessions explicitly; a
closed session stops suggesting teaching calls. Responses carry a compact `policy_version`
instead of the full policy, and `continue_lesson` returns a summary unless `verbose=True`.
Use full for the existing HTML outbox bridge.

Domain Grounding now requires source locators, excerpts, linked claims, checked examples and limitations in `save_benchmark_report(verification=...)`. Text alone remains pending; teaching entry points are guarded too. Hosts must read sources themselves and register checked questions with `save_assessment_item` before delivery. Free-text reasoning needs host semantic review: LEAP validates submitted records and estimates state; it does not prove subject-matter correctness.

See the [content-quality and integration workflow](docs/content-quality.md) and [audit of the reported delivery](docs/quality-audit-2026-10-10.md). Browser scenario checks and real MCP integration checks are separate from content review.

Every mode uses the permanent depth, controllable diagrams, wide layout, complete Obsidian source and precise resource policy. Register the actual Markdown/HTML pair with `save_teaching_package` before registering questions. See [docs/teaching-delivery](docs/teaching-delivery.md), the 11-domain catalog in [docs/subject-knowledge-map](docs/subject-knowledge-map.md), and the separate curriculum delivery workflow; course recipes are maintained outside this framework.

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

The verification sequence, browser setup and acceptance criteria live in [the contributing guide](CONTRIBUTING.md).
`.github/workflows/ci.yml` defines the automated checks, including a byte-for-byte check of the generated tool reference.

AI assistant workspaces (`.workbuddy*/`, `.claude*/`, `.cursor*/`, `agent-state/`, …) and local
scratch directories are excluded from publication by `.gitignore`, scanner rule `AI001`, and a CI
test that asserts the index and full history contain zero such files.

## 📖 Documentation

| Document | Contents |
|---|---|
| [README_CN.md](README_CN.md) | 中文说明 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture and design decisions |
| [docs/INTEGRATION.md](docs/INTEGRATION.md) | Host-agent integration guide |
| [docs/EXAMPLES.md](docs/EXAMPLES.md) | The eight teaching pages and their contract |
| [`docs/i18n/`](docs/i18n/) | Translations |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |
| [SECURITY.md](SECURITY.md) | Reporting a vulnerability |

> The authoritative framework design specification and visual design system are maintained by the
> project author separately and are **not** part of this repository. The implementation here
> follows those documents.

## 🤝 Contributing

Issues and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## 📄 License

[MIT](LICENSE) © Vinger-lee

> [!note]- Reading and verification sequence: LEAP 🎓 LEAP Framework
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[Knowledge_Index](Knowledge_Index.md) · [README_CN](README_CN.md) · [docs/ARCHITECTURE](docs/ARCHITECTURE.md) · [docs/FACADE](docs/FACADE.md) · [docs/i18n/README.ar](docs/i18n/README.ar.md) · [docs/i18n/README.es](docs/i18n/README.es.md) · [docs/i18n/README.fr](docs/i18n/README.fr.md) · [docs/i18n/README.ja](docs/i18n/README.ja.md) · [docs/i18n/README.ko](docs/i18n/README.ko.md) · [docs/i18n/README.ru](docs/i18n/README.ru.md) · [docs/scope-and-limits](docs/scope-and-limits.md)
