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

Related: [[Knowledge_Index]] · [[docs/INTEGRATION]] · [[docs/mcp-tools]] · [[docs/FACADE_CN]] · [[docs/scope-and-limits]] · [[README]] · [[docs/host-config]]

# Coarse tutor API and tool profiles

The runtime surface is fine-grained on purpose: every state change is its own auditable tool
call, and the State Guard stays the only component that may authorise a transition. The cost of
that design lands on the host agent - a single teaching turn can need six or more correctly
ordered calls, and ordering mistakes are the most common integration failure.

This page documents the two things that remove most of that cost: the **coarse tutor API** (eight
tools that compose the fine-grained ones server-side) and **tool profiles** (a `quickstart`
catalog limited to the tools needed for the ordinary teaching workflow).

## 1. The coarse tutor API

Each coarse tool calls the same runtime method as its fine-grained equivalent. It is a facade,
not a second state machine, so coarse and fine calls can be mixed inside one session.

See [[docs/mcp-tools|the generated reference]] for coarse tool names, composition semantics, signatures and profile membership.

Every response carries `next_call`: the single next tool call to make, with its arguments and the
reason. The facade therefore guides the agent instead of requiring it to memorise the lifecycle.
`next_call` only guarantees that the target tool exists in the current profile; arguments that
encode a semantic decision (for example a review rating: `next_call` supplies `review_item_id`,
`session_id` and `allowed_ratings` but no score to copy) must come from the real observation.
After a session is closed, `next_call` is null.

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
- **Delivery policy 3.0 still applies.** Responses use a compact envelope carrying only
  `policy_version`; fetch the full policy once with `get_teaching_delivery_policy()` and do not
  quote it from memory.
- **Grounding and item gates apply to both profiles.** Calls such as `submit_answer`
  and `continue_lesson` require current reviewed evidence and the reviewed package.

### Two valid shapes of `submit_answer`

With scores it stores the attempt *and* commits the assessment in one call. Without scores it
stores only the attempt and returns `next_call` pointing at `commit_assessment`, which is the
correct mode when free-text reasoning still needs your semantic review. Never derive scores from
keywords.

Both profiles expose `commit_assessment`: preserve the returned `attempt_id`, fix
the reported cause and commit the original answer and supported scores without
recording another attempt. Both also expose `assess_misconception` (record a new
misconception) and `resolve_misconception`, so the facade's misconception branch has
executable steps in each direction. Collect correction evidence before marking a
misconception resolved.

Use `get_grounding_sources` to retrieve the approved source locators and checks, then
complete calibration and register the reviewed lesson as described in [[docs/INTEGRATION]].
The first pack covers limits, derivatives and differentiability in `topic="高等数学"`.
Formal teaching pauses when evidence is missing, withdrawn or expired.

`start_learning` resumes an active session for the same learner+topic by default
(`existing_session=true`); pass `force_new=True` only when a second session is really
intended. The `get_review_queue` next_call supplies `review_item_id`, `session_id`,
`allowed_ratings` and `required_arguments=["rating"]` but no score to copy.

### Reports and closure

`generate_final_report` generates and saves a report; `complete_session` changes
session status. Confirm the report receipt, then close and check `session_status`
with `get_learner_snapshot`. Report success and closure failure separately.
Repeated closure is idempotent and does not emit another completion event;
`request_id` is an audit/idempotency correlation, never a substitute for a receipt.
After closure `next_call` is null and teaching calls return `session_closed`; stop
teaching and reopen explicitly per user intent with
`complete_session(status="active", reopen=True)`.

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
  → advanced: true · next_unit_tag: ... · has_next_unit: true · next_call: continue_lesson
    (next_call points at generate_final_report when no unit remains)
get_learner_snapshot(session_id)
  → node_states: [...] · due_review_count: 2 · setup_gaps: []
```

## 2. Tool profiles

A profile decides how much of the catalog an MCP client sees. Registration is identical in every
profile, so the runtime keeps every capability and switching profiles needs no migration.

| Profile | Contents |
|---|---|
| `quickstart` | 36 tools: coarse tutor API, reviewed-source calibration, DAG, reviewed registers for lessons and items, diagnosis, assessment recovery, misconceptions, transfer, reflection, reports and closure |
| `full` | 75 tools (the default), including detailed evidence reads, teaching drafts and page bridging |

Counts and per-tool membership come from the [[docs/mcp-tools|generated reference]].
Check the host's actual catalog for `next_call` and its follow-ups. The existing
HTML outbox bridge and fine-grained evidence reads need `full`; session lookup with
`find_session` works in both profiles. If quickstart cannot
confirm a specific write after an uncertain result, stop that write and obtain
the required read capability before retrying. For repository-skill hosts, see
[leap-tutor setup and acceptance](agent-skill.md); copy-paste MCP/Skill configuration
is in [[docs/host-config|host configuration]].

Response cost: after the fix every call carries only a compact `policy_version`;
fetch the full delivery policy once with `get_teaching_delivery_policy()`.
`continue_lesson()` returns only the current-node summary by default; pass
`verbose=True` when the full teaching context is needed. `quickstart` additionally
cuts the one-off tool schema from about 54 KB to about 26 KB.

Selection order:

```bash
python -m leap.server --tool-profile quickstart   # explicit flag
LEAP_TOOL_PROFILE=quickstart python -m leap.server # environment
# or set `tool_profile: quickstart` in config/default.yaml
```

An unknown profile name is refused at startup instead of silently widening the surface to `full`.

### Profile membership

The [[docs/mcp-tools|generated tool reference]] lists profile membership for every tool. Fine-grained
policy inspection and lower-level teaching operations remain available in `full`.

## 3. Verifying a coarse integration

Run the checks in [[CONTRIBUTING|the contributing guide]]; `python -m leap.doctor` checks installation and catalog availability.

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

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README]] · [[docs/FACADE_CN]] · [[docs/INTEGRATION]] · [[docs/scope-and-limits]] · [[docs/host-config]] · [[docs/agent-skill]]
