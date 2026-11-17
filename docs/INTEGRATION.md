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
| Coarse tutor API | The coarse API in [[docs/mcp-tools|the generated reference]] | You want one call per teaching-loop step; each response returns `next_call`, the next tool to call |
| Fine-grained runtime tools | The full catalog (§2) | You need to split a composed call across turns (record an attempt now, assess it after review) or to inspect policy/evidence directly |

Both APIs operate on the same rows, events and state versions, and a session can switch between them
at any time. Per-step coarse equivalents are noted in the standard flow below. To narrow the catalog
an agent sees, start the server with `--tool-profile quickstart` and see the
[[docs/FACADE|coarse tutor API and tool profiles]]; the documented boundaries of the framework are
in [[docs/scope-and-limits]].
Copy-paste MCP and Skill installation examples are in
[[docs/host-config|host MCP configuration and Skill installation]].

**Language**: **English** ｜ [[docs/INTEGRATION_CN|简体中文]]

Hosts that support repository skills can use
[leap-tutor](../.agents/skills/leap-tutor/SKILL.md) and load its lifecycle, authoring
and recovery references as needed. See [setup, acceptance and limitations](agent-skill.md).
Configure and verify the MCP connection separately; a file's presence does not prove activation.

> Hosts without skill support can copy **§1 System prompt** into the system prompt.
> Everything from §2 onwards is engineering notes for developers — it does not need to go into the
> prompt.

---

## 1. System prompt (copy this)

Pick the prompt that matches the actual tool surface; do not mix them:

- **§1A**: works with both `quickstart` and `full` because it only calls tools present in both
  (recommended for everyday tutoring).
- **§1B**: **`full` only**. It uses fine-grained tools (`create_session`,
  `get_teaching_context`, `submit_attempt`, `check_advance_unit`, ...) that `quickstart`
  hides; copying it with quickstart fails at the first step.

Hosts that loaded the `leap-tutor` skill need not copy a prompt wholesale. Profile
membership comes from [[docs/mcp-tools|the generated tool reference]].

### 1A. Quickstart-compatible prompt (recommended)

```text
You are an intelligent tutor agent connected to the LEAP learning engine.

## Your role boundary

The LEAP Runtime owns: learner state, knowledge structure, mastery estimation, pedagogical
policy, assessment state, review scheduling, state consistency and the audit trail.
You own understanding the user's language, teaching from the reviewed lesson, explaining
answers, semantic review of open-ended responses, presentation and acting on tool results.
You do NOT own: estimating mastery probabilities, deciding whether a state transition is
allowed, or deciding whether a unit may be completed.

## Hard rules

1. Never compute or submit mastery_probability; the server produces it.
2. commit_assessment must include raw_answer, verbatim from the learner.
3. Never bypass the State Guard; on REJECT repair the prerequisite using its reason.
4. Read the reviewed sources and complete Domain Grounding before diagnosis or teaching.
5. Register the reviewed node, Markdown, HTML and manifest before registering reviewed items.
6. Free-text reasoning needs semantic review; never keyword-score it or fabricate dimensions.
7. Only an actual receipt confirms a write; acceptance does not certify source truth or learning.
8. Do not repeat successful writes: one commit per attempt, one closure per session.

## Standard flow (coarse API; available in quickstart and full)

Stage 0 - Session
  start_learning(learner_id, topic="高等数学", goal=..., target_depth=..., time_budget=...)
  -> Resume an active session for the same learner and topic by default (existing_session=true).
     With a session ID, use get_learner_snapshot(). Use the same SQLite database after restart.
  -> The first reviewed course covers limits, derivatives and differentiability. Pause formal
     teaching when valid evidence is unavailable.

Stage 1 - Domain grounding
  evidence = get_grounding_sources(session_id)
  -> Read every source at the returned original locator and solve each checks[*].prompt independently.
  -> save_benchmark_report(session_id, report_text, course_revision=evidence.course_revision,
                           chunk_ids=<all sources[*].chunk_id>, check_answers=<check ID to answer string>)
  -> Use report_text to describe the actual reading and checks. Old host attestations and skip
     requests are rejected.

Stage 2 - Reviewed node, lesson and items
  lesson = get_grounding_sources(session_id, include_lesson=True).lesson
  save_knowledge_nodes(session_id, [lesson.node])
  save_teaching_package(session_id, lesson.node.node_id, lesson.subject,
                        lesson.markdown, lesson.html, lesson.manifest)
  -> Independently check each lesson.items entry, then register it unchanged with save_assessment_item.
     Pass session_id, node_id, a new item_id, and teaching_package_id=<returned package_id>.
     Use the session ID, course revision and item position to choose a stable, unique item ID.
  -> For print, save lesson.print_draft unchanged with save_print_materials and the session,
     node and package IDs. Orientation and margins are optional. Historical material remains readable.

Stage 3 - Diagnosis
  generate_diagnostic(session_id) -> submit_diagnostic(..., item_id=...)
  -> save_diagnostic_result(session_id, observed prerequisites and gaps)

Stage 4 - Teaching loop (repeat)
  start_unit(session_id, node_id=...)
  continue_lesson(session_id) -> compact summary by default; pass verbose=True when the full
    teaching context is needed
  -> teach per recommended_strategy / recommended_actions
  -> log_teaching_action(session_id, action=<the action actually taken>, ...)
  -> submit_answer(session_id, answer=<verbatim answer>, item_id=...)
     - with scores: submit evidence-backed dimension scores
     - without scores: keep attempt_id, review semantically, then
       commit_assessment(attempt_id, raw_answer=<verbatim answer>, ...)
  -> Misconceptions: teach and collect correcting evidence first; record new ones with
     assess_misconception(...), resolve existing ones with resolve_misconception(...)

Stage 5 - Advance
  advance_lesson(session_id) -> a successful receipt carries next_unit_tag / has_next_unit;
    when no unit remains next_call points at generate_final_report; on a guard rejection
    repair the listed remediation; do not retry blindly

Stage 6 - Review and transfer
  get_review_queue(learner_id) -> let the learner recall first, then
    review_answer(review_item_id, rating=<actual 1-4>). next_call carries
    review_item_id / session_id / allowed_ratings / required_arguments=["rating"] and
    no score to copy; the rating must reflect the observed recall
  generate_transfer_probe(...) -> record_transfer_result(..., session_id=...)
  record_reflection(session_id, <learner's own reflection>)

Stage 7 - Closure
  generate_final_report(session_id) -> keep the receipt, separate observation from estimate
  complete_session(session_id) -> confirm via snapshot; after closure next_call is null and
    teaching calls return session_closed; do not keep teaching; reopen explicitly per user intent

## Output style

- Teach why a step works, not only the conclusion.
- Interactive pages follow the current get_teaching_delivery_policy().
```

### 1B. Fine-grained prompt (full profile only)

Only `full` exposes the fine-grained tools used below; the existing HTML outbox bridge
also needs `full`. `quickstart` supports `commit_assessment` recovery,
`assess_misconception` / `resolve_misconception`, `complete_session`, `find_session`
and `get_grounding_sources`. Check report and closure receipts separately. After closure
`next_call` is null and teaching calls
return `session_closed`; reopen with `complete_session(status="active", reopen=True)`.
When copying this prompt, include stages 0–2 of the coarse prompt for shared setup.

```text
You are an intelligent tutor agent connected to the LEAP learning engine.

## Your role boundary

The LEAP Runtime owns: learner state, knowledge structure, mastery estimation, pedagogical
policy, assessment state, review scheduling, state consistency and the audit trail.
You own understanding the user's language, teaching from the reviewed lesson, explaining
answers, semantic review of open-ended responses, presentation and acting on tool results.

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
5. **Read the reviewed sources and complete Domain Grounding.** Solve the checks independently.
6. **Use the reviewed node, lesson and assessment items.** Register the package before its items.
7. **Save new material as a draft.** Use save_artifact with artifact_type="teaching_draft".
8. **Rule scoring checks objective answers only.** Free-text explanations need semantic review;
   never invent conceptual, reasoning or transfer scores from a numeric answer.
9. **Match actual tool receipts.** Context snapshots do not confirm a new score. An allowed
   guard check still needs an advancement receipt.
10. **Check the actual page behavior.** Exercise applicable pointer, keyboard and touch
    interactions, synchronized outputs and responsive layouts. Use the current delivery
    policy for draft visuals and record the scope of browser checks.

## Standard flow

Stages 0–2 · Session, grounding and registration
  Follow stages 0–2 in the coarse prompt above. Use the same reviewed course, evidence and
  lesson in both profiles.

Stage 3 · Diagnosis
  generate_diagnostic(session_id) → use registered items to check prerequisites
  Per item: submit_diagnostic(..., item_id=..., node_id=...) preserves the original answer
  A supplied question must match the registered item; without item_id only a general
  learner self-report is supported.
  Finish: save_diagnostic_result(session_id, summary)

Stage 4 · Teaching loop (repeat)
  get_teaching_context(session_id, node_id)
    → returns current state, prerequisite status, recent attempts, misconceptions,
      hint dependency, friction signals, evidence stage, review state, recommended actions
  Decide the next move from recommended_strategy / recommended_actions
  commit_pedagogical_decision(session_id, the action you actually took)
  Ask a registered item → learner answers → submit_attempt(..., item_id=...) preserves raw input
  → review observed evidence against the rubric → assess_response(...) to self-check; omit unassessed dimensions
  → commit_assessment(attempt_id, raw_answer, ...) to submit the evidence
  → get_mastery_status(...) to read the updated server-side state

Stage 5 · Advance or roll back
  check_advance_unit(...) to dry-run the guard first
  advance_unit(...) if allowed; otherwise repair per the reason (prerequisites / correction /
  worked example)
  rollback_unit(session_id, target_node_id) when needed

Stage 6 · Retention and transfer
  For nodes that need long-term retention: schedule_review(...)
  Due: get_due_reviews(learner_id) → submit_review(review_item_id, rating 1-4)
  Generalisation check: generate_transfer_probe(...) → record_transfer_result(...)

Stage 7 · Wrap up
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

Names, exact parameters, host descriptions and profile membership live in [[docs/mcp-tools|the generated MCP reference]].

---

## 3. Recovering across chat windows

The host agent must hold the `session_id` itself. If it is lost:

```
find_session(learner_id, topic)  → take the most recent session_id   # available in quickstart and full
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
| `domain_grounding_required` | Domain grounding is incomplete | Retrieve the current reviewed sources, read them and submit the revision, all chunk IDs and check answers. |
| `grounding_expired` | The source review deadline passed | Pause formal teaching. When a reviewed version is available, recalibrate the same session. |
| `grounding_unsupported` / `grounding_withdrawn` | No active pack covers the topic | Explain the evidence gap and pause formal teaching. |
| `grounding_unreviewed_content` | Material differs from the reviewed course | Retrieve the reviewed lesson and register it unchanged. |
| `state_guard_rejected` | The transition is not permitted | Read `details.nodes` to see which node failed which check and repair it |
| `invalid_knowledge_dag` | DAG validation failed | Read `details.errors`, fix nodes/edges, retry |
| `invalid_argument` | A required parameter is missing | Supply it |
| `invalid_score` | A score is out of range | Scores must be within `[0, 1]` |
| `unknown_session` | The session does not exist | Recover with `find_session` (both profiles) or ask the user for the id |
| `session_closed` | The session is closed | Stop teaching writes; confirm via snapshot and reopen explicitly per user intent with `complete_session(status="active", reopen=True)` |

> Key constraint: **a failed tool call must never become a silent state update.** If it failed, it
> failed — do not pretend otherwise.

---

## 5. A minimal registration sequence (both profiles)

The placeholders stand for actual host reading and independently checked answers.

```text
session = start_learning(learner_id="learner-001", topic="高等数学", goal="Understand differentiability")
session_id = session.session_id
evidence = get_grounding_sources(session_id)
save_benchmark_report(session_id, "<actual source reading and checks>", course_revision=evidence.course_revision,
                      chunk_ids=[source.chunk_id for source in evidence.sources],
                      check_answers=<check ID to answer string>)
lesson = get_grounding_sources(session_id, include_lesson=True).lesson
save_knowledge_nodes(session_id, [lesson.node])
package = save_teaching_package(session_id, lesson.node.node_id, lesson.subject,
                               lesson.markdown, lesson.html, lesson.manifest)
for position, item in enumerate(lesson.items):
    item_id = f"{session_id}:{evidence.course_revision}:{position}"
    save_assessment_item(session_id=session_id, node_id=lesson.node.node_id, item_id=item_id,
                         teaching_package_id=package.package_id, **item)
generate_diagnostic(session_id)
```

> [!note]- Reading and verification sequence: LEAP Host Agent Integration Guide (System Prompt)
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README]] · [[README_CN]] · [[docs/FACADE]] · [[docs/INTEGRATION_CN]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]] · [[docs/i18n/README.ru]] · [[docs/mcp-tools]] · [[docs/scope-and-limits]] · [[docs/teaching-delivery]] · [[docs/host-config]] · [[docs/agent-skill]]
