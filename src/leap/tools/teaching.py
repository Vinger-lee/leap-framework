"""Teaching-context, policy and State Guard tools (section 22.4 / 22.5 / 22.8).

This module is the boundary where the host agent *proposes* and the runtime
*decides*. Every state transition funnels through :class:`StateGuard`; nothing
here trusts prompt text.
"""

from __future__ import annotations

from typing import Any

from leap.runtime.policy import ACTIONS, STRATEGIES
from leap.runtime.state_guard import GuardDecision
from leap.storage import now_ts
from leap.tools.base import LeapToolMixin, ToolError

__all__ = ["TeachingTools"]


class TeachingTools(LeapToolMixin):
    """Context assembly, policy evaluation and guarded state transitions."""

    # ------------------------------------------------------------------
    # 22.4 Teaching context
    # ------------------------------------------------------------------
    def get_teaching_context(
        self,
        session_id: str,
        node_id: str | None = None,
        *,
        include_template: bool = False,
    ) -> dict:
        """Return the full teaching context in one call to reduce round trips.

        ``include_template=False`` (default) omits the 14 KB authoring template;
        pass ``include_template=True`` once, while authoring the lesson, instead
        of re-sending it on every teaching turn.
        """
        grounding = self.require_grounding(session_id)
        if node_id:
            # A node id is a global primary key: never build a session's context
            # from another session's node.
            self.require_node(node_id, session_id)
        context = self.policy.build_teaching_context(session_id, node_id)
        node_id = node_id or context["session"].get("current_node_id")
        if self.guard.strict_grounding and node_id:
            from leap.runtime.grounding import course_node_id

            if node_id != course_node_id(session_id):
                raise ToolError("grounding_coverage_missing", "The requested node is outside the reviewed course")

        recommended: list[str] = []
        try:
            decision = self.policy.evaluate(session_id, node_id)
            recommended = [decision.selected_action] + [
                a for a in decision.candidate_actions if a != decision.selected_action
            ]
            context["recommended_actions"] = recommended[:4]
            context["recommended_strategy"] = decision.selected_strategy
            context["recommendation_reason"] = decision.reason
        except Exception as exc:  # pragma: no cover - context must degrade gracefully
            context["recommended_actions"] = []
            context["recommendation_error"] = str(exc)

        context["due_review_count"] = len(context.get("due_reviews") or [])
        context["domain_grounding_evidence"] = self.get_evidence(session_id, node_id)
        context["assessment_delivery"] = {
            "register_items_before_delivery": "save_assessment_item",
            "free_text_requires": "host semantic review; never keyword-only scoring",
            "runtime_content_verification": False,
            "register_lesson_before_items": "save_teaching_package",
            "canonical_source": "complete Obsidian Markdown with reciprocal wikilinks and more detail than HTML",
        }
        if include_template:
            from leap.runtime.delivery import teaching_point_template

            context["teaching_point_template"] = teaching_point_template()
        context["lesson_packages"] = self.rows(
            "SELECT artifact_id, metadata FROM artifacts WHERE session_id=? "
            "AND artifact_type='teaching_package' ORDER BY rowid DESC", (session_id,)
        )
        if self.guard.strict_grounding:
            context["grounding"] = grounding
            from leap.runtime.grounding import course_node_id, reviewed_course

            context["reviewed_package_id"] = self.db.scalar(
                "SELECT artifact_id FROM artifacts WHERE session_id=? AND artifact_type='teaching_package' "
                "AND json_extract(metadata, '$.course_revision')=? AND json_extract(metadata, '$.node_id')=? "
                "ORDER BY rowid DESC LIMIT 1", (session_id, grounding["course_revision"], course_node_id(session_id)),
            )
            if not context["reviewed_package_id"]:
                context["recommended_actions"] = []
                context["recommended_strategy"] = None
            else:
                items = self.rows(
                    "SELECT item_id, question FROM assessment_items WHERE session_id=? "
                    "AND json_extract(rubric, '$.teaching_package_id')=? ORDER BY rowid ASC",
                    (session_id, context["reviewed_package_id"]),
                )
                ids = {item["question"]: item["item_id"] for item in items}
                context["reviewed_item_ids"] = [ids.get(point["item"]["question"]) for point in reviewed_course()["points"]]
        return self.ok(session_id=session_id, node_id=node_id, **context)

    # ------------------------------------------------------------------
    # 22.5 Pedagogical policy
    # ------------------------------------------------------------------
    def get_available_strategies(self) -> dict:
        """List the pedagogical strategies available to the policy engine."""
        rows = self.rows("SELECT * FROM pedagogical_strategies ORDER BY strategy_id")
        return self.ok(count=len(rows), strategies=rows, vocabulary=list(STRATEGIES))

    def get_available_actions(self) -> dict:
        """List the concrete teaching actions the host agent may execute."""
        return self.ok(count=len(ACTIONS), actions=list(ACTIONS))

    def get_plugin_info(self) -> dict:
        """Report which implementation backs each pluggable seam (section 35).

        Covers state estimation, assessment aggregation, policy, review
        scheduling, storage and artifact storage.
        """
        from leap.runtime.plugins import describe_plugins

        active = {
            "mastery_estimator": str(self.conf("mastery_estimator", "simplified_bkt")),
            "score_aggregator": str(self.conf("score_aggregator", "weighted")),
            "policy_engine": str(self.conf("policy_engine", "rule_based")),
            "review_scheduler": str(self.conf("review_scheduler", "py-fsrs")),
            "storage_backend": str(self.conf("storage_backend", "sqlite")),
            "artifact_store": str(self.conf("artifact_store", "local")),
        }
        available = describe_plugins()
        unresolved = [kind for kind, name in active.items() if name not in available.get(kind, [])]

        aggregator_detail = None
        if hasattr(self.aggregator, "describe"):
            aggregator_detail = self.aggregator.describe()

        i18n_detail = None
        if hasattr(self.i18n, "describe"):
            i18n_detail = self.i18n.describe()

        return self.ok(
            active=active,
            available=available,
            unresolved=unresolved,
            aggregator=aggregator_detail,
            i18n=i18n_detail,
            note=(
                "Each seam can be swapped by changing config/default.yaml and registering an "
                "implementation under the same kind (section 35). Unresolved entries fall back "
                "to the built-in default. 'locale' controls learner-visible text only."
            ),
        )

    def evaluate_pedagogical_policy(
        self, session_id: str, node_id: str | None = None, *, trigger_event: str | None = None
    ) -> dict:
        """Evaluate the policy for the current state without persisting a decision."""
        self.require_session(session_id)
        if self.guard.strict_grounding:
            self.require_grounding(session_id)
        context = self.policy.build_teaching_context(session_id, node_id)
        decision = self.policy.evaluate(session_id, node_id, trigger_event=trigger_event)

        self.events.emit(
            "policy_evaluated",
            session_id=session_id,
            learner_id=context.get("learner_id"),
            node_id=decision.node_id,
            payload={
                "trigger_event": trigger_event or decision.trigger_event,
                "state_snapshot": self._compact_state(context),
                "candidate_actions": decision.candidate_actions,
                "selected_strategy": decision.selected_strategy,
                "selected_action": decision.selected_action,
                "reason": decision.reason,
            },
        )
        return self.ok(session_id=session_id, decision=decision.as_dict())

    @staticmethod
    def _compact_state(context: dict) -> dict:
        """The slice of learner state a decision was made from (section 27.1)."""
        state = context.get("knowledge_state") or {}
        prerequisites = context.get("prerequisite_state") or {}
        friction = context.get("learning_friction") or {}
        return {
            "evidence_stage": context.get("evidence_stage"),
            "mastery_probability": state.get("mastery_probability"),
            "hint_dependency": state.get("hint_dependency"),
            "reasoning_quality": state.get("reasoning_quality"),
            "active_misconceptions": len(context.get("misconceptions") or []),
            "missing_prerequisites": prerequisites.get("missing") or [],
            "transfer_required": context.get("transfer_requirement"),
            "due_review_count": len(context.get("due_reviews") or []),
            "recent_attempt_count": len(context.get("recent_attempts") or []),
            "friction_signals": friction.get("signals") or [],
        }

    def commit_pedagogical_decision(
        self,
        session_id: str,
        selected_strategy: str | None = None,
        selected_action: str | None = None,
        *,
        node_id: str | None = None,
        trigger_event: str | None = None,
        rationale: str | None = None,
        expected_outcome: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Record the decision actually acted on, for later replay."""
        self.require_session(session_id)
        if self.guard.strict_grounding:
            self.require_grounding(session_id)
        recommendation = self.policy.evaluate(session_id, node_id, trigger_event=trigger_event)

        if selected_strategy and selected_strategy not in STRATEGIES:
            raise ToolError(
                "invalid_strategy", f"unknown strategy {selected_strategy!r}; see get_available_strategies"
            )
        if selected_action and selected_action not in ACTIONS:
            raise ToolError(
                "invalid_action", f"unknown action {selected_action!r}; see get_available_actions"
            )

        recommendation.selected_strategy = selected_strategy or recommendation.selected_strategy
        recommendation.selected_action = selected_action or recommendation.selected_action
        if rationale:
            recommendation.reason = rationale
        if expected_outcome:
            recommendation.expected_outcome = expected_outcome

        decision_id = self.policy.commit(
            session_id, recommendation, trigger_event=trigger_event
        )
        self.events.emit(
            "action_executed",
            session_id=session_id,
            node_id=recommendation.node_id,
            payload={"decision_id": decision_id, "action": recommendation.selected_action},
            request_id=request_id,
        )
        return self.ok(decision_id=decision_id, decision=recommendation.as_dict())

    def get_decision_log(self, session_id: str, limit: int = 50) -> dict:
        """Read the pedagogical decision history for a session."""
        self.require_session(session_id)
        rows = self.policy.decision_log(session_id, limit=limit)
        return self.ok(session_id=session_id, count=len(rows), decisions=rows)

    # ------------------------------------------------------------------
    # 22.8 State Guard tools
    # ------------------------------------------------------------------
    def start_unit(
        self,
        session_id: str,
        *,
        unit_tag: str | None = None,
        node_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Set the current teaching focus to a unit or node.

        The unit's entry node follows the DAG: prerequisites/extension edges are
        ordered topologically (ties broken by node id), instead of a plain
        lexicographic ``node_id`` sort that could start a lesson on a node whose
        prerequisites are later in the same unit.
        """
        session = self.require_session(session_id)
        self.require_active_session(session)
        self.require_grounding(session_id)
        resolved_node = self._resolve_entry_node(session_id, unit_tag, node_id)
        if self.guard.strict_grounding:
            from leap.runtime.grounding import course_node_id

            if resolved_node != course_node_id(session_id):
                raise ToolError("grounding_coverage_missing", "The requested unit is outside the reviewed course")
        ts = now_ts()
        with self.db.transaction():
            self.db.execute(
                "UPDATE learning_sessions SET current_node_id = ?, updated_at = ? "
                "WHERE session_id = ?",
                (resolved_node, ts, session_id),
            )
        self.events.emit(
            "node_started", session_id=session_id, learner_id=session["learner_id"],
            node_id=resolved_node, payload={"unit_tag": unit_tag}, request_id=request_id,
        )
        return self.ok(session_id=session_id, current_node_id=resolved_node, unit_tag=unit_tag)

    def check_advance_unit(
        self,
        session_id: str,
        *,
        unit_tag: str | None = None,
        node_id: str | None = None,
        expected_state_version: int | None = None,
    ) -> dict:
        """Dry-run the State Guard for an advance request without changing state.

        ``manual_override`` is intentionally not exposed to the host: the guard
        may only be overridden by an operator-level entry point, never by prompt
        text or a tool argument.
        """
        self.require_session(session_id)
        if self.guard.strict_grounding:
            self.require_grounding(session_id)
        resolved_tag = self._resolve_unit_tag(session_id, unit_tag, node_id)
        decision = self.guard.check_unit(
            session_id,
            resolved_tag,
            expected_state_version=expected_state_version,
        )
        return self.ok(session_id=session_id, unit_tag=resolved_tag, guard=decision.as_dict())

    def advance_unit(
        self,
        session_id: str,
        *,
        unit_tag: str | None = None,
        node_id: str | None = None,
        expected_state_version: int | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Request the next unit.

        Every node sharing the unit_tag must pass its own node-level guard;
        one failure rejects the whole request. There is no unit table. On
        success the focus moves to the next unit's entry node; when the last
        unit is passed the result says so explicitly (``has_next_unit=False``)
        instead of silently restarting the current unit.
        """
        with self.db.transaction():
            session = self.require_session(session_id)
            self.require_active_session(session)
            if self.guard.strict_grounding:
                self.require_grounding(session_id)
            resolved_tag = self._resolve_unit_tag(session_id, unit_tag, node_id)
            decision = self.guard.check_unit(
                session_id,
                resolved_tag,
                expected_state_version=expected_state_version,
            )

            if decision.allowed:
                return self._commit_unit_advance(session, resolved_tag, decision, request_id)

        self.events.emit(
            "state_guard_rejected", session_id=session_id, learner_id=session["learner_id"],
            payload={"tool": "advance_unit", "unit_tag": resolved_tag, **decision.as_dict()},
            request_id=request_id,
        )
        raise ToolError("state_guard_rejected", decision.reason, decision.as_dict())

    def _commit_unit_advance(
        self, session: dict, resolved_tag: str, decision: GuardDecision, request_id: str | None,
    ) -> dict:
        """Apply a unit transition after the caller's guard allowed it."""
        session_id = session["session_id"]
        if self.guard.strict_grounding:
            # Only one reviewed unit is installed. Nodes from older course versions
            # remain in history and cannot become the next unit automatically.
            next_unit_tag, next_node = None, None
        else:
            next_unit_tag, next_node = self._next_unit_after(session_id, resolved_tag)
        ts = now_ts()
        with self.db.transaction():
            self.db.execute(
                "UPDATE learning_sessions SET current_node_id = COALESCE(?, current_node_id), "
                "updated_at = ? WHERE session_id = ?",
                (next_node, ts, session_id),
            )
            version = self.guard.bump_state_version(session_id)
        self.events.emit(
            "unit_advanced", session_id=session_id, learner_id=session["learner_id"],
            node_id=next_node,
            payload={
                "unit_tag": resolved_tag,
                "next_unit_tag": next_unit_tag,
                "has_next_unit": next_node is not None,
                "guard": decision.as_dict(),
            },
            request_id=request_id,
        )
        return self.ok(
            session_id=session_id,
            unit_tag=resolved_tag,
            advanced=True,
            next_node_id=next_node,
            next_unit_tag=next_unit_tag,
            has_next_unit=next_node is not None,
            state_version=version,
            guard=decision.as_dict(),
            guidance=(
                "The guard released the unit. Teach next_node_id when present."
                if next_node
                else "This was the last unit: no next node was selected. Generate the closing "
                "report and close the session."
            ),
        )

    def rollback_unit(
        self,
        session_id: str,
        target_node_id: str,
        *,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Move the teaching focus back to an earlier node."""
        session = self.require_session(session_id)
        target_node_id = self.require_text(target_node_id, "target_node_id")
        self.require_node(target_node_id, session_id)
        ts = now_ts()
        with self.db.transaction():
            self.db.execute(
                "UPDATE learning_sessions SET current_node_id = ?, updated_at = ? "
                "WHERE session_id = ?",
                (target_node_id, ts, session_id),
            )
        version = self.guard.bump_state_version(session_id)
        self.events.emit(
            "unit_rollback", session_id=session_id, learner_id=session["learner_id"],
            node_id=target_node_id, payload={"reason": reason}, request_id=request_id,
        )
        return self.ok(
            session_id=session_id, current_node_id=target_node_id,
            state_version=version, reason=reason,
        )

    _STATUSES = ("active", "paused", "completed", "abandoned")

    def complete_session(
        self,
        session_id: str,
        *,
        status: str = "completed",
        reopen: bool = False,
        require_final_report: bool = True,
        request_id: str | None = None,
    ) -> dict:
        """Set the session status with explicit transition rules.

        * ``completed`` requires a persisted final report (the closing receipt)
          unless ``require_final_report=False``; closing twice is idempotent and
          emits the completion event only once.
        * reopening a completed session requires ``reopen=True`` (``active``).
        """
        with self.db.transaction():
            session = self.require_session(session_id)
            if status not in self._STATUSES:
                raise ToolError(
                    "invalid_status",
                    f"unsupported session status: {status}",
                    {"allowed": list(self._STATUSES)},
                )
            current = str(session.get("status") or "active")
            report_id = self.final_report_artifact_id(session_id)

            if status == current:
                return self.ok(
                    session_id=session_id,
                    status=status,
                    previous_status=current,
                    already_applied=True,
                    final_report_artifact_id=report_id,
                    note="the session already has this status; nothing was written",
                )

            if status == "completed":
                if require_final_report and not report_id:
                    raise ToolError(
                        "final_report_required",
                        "generate_final_report must succeed before the session can be completed",
                        {"session_id": session_id, "retryable": False,
                         "hint": "call generate_final_report first"},
                    )
                if current == "abandoned":
                    raise ToolError(
                        "invalid_transition",
                        "an abandoned session cannot be completed directly",
                        {"from": current, "to": status},
                    )
            elif status == "active":
                if current == "completed" and not reopen:
                    raise ToolError(
                        "invalid_transition",
                        "reopening a completed session requires reopen=true",
                        {"from": current, "to": status, "reopen": False},
                    )

            self.db.execute(
                "UPDATE learning_sessions SET status = ?, updated_at = ? WHERE session_id = ?",
                (status, now_ts(), session_id),
            )
            version = self.guard.bump_state_version(session_id)
            if status == "completed":
                # Literal call site: the event-vocabulary contract test scans
                # emit() calls statically.
                self.events.emit(
                    "session_completed",
                    session_id=session_id,
                    learner_id=session["learner_id"],
                    payload={"final_report_artifact_id": report_id},
                    request_id=request_id,
                )
            return self.ok(
                session_id=session_id,
                status=status,
                previous_status=current,
                already_applied=False,
                final_report_artifact_id=report_id,
                state_version=version,
            )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _resolve_unit_tag(
        self, session_id: str, unit_tag: str | None, node_id: str | None
    ) -> str:
        if unit_tag:
            return unit_tag
        if node_id:
            tag = self.db.scalar(
                "SELECT unit_tag FROM knowledge_nodes WHERE node_id = ? AND session_id = ?",
                (node_id, session_id),
            )
            if tag:
                return str(tag)
            raise ToolError("unknown_unit", f"node {node_id} has no unit_tag")
        current = self.db.scalar(
            "SELECT current_node_id FROM learning_sessions WHERE session_id = ?", (session_id,)
        )
        if current:
            tag = self.db.scalar(
                "SELECT unit_tag FROM knowledge_nodes WHERE node_id = ?", (current,)
            )
            if tag:
                return str(tag)
        raise ToolError(
            "unknown_unit",
            "cannot resolve a unit: pass unit_tag, node_id, or start_unit first",
        )

    def _resolve_entry_node(
        self, session_id: str, unit_tag: str | None, node_id: str | None
    ) -> str:
        if node_id:
            self.require_node(node_id, session_id)
            return node_id
        if unit_tag:
            entry = self._next_unit_entry(session_id, unit_tag)
            if entry:
                return entry
            raise ToolError("unknown_unit", f"unit '{unit_tag}' has no nodes in this session")
        raise ToolError("invalid_argument", "either unit_tag or node_id is required")

    #: Relations that impose teaching order.
    _DEPENDENCY_RELATIONS = frozenset({"prerequisite", "extension"})

    def _teaching_order(self, session_id: str) -> list[dict]:
        """Return the session's nodes in dependency order (deterministic).

        Prerequisite/extension edges are respected (Kahn's algorithm, ties
        broken by ``node_id``); cycles fall back to node-id order so a malformed
        DAG can never make a unit unreachable.
        """
        nodes = self.rows(
            "SELECT * FROM knowledge_nodes WHERE session_id = ? ORDER BY node_id",
            (session_id,),
        )
        edges = self.rows(
            "SELECT pre_node_id, post_node_id, relation_type FROM knowledge_edges "
            "WHERE session_id = ? ORDER BY rowid",
            (session_id,),
        )
        by_id = {node["node_id"]: node for node in nodes}
        dependencies: dict[str, set[str]] = {node_id: set() for node_id in by_id}
        for edge in edges:
            relation = str(edge.get("relation_type") or "")
            pre, post = edge.get("pre_node_id"), edge.get("post_node_id")
            if relation in self._DEPENDENCY_RELATIONS and pre in by_id and post in by_id and pre != post:
                dependencies[post].add(pre)
        remaining = set(by_id)
        ordered: list[dict] = []
        while remaining:
            ready = sorted(node_id for node_id in remaining if not (dependencies[node_id] & remaining))
            if not ready:  # cycle: keep the order deterministic instead of failing
                ready = sorted(remaining)
            for node_id in ready:
                ordered.append(by_id[node_id])
                remaining.discard(node_id)
        return ordered

    def _unit_order(self, session_id: str) -> list[str]:
        """Unit tags in the order their first node appears in the teaching order."""
        ordered: list[str] = []
        for node in self._teaching_order(session_id):
            tag = node.get("unit_tag")
            if tag and tag not in ordered:
                ordered.append(tag)
        return ordered

    def _next_unit_entry(self, session_id: str, unit_tag: str) -> str | None:
        """Entry node of a unit: the first of its nodes in dependency order."""
        for node in self._teaching_order(session_id):
            if node.get("unit_tag") == unit_tag:
                return node["node_id"]
        return None

    def _next_unit_after(self, session_id: str, unit_tag: str) -> tuple[str | None, str | None]:
        """Return ``(next unit tag, its entry node)`` after ``unit_tag``."""
        units = self._unit_order(session_id)
        if unit_tag not in units:
            return None, None
        index = units.index(unit_tag) + 1
        if index >= len(units):
            return None, None
        next_tag = units[index]
        return next_tag, self._next_unit_entry(session_id, next_tag)
