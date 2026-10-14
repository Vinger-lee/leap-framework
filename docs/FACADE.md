---
title: "Coarse tutor API and tool profiles"
tags: ["leap", "integration", "reference"]
aliases: ["Coarse tutor API and tool profiles guide"]
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP coarse tutor API facade next_call tool profiles foundations definitions workflow`
> Extension: `LEAP coarse tutor API facade next_call tool profiles failure cases examples comparison`
> Advanced: `LEAP coarse tutor API facade next_call tool profiles invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/INTEGRATION]] · [[docs/mcp-tools]] · [[docs/FACADE_CN]] · [[docs/scope-and-limits]] · [[README]]

# Coarse tutor API and tool profiles

The runtime surface is fine-grained on purpose: every state change is its own auditable tool
call, and the State Guard stays the only component that may authorise a transition. The cost of
that design lands on the host agent - a single teaching turn can need six or more correctly
ordered calls, and ordering mistakes are the most common integration failure.

This page documents the two things that remove most of that cost: the **coarse tutor API** (eight
tools that compose the fine-grained ones server-side) and **tool profiles** (a `quickstart`
catalog of about twenty-five tools instead of seventy).

## 1. The coarse tutor API

Each coarse tool calls the same runtime method as its fine-grained equivalent. It is a facade,
not a second state machine, so coarse and fine calls can be mixed inside one session.

| Coarse tool | Composes | Use it for |
|---|---|---|
| `start_learning` | `create_session` + `save_learning_goal` + `set_learning_configuration` | Opening turn: "I want to learn X" |
| `continue_lesson` | `get_teaching_context` + `get_session_info` | One read that returns state and the recommended next action |
| `log_teaching_action` | `commit_pedagogical_decision` | Recording the action you actually took |
| `submit_answer` | `submit_attempt` + `commit_assessment` + `get_mastery_status` | The learner answered something |
| `advance_lesson` | `check_advance_unit` + `advance_unit` | Advancing, with the guard dry-run built in |
| `get_review_queue` | `get_due_reviews` | What is due for spaced review |
| `review_answer` | `submit_review` | Applying a 1-4 FSRS rating |
| `get_learner_snapshot` | `get_session_info` + `get_mastery_status` + `get_knowledge_nodes` + `get_due_reviews` | Reconnecting a chat window, reporting progress, debugging |

Every response carries `next_call`: the single next tool call to make, with its arguments and the
reason. The facade therefore guides the agent instead of requiring it to memorise the lifecycle.

### What the facade does not change

- **The State Guard keeps the authority.** `advance_lesson` dry-runs the guard first and returns
  `advanced: false` plus the failed check and the repair action when the transition is refused.
  Nothing is written unless the guard allowed it, and a refusal is never an error to retry through
  prompt text.
- **Failures stay failures.** A failed step returns
  `{"ok": false, "error": { "code", "message", "details" }}`. When the second half of
  `submit_answer` fails, the response names `failed_step` and carries the stored `attempt_id`, so
  the host fixes the cause and calls `commit_assessment` directly instead of losing the answer.
- **The raw answer is still stored verbatim** and reused as `raw_answer`, which removes the usual
  mismatch error between attempt and assessment.
- **Mastery is still estimated server-side.** `mastery_probability` is never accepted from the
  agent, and the configured estimator remains the only producer of that number.
- **Delivery policy 3.0 still applies.** The coarse envelope carries the versioned policy once;
  nested sub-responses have their duplicate copy removed.
- **Grounding and item gates still apply.** `submit_answer` and `continue_lesson` fail with
  `domain_grounding_required` exactly like the fine-grained tools do.

### Two valid shapes of `submit_answer`

With scores it stores the attempt *and* commits the assessment in one call. Without scores it
stores only the attempt and returns `next_call` pointing at `commit_assessment`, which is the
correct mode when free-text reasoning still needs your semantic review. Never derive scores from
keywords.

```text
# One teaching turn, coarse path
continue_lesson(session_id, "py.recursion.base_case")
  → evidence_stage: practiced · mastery_probability: 0.62 · hint_dependency: 0.25
  → recommended_strategy: Retrieval Practice · next_call: log_teaching_action
log_teaching_action(session_id, action="Generate Retrieval Item", strategy="Retrieval Practice")
submit_answer(session_id, "<learner answer>", node_id="py.recursion.base_case",
              item_id="recursion.v1", correctness=1.0, reasoning_quality=0.9)
  → assessed: true · stage_after: demonstrated · next_call: advance_lesson
advance_lesson(session_id, unit_tag="python-recursion")
  → advanced: true · next_node_id: py.recursion.recursive_case
get_learner_snapshot(session_id)
  → node_states: [...] · due_review_count: 2 · setup_gaps: []
```

## 2. Tool profiles

A profile decides how much of the catalog an MCP client sees. Registration is identical in every
profile, so the runtime keeps every capability and switching profiles needs no migration.

| Profile | Tools | Contents |
|---|---|---|
| `quickstart` | 25 | The coarse tutor API plus the setup tools a complete lesson needs: grounding, the knowledge DAG, the canonical teaching package, registered items, diagnosis, transfer, reflection and the closing report |
| `full` | 70 | Every registered tool (the default) |

Selection order:

```bash
python -m leap.server --tool-profile quickstart   # explicit flag
LEAP_TOOL_PROFILE=quickstart python -m leap.server # environment
# or set `tool_profile: quickstart` in config/default.yaml
```

An unknown profile name is refused at startup instead of silently widening the surface to `full`.

### Which tools stay hidden in `quickstart`

Fine-grained variants of the coarse loop (`submit_attempt`, `commit_assessment`, `advance_unit`,
`check_advance_unit`, `commit_pedagogical_decision`, `get_teaching_context`, `schedule_review`,
`submit_review`, `get_due_reviews`), the policy introspection tools, and the artifact/reporting
tools that a lesson does not need per turn. They remain available in `full`, and a host agent can
switch to `full` mid-project without losing state.

## 3. Verifying a coarse integration

```bash
pytest -q tests/test_facade.py tests/test_tool_profiles.py   # composition and profile filtering
python -m leap.doctor                                        # installation and catalog self-check
python -m leap.server --tool-profile quickstart              # the narrowed catalog, for real
```

The facade tests assert the properties above, not just the happy path: a refused advance changes
nothing, a failed assessment keeps the attempt recoverable, an unrecognised learning mode is
reported back, and the grounding gate still fires.

## 4. When to use the fine-grained tools

Use them when you need to move the two halves of a coarse call to different moments - recording an
attempt now and assessing it after a human review, or evaluating several candidate actions before
committing one. Both APIs operate on the same rows, events and versions.

> [!note]- Reading and verification sequence: LEAP coarse tutor API facade next_call tool profiles
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

