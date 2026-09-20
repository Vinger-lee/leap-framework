"""Teaching-context, policy and State Guard tools (section 22.4 / 22.5 / 22.8).

This module is the boundary where the host agent *proposes* and the runtime
*decides*. Every state transition funnels through :class:`StateGuard`; nothing
here trusts prompt text.
"""

from __future__ import annotations

from typing import Any

from leap.runtime.policy import ACTIONS, STRATEGIES
from leap.storage import now_ts
from leap.tools.base import LeapToolMixin, ToolError

__all__ = ["TeachingTools"]


class TeachingTools(LeapToolMixin):
    """Context assembly, policy evaluation and guarded state transitions."""

    # ------------------------------------------------------------------
    # 22.4 Teaching context
    # ------------------------------------------------------------------
    def get_teaching_context(self, session_id: str, node_id: str | None = None) -> dict:
        """One call that returns everything a teaching turn needs."""
        context = self.policy.build_teaching_context(session_id, node_id)
        node_id = node_id or context["session"].get("current_node_id")

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
        return self.ok(session_id=session_id, node_id=node_id, **context)

    # ------------------------------------------------------------------
    # 22.5 Pedagogical policy
    # ------------------------------------------------------------------
    def get_available_strategies(self) -> dict:
        rows = self.rows("SELECT * FROM pedagogical_strategies ORDER BY strategy_id")
        return self.ok(count=len(rows), strategies=rows, vocabulary=list(STRATEGIES))

    def get_available_actions(self) -> dict:
        return self.ok(count=len(ACTIONS), actions=list(ACTIONS))

    def get_plugin_info(self) -> dict:
        """Report the active implementation for each section-35 seam.

        Lets an operator confirm what is actually wired up, and lets the host
        agent know which capabilities are backed by which engine.
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
        """Evaluate the policy **without** persisting a decision.

        The evaluation itself is still recorded as a ``policy_evaluated`` event,
        so section 27.1 stays answerable: why it fired, what the state was,
        which actions were candidates, and why one was chosen.
        """
        self.require_session(session_id)
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
        """Persist the decision the host agent actually acted on (section 27.1).

        When the agent omits a strategy/action the runtime records its own
        recommendation, so the decision log is never empty.
        """
        self.require_session(session_id)
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
        """Mark a unit/node as the current focus."""
        session = self.require_session(session_id)
        resolved_node = self._resolve_entry_node(session_id, unit_tag, node_id)
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
        manual_override: bool = False,
        expected_state_version: int | None = None,
    ) -> dict:
        """Dry-run the guard for an advance request (no state change)."""
        resolved_tag = self._resolve_unit_tag(session_id, unit_tag, node_id)
        decision = self.guard.check_unit(
            session_id,
            resolved_tag,
            manual_override=manual_override,
            expected_state_version=expected_state_version,
        )
        return self.ok(session_id=session_id, unit_tag=resolved_tag, guard=decision.as_dict())

    def advance_unit(
        self,
        session_id: str,
        *,
        unit_tag: str | None = None,
        node_id: str | None = None,
        manual_override: bool = False,
        expected_state_version: int | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Request the next unit.

        ``advance_unit`` is a **batch wrapper over a set of nodes**: every node
        carrying the same ``unit_tag`` must pass its own node-level guard, and
        a single failure rejects the whole request (section 6.6). There is no
        unit table.
        """
        session = self.require_session(session_id)
        resolved_tag = self._resolve_unit_tag(session_id, unit_tag, node_id)
        decision = self.guard.check_unit(
            session_id,
            resolved_tag,
            manual_override=manual_override,
            expected_state_version=expected_state_version,
        )

        if not decision.allowed:
            self.events.emit(
                "state_guard_rejected", session_id=session_id, learner_id=session["learner_id"],
                payload={"tool": "advance_unit", "unit_tag": resolved_tag, **decision.as_dict()},
                request_id=request_id,
            )
            raise ToolError("state_guard_rejected", decision.reason, decision.as_dict())

        next_node = self._next_unit_entry(session_id, resolved_tag)
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
            payload={"unit_tag": resolved_tag, "guard": decision.as_dict()},
            request_id=request_id,
        )
        return self.ok(
            session_id=session_id,
            unit_tag=resolved_tag,
            advanced=True,
            next_node_id=next_node,
            state_version=version,
            guard=decision.as_dict(),
        )

    def rollback_unit(
        self,
        session_id: str,
        target_node_id: str,
        *,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Move the focus back to an earlier node (section 21.3)."""
        session = self.require_session(session_id)
        target_node_id = self.require_text(target_node_id, "target_node_id")
        self.require_node(target_node_id)
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

    def complete_session(
        self, session_id: str, *, status: str = "completed", request_id: str | None = None
    ) -> dict:
        session = self.require_session(session_id)
        if status not in {"completed", "paused", "abandoned", "active"}:
            raise ToolError("invalid_status", f"unsupported session status: {status}")
        with self.db.transaction():
            self.db.execute(
                "UPDATE learning_sessions SET status = ?, updated_at = ? WHERE session_id = ?",
                (status, now_ts(), session_id),
            )
        if status == "completed":
            self.events.emit(
                "session_completed", session_id=session_id, learner_id=session["learner_id"],
                payload={}, request_id=request_id,
            )
        return self.ok(session_id=session_id, status=status)

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
            self.require_node(node_id)
            return node_id
        if unit_tag:
            entry = self._next_unit_entry(session_id, unit_tag)
            if entry:
                return entry
            raise ToolError("unknown_unit", f"unit '{unit_tag}' has no nodes in this session")
        raise ToolError("invalid_argument", "either unit_tag or node_id is required")

    def _next_unit_entry(self, session_id: str, unit_tag: str) -> str | None:
        """First node of the unit in topological-ish (id) order."""
        return self.db.scalar(
            "SELECT node_id FROM knowledge_nodes WHERE session_id = ? AND unit_tag = ? "
            "ORDER BY node_id LIMIT 1",
            (session_id, unit_tag),
        )
