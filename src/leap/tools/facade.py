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

from leap.tools.base import LeapToolMixin, PartialResultError, ToolError

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
    "unit_start": {
        "tool": "start_unit",
        "follow_up": ["save_teaching_package", "save_assessment_item"],
        "why": "The diagnostic is complete; select the first teaching unit before the loop.",
    },
    "teaching": {
        "tool": "continue_lesson",
        "why": "The session is ready for the teaching loop.",
    },
    "closed": {
        "tool": None,
        "why": "The session is completed/abandoned; teaching is closed. Start or reopen a session.",
        "session_closed": True,
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
        if step == "closed":
            return {**LIFECYCLE_NEXT_CALL["closed"], "lifecycle_step": "closed"}
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
        reuse_existing: bool = True,
        force_new: bool = False,
        request_id: str | None = None,
    ) -> dict:
        """Start a session, record its goal and pick a learning mode in one call.

        Coarse equivalent of create_session + save_learning_goal +
        set_learning_configuration. The response returns next_call - the next
        tool to call - and, when domain_grounding_notice is present, you must
        show it to the learner verbatim before the grounding stage starts.

        By default an active session for the same learner and topic is resumed
        instead of silently creating a second one (``existing_session=True``).
        Pass ``force_new=True`` to deliberately start another session.
        """
        existing = None
        if reuse_existing and not force_new:
            found = self._lean(self.find_session(learner_id, topic))
            active = [
                row for row in found.get("sessions") or []
                if str(row.get("status") or "active") == "active"
            ]
            if active:
                existing = active[0]
        if existing is None:
            session = self._lean(
                self.create_session(
                    learner_id,
                    topic,
                    allow_skip_domain_grounding=allow_skip_domain_grounding,
                    request_id=request_id,
                )
            )
        else:
            session = dict(existing)
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
            existing_session=existing is not None,
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
                "Do not invent a benchmark report: record what you actually read. "
                + (
                    "This call RESUMED the active session for this learner+topic; pass "
                    "force_new=True if a second session is really intended."
                    if existing is not None
                    else ""
                )
            ),
        )

    # ------------------------------------------------------------------
    # 2. teaching turn
    # ------------------------------------------------------------------
    def continue_lesson(
        self, session_id: str, node_id: str | None = None, *, verbose: bool = False
    ) -> dict:
        """Return the teaching state and the next action in one call.

        Coarse equivalent of get_teaching_context + get_session_info. Reports
        the policy engine's recommended strategy and actions together with the
        evidence stage, friction signals, active misconceptions and due review
        count, plus next_call. The facade never selects the pedagogy itself.

        ``verbose=False`` (default) returns the summary only; pass
        ``verbose=True`` to embed the full teaching context (or call
        ``get_teaching_context`` directly when you need it).
        """
        session = self.require_session(session_id)
        self.require_active_session(session)
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
                "arguments": {"learner_id": session["learner_id"], "session_id": session_id},
                "why": "Spaced reviews are due; they do not block new learning globally, but they are evidence.",
            }
        else:
            from leap.runtime.policy import ACTIONS

            next_call = {
                "tool": "log_teaching_action",
                "then": "submit_answer",
                "allowed_actions": list(ACTIONS),
                "why": "Log the action you actually take, then record the learner's answer against it.",
            }

        payload: dict[str, Any] = dict(
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
        )
        if verbose:
            payload["teaching_context"] = context
        else:
            payload["teaching_context_omitted"] = True
            payload["teaching_context_hint"] = {
                "tool": "get_teaching_context",
                "why": "Full context is opt-in to keep every teaching turn small.",
            }
        return self.ok(**payload)

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

        Coarse equivalent of commit_pedagogical_decision. Omitting action and
        strategy records the runtime recommendation, so the decision log is
        never empty; passing what you did keeps the log auditable.
        """
        from leap.runtime.policy import ACTIONS, STRATEGIES

        if action and action not in ACTIONS:
            raise ToolError(
                "invalid_action",
                f"unknown action {action!r}",
                {"allowed_actions": list(ACTIONS), "retryable": False,
                 "hint": "use one of allowed_actions, or omit action to record the recommendation"},
            )
        if strategy and strategy not in STRATEGIES:
            raise ToolError(
                "invalid_strategy",
                f"unknown strategy {strategy!r}",
                {"allowed_strategies": list(STRATEGIES), "retryable": False},
            )
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

        Coarse equivalent of submit_attempt + commit_assessment (plus a read-back
        of the updated state). The raw answer is stored verbatim and reused as
        raw_answer, which removes the usual mismatch error. With no score
        supplied only the attempt is stored - use that when free-text reasoning
        still needs your semantic review, then call commit_assessment yourself.
        Never send mastery_probability: it is computed server-side.
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
            raise PartialResultError(
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
                retryable=exc.retryable,
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
        expected_state_version: int | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Dry-run the State Guard and advance only if it allows the transition.

        Coarse equivalent of check_advance_unit + advance_unit. A rejection is
        not an error: the response returns advanced=false, the guard's own
        reason and the repair action, and nothing is written. Never work around
        a rejection in prompt text - and the host has no manual_override switch
        to do so with.
        """
        with self.db.transaction():
            session = self.require_session(session_id)
            self.require_active_session(session)
            resolved_tag = self._resolve_unit_tag(session_id, unit_tag, node_id)
            decision = self.guard.check_unit(
                session_id, resolved_tag, expected_state_version=expected_state_version
            )
            guard = decision.as_dict()
            if not decision.allowed:
                reason = guard.get("reason") or "the State Guard did not allow this transition"
                return self.ok(
                    session_id=session_id,
                    unit_tag=resolved_tag,
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
                self._commit_unit_advance(session, resolved_tag, decision, request_id)
            )
            has_next = bool(result.get("has_next_unit"))
            return self.ok(
                session_id=session_id,
                unit_tag=result.get("unit_tag"),
                advanced=True,
                guard_allowed=True,
                next_node_id=result.get("next_node_id"),
                next_unit_tag=result.get("next_unit_tag"),
                has_next_unit=has_next,
                state_version=result.get("state_version"),
                guard=result.get("guard"),
                next_call={
                    "tool": "continue_lesson" if has_next else "generate_final_report",
                    "why": (
                        "Teach the node the guard released."
                        if has_next
                        else "The last unit passed: generate the closing report, then complete the session."
                    ),
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
        """List the due spaced reviews for a learner with the next call to make.

        Coarse equivalent of get_due_reviews. A non-empty queue is not a global
        block on new learning; whether to insert, prioritise or block is decided
        per node by Policy + State Guard.
        """
        due = self._lean(self.get_due_reviews(learner_id, limit=limit, session_id=session_id))
        items = due.get("due_reviews") or []
        next_call: dict[str, Any]
        if items:
            first = items[0]
            resolved_session_id = session_id or self.session_of_node(first.get("node_id"))
            arguments: dict[str, Any] = {"review_item_id": first.get("review_item_id")}
            if resolved_session_id:
                # Required for the evidence-stage recalculation: without it the
                # review used to demote the node to `estimated`.
                arguments["session_id"] = resolved_session_id
            next_call = {
                "tool": "review_answer",
                "arguments": arguments,
                # `rating` is deliberately NOT prefilled: a placeholder would be
                # committed as the observed recall if the host forgets to replace
                # it. The host must supply the real 1-4 rating.
                "required_arguments": ["rating"],
                "allowed_ratings": [1, 2, 3, 4],
                "why": (
                    "Ask the learner to retrieve the item, then call review_answer with the "
                    "rating you actually observed: 1 again, 2 hard, 3 good, 4 easy."
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

        Coarse equivalent of submit_review. Rate what you observed: a rating of
        2 or more re-confirms retention evidence and can move the node's
        evidence stage, while an inflated rating delays the next review.
        """
        result = self._lean(
            self.submit_review(review_item_id, rating, session_id=session_id, request_id=request_id)
        )
        return self.ok(
            review_item_id=result.get("review_item_id"),
            rating=result.get("rating"),
            session_id=result.get("session_id"),
            session_inferred=result.get("session_inferred"),
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

        Coarse equivalent of get_session_info + get_mastery_status +
        get_knowledge_nodes + get_due_reviews. Use it as the single read for
        reconnecting a chat window, reporting progress or debugging a session,
        instead of rebuilding state from memory.
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

        status = str(session.get("status") or "active")
        closed = status in {"completed", "abandoned"}
        return self.ok(
            session_id=session_id,
            learner_id=learner_id,
            topic=session.get("topic"),
            session_status=status,
            session_closed=closed,
            current_node_id=session.get("current_node_id"),
            domain_grounding_stage=session.get("domain_grounding_stage"),
            next_step=info.get("next_step"),
            next_call=None if closed else self._next_call_for_step(session_id),
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
