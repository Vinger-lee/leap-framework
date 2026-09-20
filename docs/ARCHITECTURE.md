# Architecture

**Language**: English ｜ [中文](ARCHITECTURE_CN.md)

> The authoritative framework design specification and visual design system are maintained by the
> project author separately and are **not** part of this repository. This document describes the
> architecture as implemented here.

---

## 1. Layers

```
Learner
   ↓
Host Agent — reasoning, generation, interaction, multimodality
   ↓  MCP (stdio)
LEAP MCP Server — tool interface, request validation, error mapping
   ↓
LEAP Learning Runtime
   Goal · Diagnostic · Knowledge DAG · State estimation
   Policy · Assessment · Retention · Transfer · State Guard
   ↓
Persistence — SQLite · artifacts · append-only event log
```

The split is deliberate: **prompts guide behaviour, the server guarantees consistency.**
Everything that must not diverge between sessions — mastery, prerequisites, assessment
sufficiency, transfer evidence, review state, whether a topic may be closed — is decided
server-side.

## 2. Design principles

| Principle | Consequence |
|---|---|
| Three-layer separation | Evidence-backed principles → pedagogical policy → engineering parameters. Every threshold is a configurable heuristic, never a claimed optimum |
| State-driven | The session is a container; **learner state is the input to teaching decisions**. No hard-coded "explain for 10 minutes, then quiz" rhythm |
| Server-side authority | The State Guard is the only component that may authorise a transition |
| Correct ≠ learned | One correct answer is one piece of evidence; stages regress |
| Progressive disclosure | An answer is a teaching resource: protect thinking space → detect difficulty → support → demonstrate → **verify afterwards** |
| Retention and transfer are the evidence | Success in the current task is not the outcome |
| Model-agnostic | Not tied to any specific LLM |

## 3. Runtime subsystems

| Subsystem | Module | Responsibility |
|---|---|---|
| State estimation | `runtime/bkt.py` | Forgetting-aware BKT; mastery is computed here, never by the LLM |
| Evidence stages | `runtime/evidence.py` | Promote / regress heuristics over `estimated → … → transferred` |
| Policy | `runtime/policy.py` | Chooses strategy and action from state; includes interleaving and session overrides |
| State Guard | `runtime/state_guard.py` | The only transition authority; returns structured allow / reject |
| Review scheduling | `runtime/scheduler.py` | FSRS-based spaced repetition, rating 1–4 |
| Learning modes | `runtime/learning_modes.py` | Learner-requested modes → session-scoped policy overrides |
| Metrics | `runtime/metrics.py` | Learning-outcome indicators |
| Plugin registry | `runtime/plugins.py` | Resolves the six seams from configuration |
| Contracts | `runtime/contracts.py` | The protocols a replacement must satisfy |
| Events | `runtime/events.py` | Append-only log; every decision is replayable |

## 4. Data model

SQLite, with `knowledge_node` as the only teaching entity. A **unit** is a business aggregation
label (`knowledge_nodes.unit_tag`), not a table.

| Concern | Authoritative source | Cache column |
|---|---|---|
| Misconceptions | `misconceptions` | `learner_knowledge_state.misconception_state` |
| Review state | `review_items` | `learner_knowledge_state.next_review_at` |
| Evidence stage | `learner_knowledge_state.evidence_stage` | `assessment_results.evidence_stage` (per-attempt snapshot) |

Cache columns are refreshed by the runtime; business code never writes them directly.

**Timestamps are Unix seconds throughout.** Because several events can share a second, any
before/after split (for example diagnostic baseline versus post-test) uses the event log's
append order, never the timestamp alone.

Schema changes are additive: `CREATE TABLE IF NOT EXISTS` never alters an existing table, so new
columns are registered in `ADDED_COLUMNS` and applied by `Database._migrate()`.

## 5. Request flow

1. `create_session` — if a `domain_grounding_notice` is returned, the agent must show it to the
   learner (token cost, waiting time, the risk of skipping) and let them choose.
2. Domain Grounding — the agent studies the topic, then `save_benchmark_report`.
3. `save_learning_goal`, then `generate_diagnostic` / `submit_diagnostic`.
4. `decompose_topic` returns a **template**; the agent authors nodes and edges and submits them,
   and the server validates the DAG.
5. Teaching loop: `get_teaching_context` → `commit_pedagogical_decision` → `submit_attempt` →
   `commit_assessment` → `get_mastery_status`.
6. `check_advance_unit` (dry run) → `advance_unit`, or `rollback_unit`.
7. `schedule_review` / `get_due_reviews` / `submit_review`, plus `generate_transfer_probe` and
   `record_transfer_result`.
8. `record_reflection` → `generate_final_report` → `complete_session`.

## 6. Error model

A failing tool returns `{ ok: false, error: { code, message, details } }`. Common codes:
`domain_grounding_required`, `state_guard_rejected`, `invalid_knowledge_dag`,
`invalid_argument`, `invalid_score`, `unknown_session`.

A failed call is never turned into a silent state update.

## 7. Extension points

See [`README.md`](../README.md#-pluggable-by-design). Each seam is a `Protocol` in
`runtime/contracts.py`; implementations register against a kind in `runtime/plugins.py` and are
selected by name in `config/default.yaml`.

## 8. Internationalisation

Learner-facing text resolves through `src/leap/i18n.py`: active locale → default locale → the key
itself, so a missing translation degrades instead of raising. Tool names, field names and enum
values are intentionally not translated. See [`LOCALIZATION.md`](LOCALIZATION.md).

## 9. Quality gates

| Gate | Command |
|---|---|
| Tests | `pytest -q` |
| Secrets & PII | `python scripts/security_scan.py --root .` |
| Example static compliance | `python scripts/verify_example.py --all` |
| Example runtime compliance | `python scripts/verify_example_runtime.py --all` |
| Spec coverage | `python scripts/spec_coverage.py` |
| Host bridge completeness | `python scripts/apply_leap_bridge.py --check` |

Exit codes are `0` clean / `1` blocking / `2` warnings only. The first four run in CI on every
push.

## 10. Publication hygiene

AI assistant workspaces and local scratch directories never reach a commit. Three layers enforce
this:

1. `.gitignore` covers the whole category, with wildcard forms for variant names.
2. Scanner rule `AI001` is path-based, so it fires even when `.gitignore` is bypassed.
3. `tests/test_infrastructure.py::TestAiWorkspaceIsolation` queries `git ls-files` and the full
   commit history and asserts zero such files; CI runs it on every push.
