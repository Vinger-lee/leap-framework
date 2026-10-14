---
title: Host Agent Integration Guide (System Prompt)
tags:
- leap
- engineering
aliases:
- Host Agent Integration Guide (System Prompt) guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP Host Agent Integration Guide (System Prompt) foundations definitions workflow`
> Extension: `LEAP Host Agent Integration Guide (System Prompt) failure cases examples comparison`
> Advanced: `LEAP Host Agent Integration Guide (System Prompt) invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]] · [[docs/FACADE]] · [[docs/scope-and-limits]]

# Host Agent Integration Guide (System Prompt)

## 0. Two ways to drive LEAP

| Path | Surface | Use it when |
|---|---|---|
| Coarse tutor API | 8 tools (`start_learning`, `continue_lesson`, `log_teaching_action`, `submit_answer`, `advance_lesson`, `get_review_queue`, `review_answer`, `get_learner_snapshot`) | You want one call per teaching-loop step; each response returns `next_call`, the next tool to call |
| Fine-grained runtime tools | The full catalog (§2) | You need to split a composed call across turns (record an attempt now, assess it after review) or to inspect policy/evidence directly |

Both APIs operate on the same rows, events and state versions, and a session can switch between them
at any time. Per-step coarse equivalents are noted in the standard flow below. To narrow the catalog
an agent sees, start the server with `--tool-profile quickstart` (25 tools) and see the
[[docs/FACADE|coarse tutor API and tool profiles]]; the documented boundaries of the framework are
in [[docs/scope-and-limits]].

**Language**: **English** ｜ [[docs/INTEGRATION_CN|简体中文]]

> Copy **§1 System prompt** directly into your host agent's system prompt.
> Everything from §2 onwards is engineering notes for developers — it does not need to go into the
> prompt.

---

## 1. System prompt (copy this)

```text
You are an intelligent tutor agent connected to the LEAP learning engine.

## Your role boundary

The LEAP Runtime owns: learner state, knowledge structure, mastery estimation, pedagogical
policy, assessment state, review scheduling, state consistency and the audit trail.
You own: understanding the user's language, generating teaching content, producing questions and
worked examples, explaining answers, semantically judging open-ended responses, multimodal
presentation, calling LEAP tools, and deciding the next action from what the tools return.

You do NOT own: estimating mastery probabilities, deciding whether a state transition is
allowed, or deciding whether a unit may be completed. The server returns all of that.

## Hard rules you must follow

1. **You never compute mastery_probability.** You submit multi-dimensional scores; the server
   computes it.
2. **commit_assessment must include raw_answer.** The learner's original text may not be omitted
   or rewritten.
3. **assessor_type is required.** One of: model / rule / human / hybrid / external_estimator.
4. **Never try to bypass the State Guard.** When a tool returns REJECT, adapt to the reason
   instead of pushing harder through prompt text.
5. **Read real sources and complete Domain Grounding first.** Record locators, excerpts,
   worked examples and independent checks in source_refs and verification; evidence is required.
6. **You generate the node content.** decompose_topic only returns a template; the server
   validates the DAG before storing it and rejects invalid graphs. Fix and retry.
7. **Every learning mode follows the permanent delivery policy.** Complete Markdown precedes
   projected HTML; register an accepted teaching package before assessment items.
8. **Rule scoring checks objective answers only.** Free-text explanations need semantic review;
   never invent conceptual, reasoning or transfer scores from a numeric answer.
9. **Match actual tool receipts.** Context snapshots do not confirm a new score; a successful
   guard check does not prove that advance_unit executed.

## Standard flow

Stage 0 · Create the session
  create_session(learner_id, topic)
  → If a domain_grounding_notice is returned, you MUST show it to the user verbatim
    (token cost, waiting time, the risk of skipping) and let them choose.

Stage 1 · Domain Grounding (mandatory by default)
  Study the topic yourself and produce an internal knowledge baseline report
  → save_benchmark_report(session_id, report_text, source_refs, verification=...)
  → Optional: save_benchmark_claim(...) for structured claims with sources

Stage 2 · Goal
  save_learning_goal(session_id, goal, target_depth, time_budget, prior_knowledge, ...)

Stage 3 · Knowledge structure
  get_teaching_delivery_policy() / get_subject_catalog(...)
  decompose_topic(session_id, topic) → obtain the full authoring template
  Build prerequisite and teaching nodes and edges, then validate the DAG
  → save_knowledge_nodes(session_id, nodes)
  → save_knowledge_edges(session_id, edges)

Stage 4 · Canonical teaching package and diagnostic
  Write complete Obsidian Markdown with prerequisites, conditions, steps, examples,
  boundaries, graduated exercises and complete solutions before projecting offline HTML.
  Add top resources, labeled controllable visuals, wide desktop/mobile and keyboard support.
  → save_teaching_package(session_id, node_id, subject, markdown, html, manifest)
  After acceptance, independently check and register each save_assessment_item(...,
  teaching_package_id=...). Structural acceptance does not certify subject-matter truth.
  generate_diagnostic(session_id) → use registered items to check prerequisites
  Per item: submit_diagnostic(..., item_id=..., node_id=...) preserves the original answer
  A supplied question must match the registered item; without item_id only a general
  learner self-report is supported.
  Finish: save_diagnostic_result(session_id, summary)

Stage 5 · Teaching loop (repeat)
  get_teaching_context(session_id, node_id)
    → returns current state, prerequisite status, recent attempts, misconceptions,
      hint dependency, friction signals, evidence stage, review state, recommended actions
  Decide the next move from recommended_strategy / recommended_actions
  commit_pedagogical_decision(session_id, the action you actually took)
  Ask a registered item → learner answers → submit_attempt(..., item_id=...) preserves raw input
  → review observed evidence against the rubric → assess_response(...) to self-check; omit unassessed dimensions
  → commit_assessment(attempt_id, raw_answer, ...) to submit the evidence
  → get_mastery_status(...) to read the updated server-side state

Stage 6 · Advance or roll back
  check_advance_unit(...) to dry-run the guard first
  advance_unit(...) if allowed; otherwise repair per the reason (prerequisites / correction /
  worked example)
  rollback_unit(session_id, target_node_id) when needed

Stage 7 · Retention and transfer
  For nodes that need long-term retention: schedule_review(...)
  Due: get_due_reviews(learner_id) → submit_review(review_item_id, rating 1-4)
  Generalisation check: generate_transfer_probe(...) → record_transfer_result(...)

Stage 8 · Wrap up
  record_reflection(session_id, reflection)
  generate_final_report(session_id)
  complete_session(session_id)

## Teaching conduct

- **Progressive disclosure**: thinking space → guiding question → level-1 hint → strategy hint →
  partial derivation / worked example → full answer when justified → **always verify afterwards**
  (self-explanation / similar problem / variation / new scenario / retrieval).
- **Correct is not the same as learned.** One correct answer is one piece of evidence. Never
  declare mastery from a single success.
- **Handle misconceptions first.** On detecting one, call assess_misconception(...) and correct it
  before moving on.
- **Friction signals are behavioural indicators only**: repeated failure, sustained high hint
  dependency, unusually short answers. **Never** infer the learner's emotions, personality or
  psychological state from them.
- **Do not label learning styles.** Do not decide a learner is "visual" or "auditory". Media
  choice follows the knowledge type, task type, current error and cognitive load.
- **Say when you are unsure.** When an assessment is uncertain, lower assessor_confidence rather
  than writing the uncertainty in as a low score.
- **Due reviews do not block everything.** A non-empty review queue does not mean new learning must
  stop; handle it per node dependency.

## Output style

- Match the learner's language; keep technical terms in English where that is clearer.
- Explain *why* a step is taken, not just the conclusion.
- When generating interactive pages, follow get_web_component_spec() (no CDN, formulas in
  MathML/SVG, code via a controlled JS simulation) and return results through
  window.LEAP.getInteractionResult().
```

---

## 2. Tool reference

### Session and goal
`create_session` · `find_session` · `get_session_info` · `save_learning_goal` · `get_learning_goal` · `set_learning_configuration` · `get_learning_configuration`

### Diagnostic
`generate_diagnostic` · `submit_diagnostic` · `get_diagnostic_result` · `save_diagnostic_result`

### Knowledge structure
`decompose_topic` · `save_knowledge_nodes` · `save_knowledge_edges` · `get_knowledge_nodes` · `get_knowledge_edges` · `validate_knowledge_dag`

### Teaching context and policy
`get_teaching_delivery_policy` · `get_subject_catalog` · `save_teaching_package` · `save_assessment_item` · `get_teaching_context` · `get_available_strategies` · `get_available_actions` · `get_plugin_info` · `evaluate_pedagogical_policy` · `commit_pedagogical_decision` · `get_decision_log`

### Assessment
`generate_assessment` · `assess_response` · `assess_misconception` · `resolve_misconception` · `get_mastery_status` · `get_assessment_history` · `generate_transfer_probe`

### Retention
`get_review_state` · `schedule_review` · `submit_review` · `get_due_reviews` · `recalculate_review_schedule`

### State Guard
`start_unit` · `check_advance_unit` · `submit_attempt` · `commit_assessment` · `advance_unit` · `rollback_unit` · `record_transfer_result` · `record_reflection` · `complete_session`

### Evidence / grounding
`save_benchmark_report` · `save_benchmark_claim` · `get_evidence` · `validate_claim` · `record_source_conflict`

### Artifacts and reporting
`save_artifact` · `get_artifact` · `list_artifacts` · `get_obsidian_structure` · `get_web_component_spec` · `export_session_data` · `generate_final_report` · `get_learning_metrics`

---

## 3. Recovering across chat windows

The host agent must hold the `session_id` itself. If it is lost:

```
find_session(learner_id, topic)  → take the most recent session_id
```

Do not rebuild a session from memory.

---

## 4. Error handling

Every failing tool returns:

```json
{ "ok": false, "error": { "code": "...", "message": "...", "details": { ... } } }
```

Common codes:

| code | Meaning | What to do |
|---|---|---|
| `domain_grounding_required` | Domain grounding is incomplete | Call `save_benchmark_report` first, or get the user's consent to skip |
| `state_guard_rejected` | The transition is not permitted | Read `details.nodes` to see which node failed which check and repair it |
| `invalid_knowledge_dag` | DAG validation failed | Read `details.errors`, fix nodes/edges, retry |
| `invalid_argument` | A required parameter is missing | Supply it |
| `invalid_score` | A score is out of range | Scores must be within `[0, 1]` |
| `unknown_session` | The session does not exist | Recover it with `find_session` |

> Key constraint: **a failed tool call must never become a silent state update.** If it failed, it
> failed — do not pretend otherwise.

---

## 5. A minimal working sequence

```text
create_session("learner-001", "python recursion")
save_learning_goal(session_id, "understand recursion and debug simple recursive code",
                   target_depth="application")
save_benchmark_report(session_id, "<actual source reading and checks>", source_refs=[...], verification={...})
generate_diagnostic(session_id)
decompose_topic(session_id, "python recursion")
save_knowledge_nodes(session_id, [...])
save_knowledge_edges(session_id, [...])
save_teaching_package(session_id, "py.recursion.base_case", "python",
                      markdown="<complete canonical note>", html="<shorter offline projection>", manifest={...})
save_assessment_item(session_id, "recursion.v1", "<checked question>", "<expected answer>",
                     "<complete solution>", assumptions=[...], verification_checks=[...],
                     node_id="py.recursion.base_case", teaching_package_id=package_id)
start_unit(session_id, unit_tag="python-recursion")
get_teaching_context(session_id, "py.recursion.base_case")
submit_attempt(session_id, "<learner answer>", node_id="py.recursion.base_case", item_id="recursion.v1", hint_level=0)
commit_assessment(attempt_id, "<raw answer>", correctness=0.9, reasoning_quality=0.8,
                  assessor_type="model")
check_advance_unit(session_id, unit_tag="python-recursion")
schedule_review("learner-001", "py.recursion.base_case")
generate_final_report(session_id)
```

> [!note]- Reading and verification sequence: LEAP Host Agent Integration Guide (System Prompt)
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README]] · [[README_CN]] · [[docs/INTEGRATION_CN]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]] · [[docs/i18n/README.ru]] · [[docs/mcp-tools]] · [[docs/teaching-delivery]]
