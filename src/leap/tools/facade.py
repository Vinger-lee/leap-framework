"""Coarse-grained tutor API: a facade over the fine-grained runtime tools.

Why this module exists
----------------------
The runtime surface is deliberately fine-grained: every state change is its own
auditable tool call, and the State Guard stays the only component that may
authorise a transition. That design is right for auditing, but it pushes a long,
order-sensitive sequence onto the host agent - one teaching turn easily costs
six or more calls, and getting the order wrong is the most common integration
failure.

The facade composes those calls **server-side**. Every step below calls exactly
the runtime method the fine-grained tool calls, so:

* no invariant is relaxed - State Guard checks, evidence rules, the mandatory
  domain-grounding gate and the "a failed call never becomes a silent state
  update" rule all still hold;
* the learner's original answer is still stored verbatim, and mastery is still
  estimated server-side by the configured estimator (never sent by the agent);
* each response carries ``next_call`` - the single next tool call to make - so
  the coarse path guides the agent instead of requiring it to memorise the
  lifecycle.

Coarse and fine tools are interchangeable inside one session. A host agent may
call ``submit_answer`` on one turn and ``commit_assessment`` on the next; the
facade is a convenience layer, not a second state machine.
"""

from __future__ import annotations

from typing import Any, Mapping

from leap.tools.base import LeapToolMixin, ToolError

__all__ = ["FacadeTools", "LIFECYCLE_NEXT_CALL"]


#: The lifecycle step reported by ``get_session_info`` mapped to the next call.
#: This is orientation text for the host agent - the runtime state, the Policy
#: engine and the State Guard remain authoritative.
LIFECYCLE_NEXT_CALL: dict[str, dict[str, Any]] = {
    "domain_grounding": {
        "tool": "save_benchmark_report",
        "why": (
            "Domain Grounding is mandatory unless the session allows skipping it. "
            "Read authoritative sources yourself and record them with verification."
        ),
    },
    "knowledge_representation": {
        "tool": "decompose_topic",
        "follow_up": ["save_knowledge_nodes", "save_knowledge_edges", "validate_knowledge_dag"],
        "why": "No knowledge node exists yet, so there is nothing to teach or assess.",
    },
    "diagnostic": {
        "tool": "generate_diagnostic",
        "follow_up": ["submit_diagnostic", "save_diagnostic_result"],
        "why": "The knowledge structure exists but the learner has no initial state yet.",
    },
    "teaching": {
        "tool": "continue_lesson",
        "why": "The session is ready for the teaching loop.",
    },
}

#: State Guard check name -> the repair action that follows a failed check.
#: Names come from ``StateGuard.check_node``; a failed check is never a retry
#: signal, it is an instruction to change what you do next.
GUARD_REMEDIATION: dict[str, str] = {
    "prerequisites_met": "Teach or repair the unmet prerequisite nodes first (unmet list is in details).",
    "assessment_sufficient": "Record an assessed attempt for the node - a guard needs real evidence, not a retry.",
    "evidence_sufficient": (
        "Evidence stage is below 'demonstrated': collect unassisted successes, a transfer probe "
        "or a spaced review before advancing."
    ),
    "transfer_completed": "Run the required transfer probe and record its result above the pass score.",
    "current_state_version_valid": "The state moved on: re-read the learner state, then decide again.",
}


class FacadeTools(LeapToolMixin):
    """Coarse-grained wrappers: one call per teaching-loop step."""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _lean(result: Mapping[str, Any]) -> dict:
        """Drop the delivery-policy copy nested inside a composed response.

        Every sub-response carries the versioned policy; the facade envelope
        carries it once, so the nested copies are removed to keep the payload
        small instead of repeating the same policy N times.
        """
        data = dict(result)
        data.pop("teaching_delivery_policy", None)
        return data

    def _next_call_for_step(self, session_id: str) -> dict[str, Any]:
        info = self._lean(self.get_session_info(session_id))
        step = info.get("next_step")
        guidance = dict(LIFECYCLE_NEXT_CALL.get(step, LIFECYCLE_NEXT_CALL["teaching"]))
        guidance["lifecycle_step"] = step
        return guidance

    # ------------------------------------------------------------------
    # 1. session start
    # ------------------------------------------------------------------
    def start_learning(
        self,
        learner_id: str,
        topic: str,
        *,
        goal: str | None = None,
        target_depth: str | None = None,
        target_domain: str | None = None,
        target_outcome: str | None = None,
        time_budget: int | None = None,
        prior_knowledge: str | None = None,
        constraints: str | None = None,
        mode: str | None = None,
        allow_skip_domain_grounding: bool | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Start a learning session, record its goal and pick a learning mode in one call.

        Coarse equivalent of ``create_session`` + ``save_learning_goal`` +
        ``set_learning_configuration``. Use it for the common opening turn; call
        the fine-grained tools instead when you need to create the session and
        the goal at different moments.

        ``goal`` and friends are optional: with no goal text the session is
        still created and the response says so. ``mode`` accepts the learner's
        own words ("我要准备考试") or a mode name.

        The response returns ``next_call`` - the next tool to call - and, when
        ``domain_grounding_notice`` is present, you must show it to the learner
        verbatim before the grounding stage starts.
        """
        session = self._lean(
            self.create_session(
                learner_id,
                topic,
                allow_skip_domain_grounding=allow_skip_domain_grounding,
                request_id=request_id,
            )
        )
        session_id = session["session_id"]

        goal_saved = False
        if any(
            value is not None
            for value in (
                goal, target_domain, target_outcome, target_depth,
                time_budget, prior_knowledge, constraints,
            )
        ):
            self.save_learning_goal(
                session_id,
                goal,
                target_domain=target_domain,
                target_outcome=target_outcome,
                target_depth=target_depth,
                time_budget=time_budget,
                prior_knowledge=prior_knowledge,
                constraints=constraints,
                request_id=request_id,
            )
            goal_saved = True

        learning_mode = None
        mode_notice = None
        if mode:
            configuration = self._lean(self.set_learning_configuration(session_id, request=mode))
            learning_mode = configuration.get("mode")
            if configuration.get("unrecognised"):
                mode_notice = (
                    "The requested mode was not recognised and the session kept its default: "
                    f"{configuration['unrecognised']}"
                )

        next_call = self._next_call_for_step(session_id)
        return self.ok(
            session_id=session_id,
            learner_id=learner_id,
            topic=topic,
            goal_saved=goal_saved,
            learning_mode=learning_mode,
            mode_notice=mode_notice,
            domain_grounding_stage=session.get("domain_grounding_stage"),
            domain_grounding_notice=session.get("domain_grounding_notice"),
            allow_skip_domain_grounding=session.get("allow_skip_domain_grounding"),
            next_step=next_call.get("lifecycle_step"),
            next_call=next_call,
            coarse_of=["create_session", "save_learning_goal", "set_learning_configuration"],
            guidance=(
                "Show domain_grounding_notice verbatim when it is present, then follow next_call. "
                "Do not invent a benchmark report: record what you actually read."
            ),
        )

    # ------------------------------------------------------------------
    # 2. teaching turn
    # ------------------------------------------------------------------
    def continue_lesson(self, session_id: str, node_id: str | None = None) -> dict:
        """Return the current teaching state and the next action in one call.

        Coarse equivalent of ``get_teaching_context`` (+ ``get_session_info``).
        The response keeps the runtime's own recommendation,
        ``recommended_strategy`` / ``recommended_actions``, together with the
        evidence stage, friction signals, active misconceptions and the due
        review count, so one call is enough to decide the next move.

        The facade never chooses the pedagogy for you: it reports what the
        configured policy engine recommends and which call to make next.
        """
        self.require_session(session_id)
        context = self._lean(self.get_teaching_context(session_id, node_id))
        current_node = context.get("current_node") or {}
        knowledge_state = context.get("knowledge_state") or {}

        next_call: dict[str, Any]
        due_reviews = context.get("due_review_count") or 0
        misconceptions = context.get("misconceptions") or []
        if misconceptions:
            next_call = {
                "tool": "resolve_misconception",
                "why": "An active misconception must be corrected before new material is added.",
            }
        elif due_reviews:
            next_call = {
                "tool": "get_review_queue",
                "why": "Spaced reviews are due; they do not block new learning globally, but they are evidence.",
            }
        else:
            next_call = {
                "tool": "log_teaching_action",
                "then": "submit_answer",
                "why": "Log the action you actually take, then record the learner's answer against it.",
            }

        return self.ok(
            session_id=session_id,
            node_id=context.get("node_id") or current_node.get("node_id"),
            current_node_title=current_node.get("title"),
            evidence_stage=knowledge_state.get("evidence_stage", "estimated"),
            mastery_probability=knowledge_state.get("mastery_probability"),
            hint_dependency=knowledge_state.get("hint_dependency"),
            recommended_strategy=context.get("recommended_strategy"),
            recommended_actions=context.get("recommended_actions"),
            recommendation_reason=context.get("recommendation_reason"),
            learning_friction=context.get("learning_friction"),
            prerequisite_state=context.get("prerequisite_state"),
            transfer_requirement=context.get("transfer_requirement"),
            active_misconceptions=misconceptions,
            due_review_count=due_reviews,
            learning_mode=context.get("learning_mode"),
            next_call=next_call,
            coarse_of=["get_teaching_context", "get_session_info"],
            teaching_context=context,
        )

    def log_teaching_action(
        self,
        session_id: str,
        *,
        action: str | None = None,
        strategy: str | None = None,
        node_id: str | None = None,
        rationale: str | None = None,
        expected_outcome: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Record the teaching action you actually took (section 27.1).

        Coarse equivalent of ``commit_pedagogical_decision``. Omit
        ``action``/``strategy`` to record the runtime's own recommendation, so
        the decision log is never empty. Pass the action you *did* take - the
        log exists to make the teaching decision auditable, not to flatter the
        recommendation.
        """
        decision = self._lean(
            self.commit_pedagogical_decision(
                session_id,
                strategy,
                action,
                node_id=node_id,
                rationale=rationale,
                expected_outcome=expected_outcome,
                request_id=request_id,
            )
        )
        return self.ok(
            session_id=session_id,
            decision_id=decision.get("decision_id"),
            recorded_action=(decision.get("decision") or {}).get("selected_action"),
            recorded_strategy=(decision.get("decision") or {}).get("selected_strategy"),
            decision=decision.get("decision"),
            next_call={"tool": "submit_answer", "why": "Record the learner's answer for this action."},
            coarse_of=["commit_pedagogical_decision"],
        )

    # ------------------------------------------------------------------
    # 3. answer + assessment
    # ------------------------------------------------------------------
    def submit_answer(
        self,
        session_id: str,
        answer: str,
        *,
        item_id: str | None = None,
        node_id: str | None = None,
        hint_level: int = 0,
        response_time: float | None = None,
        correctness: float | None = None,
        conceptual_understanding: float | None = None,
        reasoning_quality: float | None = None,
        application: float | None = None,
        transfer: float | None = None,
        hint_dependency: float | None = None,
        assessor_type: str = "model",
        assessor_confidence: float = 1.0,
        confidence: float | None = None,
        expected_state_version: int | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Record the learner's answer and commit your assessment in one call.

        Coarse equivalent of ``submit_attempt`` + ``commit_assessment`` (plus a
        read-back of the updated state). The raw answer is stored verbatim and
        reused as ``raw_answer``, which removes the most common integration
        error: committing an assessment whose text does not match the attempt.

        With no score supplied the attempt is stored and nothing is committed -
        use that mode when free-text reasoning still needs your semantic review,
        then call ``commit_assessment`` yourself.

        ``mastery_probability`` is never accepted from you: it is computed
        server-side from the evidence you submit.
        """
        attempt = self._lean(
            self.submit_attempt(
                session_id,
                answer,
                item_id=item_id,
                node_id=node_id,
                hint_level=hint_level,
                response_time=response_time,
                request_id=request_id,
            )
        )
        attempt_id = attempt["attempt_id"]
        resolved_node = attempt.get("node_id")

        scores = {
            "correctness": correctness,
            "conceptual_understanding": conceptual_understanding,
            "reasoning_quality": reasoning_quality,
            "application": application,
            "transfer": transfer,
            "hint_dependency": hint_dependency,
        }
        supplied = {key: value for key, value in scores.items() if value is not None}
        if not supplied:
            return self.ok(
                session_id=session_id,
                attempt_id=attempt_id,
                node_id=resolved_node,
                assessed=False,
                next_call={
                    "tool": "commit_assessment",
                    "arguments": {"attempt_id": attempt_id, "raw_answer": answer},
                    "why": "The attempt is stored. Review the answer yourself and commit the scores.",
                },
                coarse_of=["submit_attempt"],
                guidance=(
                    "No score was supplied, so nothing was committed. Free-text reasoning needs "
                    "your semantic review; never derive scores from keywords."
                ),
            )

        try:
            assessment = self._lean(
                self.commit_assessment(
                    attempt_id,
                    answer,
                    assessor_type=assessor_type,
                    assessor_confidence=assessor_confidence,
                    confidence=confidence,
                    expected_state_version=expected_state_version,
                    request_id=request_id,
                    **supplied,
                )
            )
        except ToolError as exc:
            # The attempt is already stored. Keep it recoverable instead of
            # hiding the failure: the host fixes the cause and commits directly.
            raise ToolError(
                exc.code,
                exc.message,
                {
                    **exc.details,
                    "attempt_id": attempt_id,
                    "failed_step": "commit_assessment",
                    "facade_hint": (
                        "The learner's attempt is stored. Fix the reported problem and call "
                        "commit_assessment(attempt_id, raw_answer=...) directly - do not record "
                        "the answer again."
                    ),
                },
            ) from exc

        state = self._lean(self.get_mastery_status(session_id, resolved_node)) if resolved_node else {}
        return self.ok(
            session_id=session_id,
            attempt_id=attempt_id,
            node_id=resolved_node,
            assessed=True,
            assessment=assessment,
            learner_state=state.get("learner_state"),
            misconception_ids=state.get("misconception_ids"),
            next_call={
                "tool": "advance_lesson" if self._advance_ready(state) else "continue_lesson",
                "why": (
                    "Enough evidence is recorded for the guard; dry-run the advance."
                    if self._advance_ready(state)
                    else "Keep teaching: read the updated state before the next move."
                ),
            },
            coarse_of=["submit_attempt", "commit_assessment", "get_mastery_status"],
        )

    @staticmethod
    def _advance_ready(state: Mapping[str, Any]) -> bool:
        """True when the recorded state looks ready for a guard dry-run.

        This is orientation only. The State Guard decides, and ``advance_lesson``
        always re-checks before it changes anything.
        """
        learner_state = state.get("learner_state") or {}
        stage = learner_state.get("evidence_stage")
        mastery = learner_state.get("mastery_probability")
        return stage in {"demonstrated", "retained", "transferred"} or (
            isinstance(mastery, (int, float)) and mastery >= 0.8
        )

    # ------------------------------------------------------------------
    # 4. advance / rollback
    # ------------------------------------------------------------------
    def advance_lesson(
        self,
        session_id: str,
        *,
        unit_tag: str | None = None,
        node_id: str | None = None,
        manual_override: bool = False,
        request_id: str | None = None,
    ) -> dict:
        """Dry-run the State Guard and advance only if it allows the transition.

        Coarse equivalent of ``check_advance_unit`` + ``advance_unit``. A
        rejection is **not** an error: the response returns
        ``advanced: false`` together with the guard's own reason and the repair
        action, so the host agent can react to the reason instead of retrying.
        Nothing is written unless the guard allowed it.
        """
        self.require_session(session_id)
        check = self._lean(
            self.check_advance_unit(
                session_id, unit_tag=unit_tag, node_id=node_id, manual_override=manual_override
            )
        )
        guard = check.get("guard") or {}
        allowed = guard.get("decision") == "ALLOW"
        if not allowed:
            reason = guard.get("reason") or "the State Guard did not allow this transition"
            return self.ok(
                session_id=session_id,
                unit_tag=check.get("unit_tag"),
                advanced=False,
                guard_allowed=False,
                guard=guard,
                remediation=self._remediation(guard),
                next_call={
                    "tool": "continue_lesson",
                    "why": reason,
                },
                coarse_of=["check_advance_unit"],
                guidance=(
                    "The transition was not permitted and no state changed. Repair the reason "
                    "listed in `guard` and try again; never work around the guard in prompt text."
                ),
            )

        result = self._lean(
            self.advance_unit(
                session_id,
                unit_tag=unit_tag,
                node_id=node_id,
                manual_override=manual_override,
                request_id=request_id,
            )
        )
        return self.ok(
            session_id=session_id,
            unit_tag=result.get("unit_tag"),
            advanced=True,
            guard_allowed=True,
            next_node_id=result.get("next_node_id"),
            state_version=result.get("state_version"),
            guard=result.get("guard"),
            next_call={
                "tool": "continue_lesson",
                "why": "Teach the node the guard released.",
            },
            coarse_of=["check_advance_unit", "advance_unit"],
        )

    def _remediation(self, guard: Mapping[str, Any]) -> list[str]:
        """Map the guard's failed checks to the repair action that follows.

        The unit-level decision nests one decision per node; the checks are
        plain booleans on each nested dict (``prerequisites_met`` and friends).
        Boolean checks that describe the request rather than the state -
        ``transfer_required``, ``manual_override``, ``all_nodes_pass`` - are
        skipped: they are not failures to repair.
        """
        ignored = {"transfer_required", "manual_override", "all_nodes_pass", "node_count"}
        reasons: list[str] = []

        def collect(decision: Mapping[str, Any], prefix: str) -> None:
            for name, passed in decision.items():
                if not isinstance(passed, bool) or passed or name in ignored:
                    continue
                remedy = GUARD_REMEDIATION.get(name, f"Repair the failing check: {name}.")
                reasons.append(f"{prefix}{remedy}")

        nodes = ((guard.get("details") or {}).get("nodes")) or {}
        if nodes:
            for node_id, decision in nodes.items():
                if isinstance(decision, dict) and decision.get("decision") != "ALLOW":
                    collect(decision, f"{node_id}: ")
        else:
            collect(guard, "")
        if not reasons and guard.get("reason"):
            reasons.append(str(guard["reason"]))
        return reasons

    # ------------------------------------------------------------------
    # 5. retention
    # ------------------------------------------------------------------
    def get_review_queue(
        self, learner_id: str, *, session_id: str | None = None, limit: int = 10
    ) -> dict:
        """List the due spaced reviews for a learner, with the next call to make.

        Coarse equivalent of ``get_due_reviews``. A non-empty queue is **not** a
        global block on new learning: whether to insert, prioritise or block is
        decided per node by Policy + State Guard.
        """
        due = self._lean(self.get_due_reviews(learner_id, limit=limit))
        items = due.get("due_reviews") or []
        next_call: dict[str, Any]
        if items:
            first = items[0]
            next_call = {
                "tool": "review_answer",
                "arguments": {
                    "review_item_id": first.get("review_item_id"),
                    "rating": 1,
                },
                "why": (
                    "Ask the learner to retrieve the item, then rate the outcome 1-4 exactly as "
                    "observed: 1 again, 2 hard, 3 good, 4 easy."
                ),
            }
        else:
            next_call = {"tool": "continue_lesson", "why": "Nothing is due; continue new learning."}
        return self.ok(
            learner_id=learner_id,
            session_id=session_id,
            count=due.get("count", len(items)),
            due_reviews=items,
            blocks_new_learning=False,
            next_call=next_call,
            coarse_of=["get_due_reviews"],
            note=due.get("note"),
        )

    def review_answer(
        self,
        review_item_id: str,
        rating: int,
        *,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Apply a 1-4 FSRS rating to a due review and reschedule it.

        Coarse equivalent of ``submit_review``. Rate what you observed, not what
        you hope: a rating >= 2 re-confirms retention evidence and moves the
        node's evidence stage, and an inflated rating delays the next review.
        """
        result = self._lean(
            self.submit_review(review_item_id, rating, session_id=session_id, request_id=request_id)
        )
        return self.ok(
            review_item_id=result.get("review_item_id"),
            rating=result.get("rating"),
            next_review_at=result.get("next_review_at"),
            interval_days=result.get("interval_days"),
            evidence_stage=result.get("evidence_stage"),
            next_call={"tool": "continue_lesson", "why": "Return to the teaching loop."},
            coarse_of=["submit_review"],
        )

    # ------------------------------------------------------------------
    # 6. one-call status
    # ------------------------------------------------------------------
    def get_learner_snapshot(self, session_id: str) -> dict:
        """Return session, node, mastery and review state in one call.

        Coarse equivalent of ``get_session_info`` + ``get_mastery_status`` +
        ``get_knowledge_nodes`` + ``get_due_reviews``. Use it as the single
        read for debugging, progress reporting and the opening turn of a
        reconnected chat window, instead of reconstructing state from memory.
        """
        session = self.require_session(session_id)
        learner_id = session["learner_id"]
        info = self._lean(self.get_session_info(session_id))
        states = self._lean(self.get_mastery_status(session_id)).get("states") or []
        nodes = self._lean(self.get_knowledge_nodes(session_id)).get("nodes") or []
        due = self._lean(self.get_due_reviews(learner_id, limit=5))

        node_titles = {node.get("node_id"): node.get("title") for node in nodes}
        stage_counts: dict[str, int] = {}
        focus: list[dict[str, Any]] = []
        for state in states:
            stage = state.get("evidence_stage") or "estimated"
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            focus.append(
                {
                    "node_id": state.get("node_id"),
                    "title": node_titles.get(state.get("node_id")),
                    "evidence_stage": stage,
                    "mastery_probability": state.get("mastery_probability"),
                    "hint_dependency": state.get("hint_dependency"),
                    "next_review_at": state.get("next_review_at"),
                }
            )

        setup_gaps: list[str] = []
        if session.get("domain_grounding_stage") != "completed":
            setup_gaps.append("domain_grounding_incomplete")
        if not nodes:
            setup_gaps.append("knowledge_nodes_missing")
        if not int(
            self.db.scalar(
                "SELECT COUNT(*) FROM artifacts WHERE session_id = ? "
                "AND artifact_type = 'teaching_package'",
                (session_id,),
                0,
            )
        ):
            setup_gaps.append("teaching_package_missing")
        if not int(
            self.db.scalar(
                "SELECT COUNT(*) FROM assessment_items WHERE session_id = ?", (session_id,), 0
            )
        ):
            setup_gaps.append("assessment_items_missing")

        return self.ok(
            session_id=session_id,
            learner_id=learner_id,
            topic=session.get("topic"),
            session_status=session.get("status"),
            current_node_id=session.get("current_node_id"),
            domain_grounding_stage=session.get("domain_grounding_stage"),
            next_step=info.get("next_step"),
            next_call=self._next_call_for_step(session_id),
            knowledge_node_count=info.get("knowledge_node_count"),
            tracked_nodes=len(states),
            evidence_stage_counts=stage_counts,
            node_states=focus,
            due_review_count=due.get("count", 0),
            due_reviews=due.get("due_reviews") or [],
            setup_gaps=setup_gaps,
            coarse_of=[
                "get_session_info",
                "get_mastery_status",
                "get_knowledge_nodes",
                "get_due_reviews",
            ],
        )
