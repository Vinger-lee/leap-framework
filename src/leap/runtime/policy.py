"""Dynamic Pedagogical Policy engine (sections 8, 9, 12, 15, 21).

The engine answers one question: *given the current state, what should happen
next?* It is deliberately **rule-based in P0** - section 35.3 places
``Rule-based -> LLM Policy -> Hybrid -> Learned`` on a pluggability ladder, and
the rule rung is the one that can be audited and regression-tested.

Two concepts are kept strictly apart (section 8.4)::

    Strategy = the teaching method      (Explanation, Scaffolding, ...)
    Action   = the concrete next move   (Explain Concept, Give Hint, ...)

One strategy spans many actions and one action may serve several strategies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from leap.runtime.evidence import stage_index
from leap.runtime.scheduler import ReviewScheduler
from leap.storage import Database, new_id, now_ts

__all__ = ["PolicyDecision", "PolicyEngine", "STRATEGIES", "ACTIONS"]

#: Strategy vocabulary (section 8.4).
STRATEGIES: tuple[str, ...] = (
    "Explanation",
    "Scaffolding",
    "Socratic",
    "Correction",
    "Worked Example",
    "Retrieval Practice",
    "PBL",
    "Cognitive Apprenticeship",
    "Transfer Probe",
    "Reflection",
)

#: Action vocabulary (section 8.4).
ACTIONS: tuple[str, ...] = (
    "Explain Concept",
    "Ask Guiding Question",
    "Give Hint",
    "Give Partial Derivation",
    "Provide Worked Example",
    "Generate Practice",
    "Generate Retrieval Item",
    "Correct Misconception",
    "Show Visualization",
    "Review Prerequisite",
    "Run Transfer Probe",
    "Record Reflection",
    "Advance Unit",
    "Rollback",
    "Schedule Review",
)


@dataclass
class PolicyDecision:
    """The structured decision record (section 8.3)."""

    selected_strategy: str
    selected_action: str
    reason: str
    expected_outcome: str = ""
    candidate_actions: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    state_guard_checks: list[dict] = field(default_factory=list)
    node_id: str | None = None
    trigger_event: str | None = None
    disclosure_level: int = 0
    #: Present when the decision is an interleaving decision (section 31).
    interleaving: dict | None = None

    def as_dict(self) -> dict:
        payload = {
            "candidate_actions": self.candidate_actions,
            "selected_strategy": self.selected_strategy,
            "selected_action": self.selected_action,
            "reason": self.reason,
            "expected_outcome": self.expected_outcome,
            "required_evidence": self.required_evidence,
            "state_guard_checks": self.state_guard_checks,
            "node_id": self.node_id,
            "trigger_event": self.trigger_event,
            "disclosure_level": self.disclosure_level,
        }
        if self.interleaving is not None:
            payload["interleaving"] = self.interleaving
        return payload


class PolicyEngine:
    """Rule-based policy engine with an auditable decision trail."""

    def __init__(self, db: Database, cfg: Any, events: Any = None) -> None:
        self._db = db
        self._cfg = cfg
        self._events = events
        self._scheduler = ReviewScheduler(cfg)
        #: Session-scoped policy overrides (section 32), keyed by session_id.
        self._override_cache: dict[str, dict] = {}

    def _get(self, key: str, default: Any = None, session_id: str | None = None) -> Any:
        """Read a parameter, letting a session override win over global config.

        Section 32: a learner's requested mode is stored as *Learning
        Configuration + Pedagogical Policy Overrides*, not by editing the
        program. This lookup is where that promise is honoured.
        """
        if session_id:
            overrides = self.session_overrides(session_id)
            if key in overrides:
                return overrides[key]
        return self._cfg.get(key, default) if hasattr(self._cfg, "get") else default

    def session_overrides(self, session_id: str) -> dict:
        """Return the session's effective parameter overrides, cached per process.

        The stored payload is ``{mode, overrides, preferences, requested}``;
        only the ``overrides`` sub-mapping changes engine parameters. A flat
        mapping is also accepted, so a hand-written row still works.
        """
        cached = self._override_cache.get(session_id)
        if cached is not None:
            return cached
        raw = self._db.scalar(
            "SELECT policy_overrides FROM learning_sessions WHERE session_id = ?", (session_id,)
        )
        data: dict = {}
        if raw:
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                nested = parsed.get("overrides")
                data = dict(nested) if isinstance(nested, dict) else dict(parsed)
        self._override_cache[session_id] = data
        return data

    def invalidate_overrides(self, session_id: str) -> None:
        """Drop the cached overrides after they change."""
        self._override_cache.pop(session_id, None)

    def learning_mode(self, session_id: str) -> str:
        value = self._db.scalar(
            "SELECT learning_mode FROM learning_sessions WHERE session_id = ?", (session_id,)
        )
        return str(value or "balanced")

    # ------------------------------------------------------------------
    # Teaching context (section 22.4)
    # ------------------------------------------------------------------
    def build_teaching_context(self, session_id: str, node_id: str | None = None) -> dict:
        """Assemble everything a policy decision needs in one read."""
        session = self._db.query_one(
            "SELECT * FROM learning_sessions WHERE session_id = ?", (session_id,)
        )
        if session is None:
            raise KeyError(f"unknown session: {session_id}")
        session = dict(session)
        learner_id = session["learner_id"]

        current_node_id = node_id or session.get("current_node_id")
        node = None
        if current_node_id:
            row = self._db.query_one(
                "SELECT * FROM knowledge_nodes WHERE node_id = ?", (current_node_id,)
            )
            node = dict(row) if row else None

        knowledge_state = None
        if current_node_id:
            row = self._db.query_one(
                "SELECT * FROM learner_knowledge_state WHERE learner_id = ? AND node_id = ?",
                (learner_id, current_node_id),
            )
            knowledge_state = dict(row) if row else None

        attempts = self._recent_attempts(session_id, current_node_id)
        misconceptions = self._active_misconceptions(learner_id, current_node_id)
        friction = self._friction_signals(attempts)
        prerequisites = self._prerequisite_status(learner_id, current_node_id)
        due_reviews = self.due_reviews(learner_id)

        return {
            "session": session,
            "learner_id": learner_id,
            "current_node": node,
            "knowledge_state": knowledge_state,
            "recent_attempts": attempts,
            "misconceptions": misconceptions,
            "learning_friction": friction,
            "prerequisite_state": prerequisites,
            "due_reviews": due_reviews,
            "evidence_stage": (knowledge_state or {}).get("evidence_stage", "estimated"),
            "transfer_requirement": self._transfer_requirement(node, session_id),
            "learning_mode": self.learning_mode(session_id),
            "learning_preferences": self.learning_preferences(session_id),
        }

    # ------------------------------------------------------------------
    # Policy evaluation
    # ------------------------------------------------------------------
    def evaluate(
        self,
        session_id: str,
        node_id: str | None = None,
        *,
        trigger_event: str | None = None,
        guard_checks: list[dict] | None = None,
    ) -> PolicyDecision:
        """Choose the next strategy/action for the current state."""
        ctx = self.build_teaching_context(session_id, node_id)
        node = ctx["current_node"]
        state = ctx["knowledge_state"] or {}
        friction = ctx["learning_friction"]

        mastery = float(state.get("mastery_probability") or 0.0)
        hint_dep = float(state.get("hint_dependency") or 0.0)
        stage = ctx["evidence_stage"]

        # Session-scoped overrides take precedence over global config (section 32).
        mastery_threshold = float(self._get("mastery_threshold", 0.80, session_id))
        hint_high = float(self._get("hint_dependency_high", 0.70, session_id))
        reasoning_low = float(self._get("reasoning_quality_low", 0.50, session_id))
        max_retry = int(self._get("max_retry_before_example", 3, session_id))

        decision: PolicyDecision
        candidates: list[str] = []

        # 1. Active misconception -> correct before anything else (section 9.4).
        #    A wrong mental model corrupts every downstream observation, so it
        #    outranks even prerequisite repair.
        if ctx["misconceptions"]:
            top = ctx["misconceptions"][0]
            candidates = ["Correct Misconception", "Ask Guiding Question", "Give Partial Derivation"]
            return self._finalize(
                PolicyDecision(
                    selected_strategy="Correction",
                    selected_action="Correct Misconception",
                    reason=f"active misconception: {top['misconception']}",
                    expected_outcome="misconception marked resolved and re-verified",
                    candidate_actions=candidates,
                    required_evidence=["re-explanation", "counterexample task"],
                    node_id=(node or {}).get("node_id"),
                    trigger_event=trigger_event or "misconception_detected",
                ),
                guard_checks,
            )

        # 2. Missing prerequisites -> repair the foundation before teaching on
        #    top of a gap (section 21.3).
        missing = ctx["prerequisite_state"].get("missing") or []
        if missing:
            candidates = ["Review Prerequisite", "Rollback", "Explain Concept"]
            return self._finalize(
                PolicyDecision(
                    selected_strategy="Scaffolding",
                    selected_action="Review Prerequisite",
                    reason=(
                        "critical prerequisite(s) not yet at 'demonstrated': "
                        + ", ".join(missing)
                    ),
                    expected_outcome="prerequisite nodes raised to 'demonstrated'",
                    candidate_actions=candidates,
                    required_evidence=["prerequisite mastery", "low-hint success"],
                    node_id=(node or {}).get("node_id"),
                    trigger_event=trigger_event or "prerequisite_gap",
                ),
                guard_checks,
            )

        # 3. Learning friction -> reduce granularity, raise support (section 15.3)
        if friction["triggered"]:
            candidates = ["Give Hint", "Provide Worked Example", "Ask Guiding Question"]
            return self._finalize(
                PolicyDecision(
                    selected_strategy="Scaffolding",
                    selected_action="Give Hint",
                    reason=(
                        "learning friction detected: "
                        + "; ".join(friction["signals"])
                    ),
                    expected_outcome="learner re-attempts with reduced task granularity",
                    candidate_actions=candidates,
                    required_evidence=["re-attempt"],
                    node_id=(node or {}).get("node_id"),
                    trigger_event=trigger_event or "friction",
                ),
                guard_checks,
            )

        # 4. Repeated failure / rising hint dependency -> worked example (9.5)
        if (
            friction["consecutive_failures"] >= max_retry
            or hint_dep > hint_high
            or (friction["consecutive_high_hint"] >= max_retry)
        ):
            candidates = ["Provide Worked Example", "Give Partial Derivation", "Give Hint"]
            return self._finalize(
                PolicyDecision(
                    selected_strategy="Worked Example",
                    selected_action="Provide Worked Example",
                    reason=(
                        f"repeated failure ({friction['consecutive_failures']}) or high hint "
                        f"dependency ({hint_dep:.2f} > {hint_high:.2f}); a full demonstration "
                        "is now justified"
                    ),
                    expected_outcome="self-explanation plus a new independent problem",
                    candidate_actions=candidates,
                    required_evidence=["self-explanation", "new problem result"],
                    node_id=(node or {}).get("node_id"),
                    trigger_event=trigger_event or "repeated_failure",
                    disclosure_level=3,
                ),
                guard_checks,
            )

        # 5. No evidence at all -> teach the concept
        if not ctx["recent_attempts"]:
            candidates = ["Explain Concept", "Show Visualization", "Generate Practice"]
            return self._finalize(
                PolicyDecision(
                    selected_strategy="Explanation",
                    selected_action="Explain Concept",
                    reason="no attempt evidence for this node yet; establish the concept first",
                    expected_outcome="learner can restate the concept and attempt a task",
                    candidate_actions=candidates,
                    required_evidence=["understanding check"],
                    node_id=(node or {}).get("node_id"),
                    trigger_event=trigger_event or "node_started",
                ),
                guard_checks,
            )

        # 6. Low reasoning quality -> socratic probing (9.3)
        reasoning = state.get("reasoning_quality")
        if reasoning is not None and float(reasoning) < reasoning_low:
            candidates = ["Ask Guiding Question", "Give Hint", "Explain Concept"]
            return self._finalize(
                PolicyDecision(
                    selected_strategy="Socratic",
                    selected_action="Ask Guiding Question",
                    reason=f"reasoning_quality {float(reasoning):.2f} < {reasoning_low:.2f}",
                    expected_outcome="reasoning gap surfaced and addressed",
                    candidate_actions=candidates,
                    required_evidence=["reasoning trace"],
                    node_id=(node or {}).get("node_id"),
                    trigger_event=trigger_event or "reasoning_gap",
                ),
                guard_checks,
            )

        # 7. Mastery reached but not yet demonstrated independently -> retrieval (9.6)
        if stage_index(stage) < stage_index("demonstrated") and mastery >= mastery_threshold:
            candidates = ["Generate Retrieval Item", "Generate Practice", "Ask Guiding Question"]
            return self._finalize(
                PolicyDecision(
                    selected_strategy="Retrieval Practice",
                    selected_action="Generate Retrieval Item",
                    reason=(
                        f"mastery {mastery:.2f} >= {mastery_threshold:.2f} but evidence stage "
                        f"is still '{stage}'; need independent retrieval evidence"
                    ),
                    expected_outcome="independent, low-hint success recorded",
                    candidate_actions=candidates,
                    required_evidence=["unassisted success"],
                    node_id=(node or {}).get("node_id"),
                    trigger_event=trigger_event or "mastery_without_evidence",
                ),
                guard_checks,
            )

        # 8. Transfer required and not yet passed (section 13.6 / 21.4)
        if (
            ctx["transfer_requirement"]
            and stage_index(stage) >= stage_index("demonstrated")
            and not ctx["prerequisite_state"].get("transfer_passed")
        ):
            candidates = ["Run Transfer Probe", "Generate Practice"]
            return self._finalize(
                PolicyDecision(
                    selected_strategy="Transfer Probe",
                    selected_action="Run Transfer Probe",
                    reason="node requires generalization evidence and no passing probe exists",
                    expected_outcome="transfer score at or above the configured threshold",
                    candidate_actions=candidates,
                    required_evidence=["transfer_probe result"],
                    node_id=(node or {}).get("node_id"),
                    trigger_event=trigger_event or "transfer_required",
                ),
                guard_checks,
            )

        # 9. Due review for this node -> retrieval (section 21.5)
        if ctx["due_reviews"]:
            due_here = [r for r in ctx["due_reviews"] if r["node_id"] == (node or {}).get("node_id")]
            if due_here:
                candidates = ["Generate Retrieval Item", "Schedule Review"]
                return self._finalize(
                    PolicyDecision(
                        selected_strategy="Retrieval Practice",
                        selected_action="Generate Retrieval Item",
                        reason=f"{len(due_here)} review item(s) due for this node",
                        expected_outcome="retention evidence refreshed",
                        candidate_actions=candidates,
                        required_evidence=["review rating"],
                        node_id=(node or {}).get("node_id"),
                        trigger_event=trigger_event or "review_due",
                    ),
                    guard_checks,
                )

        # 10. Interleaving (section 31). A *conditional* strategy, never a global
        #     default: it only applies once the relevant knowledge has basic
        #     stability and the extra cognitive load is acceptable.
        plan = self.interleaving_plan(ctx)
        if plan["applicable"]:
            candidates = ["Generate Practice", "Generate Retrieval Item", "Record Reflection"]
            return self._finalize(
                PolicyDecision(
                    selected_strategy="Retrieval Practice",
                    selected_action="Generate Practice",
                    reason=(
                        f"interleaving applies: {plan['reason']}; mix tasks across "
                        + ", ".join(plan["node_ids"])
                    ),
                    expected_outcome=(
                        "the learner discriminates between related concepts instead of "
                        "pattern-matching a single familiar item type"
                    ),
                    candidate_actions=candidates,
                    required_evidence=["interleaved practice result"],
                    node_id=(node or {}).get("node_id"),
                    trigger_event=trigger_event or "interleaving",
                    interleaving=plan,
                ),
                guard_checks,
            )

        # 11. Nothing blocking -> consolidate, then advance is a guard decision
        candidates = ["Generate Practice", "Record Reflection", "Advance Unit"]
        return self._finalize(
            PolicyDecision(
                selected_strategy="Retrieval Practice",
                selected_action="Generate Practice",
                reason=(
                    "no blocking signal; consolidate with practice while the State Guard "
                    "decides whether the unit may advance"
                ),
                expected_outcome="stabilised performance and a guard-eligible advance",
                candidate_actions=candidates,
                required_evidence=["practice result"],
                node_id=(node or {}).get("node_id"),
                trigger_event=trigger_event or "consolidation",
            ),
            guard_checks,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def commit(
        self,
        session_id: str,
        decision: PolicyDecision,
        *,
        current_state: Mapping[str, Any] | None = None,
        trigger_event: str | None = None,
    ) -> str:
        """Persist a decision to ``pedagogical_decisions`` for replay."""
        decision_id = new_id("dec")
        self._db.execute(
            "INSERT INTO pedagogical_decisions "
            "(decision_id, session_id, node_id, trigger_event, current_state, candidate_actions, "
            " selected_policy, selected_action, rationale, expected_outcome, actual_result, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                decision_id,
                session_id,
                decision.node_id,
                trigger_event or decision.trigger_event,
                json.dumps(current_state, ensure_ascii=False, default=str) if current_state else None,
                json.dumps(decision.candidate_actions, ensure_ascii=False),
                decision.selected_strategy,
                decision.selected_action,
                decision.reason,
                decision.expected_outcome,
                None,
                now_ts(),
            ),
        )
        if self._events is not None:
            self._events.emit(
                "policy_committed",
                session_id=session_id,
                node_id=decision.node_id,
                payload=decision.as_dict(),
            )
        return decision_id

    def decision_log(self, session_id: str, limit: int = 50) -> list[dict]:
        rows = self._db.query(
            "SELECT * FROM pedagogical_decisions WHERE session_id = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (session_id, limit),
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Interleaving (section 31)
    # ------------------------------------------------------------------
    def interleaving_plan(self, context: dict) -> dict:
        """Decide whether interleaved practice is appropriate right now.

        Section 31.2 requires all three of:

        1. the relevant knowledge has basic stability;
        2. discriminating between the concepts is useful;
        3. the additional cognitive load is acceptable.

        It is a **conditional strategy, not a global default** - the default
        answer is "not applicable", and the caller must be able to say why.
        """
        node = context.get("current_node")
        if not node:
            return {"applicable": False, "reason": "no current knowledge node"}

        session_id = (context.get("session") or {}).get("session_id")
        mode = str(self._get("interleaving_enabled", "conditional", session_id)).lower()
        if mode in {"false", "off", "never", "disabled"}:
            return {"applicable": False, "reason": "interleaving is disabled by configuration"}

        learner_id = context["learner_id"]
        state = context.get("knowledge_state") or {}
        stage = context.get("evidence_stage", "estimated")
        hint_dependency = float(state.get("hint_dependency") or 0.0)
        friction = context.get("learning_friction") or {}

        # Condition 1 - the current node itself must have basic stability.
        if stage_index(stage) < stage_index("practiced"):
            return {
                "applicable": False,
                "reason": f"current node is only at '{stage}'; basic stability is required first",
            }

        unit_tag = node.get("unit_tag")
        if not unit_tag:
            return {
                "applicable": False,
                "reason": "current node has no unit_tag, so there is nothing to interleave with",
            }

        # Condition 2 - at least one sibling concept is stable enough to mix in.
        rows = self._db.query(
            "SELECT kn.node_id, kn.title, kn.bloom_level, "
            "       COALESCE(lks.evidence_stage, 'estimated') AS evidence_stage "
            "FROM knowledge_nodes kn "
            "LEFT JOIN learner_knowledge_state lks "
            "  ON lks.node_id = kn.node_id AND lks.learner_id = ? "
            "WHERE kn.session_id = ? AND kn.unit_tag = ? ORDER BY kn.node_id",
            (learner_id, session_id, unit_tag),
        )
        stable = [
            {"node_id": r["node_id"], "title": r["title"], "bloom_level": r["bloom_level"],
             "evidence_stage": r["evidence_stage"]}
            for r in rows
            if stage_index(r["evidence_stage"]) >= stage_index("practiced")
        ]
        if len(stable) < 2:
            return {
                "applicable": False,
                "reason": (
                    f"only {len(stable)} node(s) in unit '{unit_tag}' have basic stability; "
                    "at least 2 are needed to discriminate between concepts"
                ),
                "unit_tag": unit_tag,
            }

        # Condition 3 - the extra load must be acceptable.
        if friction.get("triggered"):
            return {
                "applicable": False,
                "reason": "learning friction is present; additional load is not acceptable",
                "unit_tag": unit_tag,
            }
        hint_high = float(self._get("hint_dependency_high", 0.70, session_id))
        if hint_dependency > hint_high:
            return {
                "applicable": False,
                "reason": (
                    f"hint dependency {hint_dependency:.2f} exceeds {hint_high:.2f}; "
                    "consolidate with support before interleaving"
                ),
                "unit_tag": unit_tag,
            }

        return {
            "applicable": True,
            "reason": (
                f"{len(stable)} nodes in unit '{unit_tag}' have basic stability and "
                f"load is acceptable (hint dependency {hint_dependency:.2f})"
            ),
            "unit_tag": unit_tag,
            "nodes": stable,
            "node_ids": [n["node_id"] for n in stable],
            "configuration": mode,
        }

    # ------------------------------------------------------------------
    # Retention queries
    # ------------------------------------------------------------------
    def due_reviews(self, learner_id: str, now: int | None = None) -> list[dict]:
        reference = now if now is not None else now_ts()
        rows = self._db.query(
            "SELECT * FROM review_items WHERE learner_id = ? AND next_review_at IS NOT NULL "
            "AND next_review_at <= ? ORDER BY next_review_at ASC",
            (learner_id, reference),
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _finalize(self, decision: PolicyDecision, guard_checks: list[dict] | None) -> PolicyDecision:
        decision.state_guard_checks = guard_checks or []
        return decision

    def _recent_attempts(self, session_id: str, node_id: str | None, limit: int = 10) -> list[dict]:
        if node_id:
            rows = self._db.query(
                "SELECT la.*, ar.overall_score, ar.correctness, ar.assessor_type "
                "FROM learning_attempts la "
                "LEFT JOIN assessment_results ar ON ar.attempt_id = la.attempt_id "
                "WHERE la.session_id = ? AND la.node_id = ? "
                "ORDER BY la.created_at DESC, la.rowid DESC LIMIT ?",
                (session_id, node_id, limit),
            )
        else:
            rows = self._db.query(
                "SELECT la.*, ar.overall_score, ar.correctness, ar.assessor_type "
                "FROM learning_attempts la "
                "LEFT JOIN assessment_results ar ON ar.attempt_id = la.attempt_id "
                "WHERE la.session_id = ? ORDER BY la.created_at DESC, la.rowid DESC LIMIT ?",
                (session_id, limit),
            )
        return [dict(r) for r in rows]

    def _active_misconceptions(self, learner_id: str, node_id: str | None) -> list[dict]:
        if not node_id:
            return []
        rows = self._db.query(
            "SELECT * FROM misconceptions WHERE learner_id = ? AND node_id = ? "
            "AND status = 'active' ORDER BY severity DESC, last_seen_at DESC",
            (learner_id, node_id),
        )
        return [dict(r) for r in rows]

    def _friction_signals(self, attempts: list[dict]) -> dict:
        """Observable interaction signals only - never psychological claims (15.1)."""
        window = int(self._get("friction_window", 3))
        trigger = int(self._get("friction_trigger_consecutive", 3))
        recent = attempts[:window]

        consecutive_failures = 0
        for attempt in attempts:
            score = attempt.get("overall_score")
            if score is None:
                break
            if float(score) >= 0.6:
                break
            consecutive_failures += 1

        consecutive_high_hint = 0
        for attempt in attempts:
            if int(attempt.get("hint_level") or 0) >= 2:
                consecutive_high_hint += 1
            else:
                break

        signals: list[str] = []
        if consecutive_failures >= trigger:
            signals.append(f"{consecutive_failures} consecutive unsuccessful attempts")
        if consecutive_high_hint >= trigger:
            signals.append(f"{consecutive_high_hint} consecutive high-hint attempts")
        if recent and all((a.get("response_time") or 99) < 5 for a in recent):
            signals.append("repeated very short responses")
        if recent and any(int(a.get("hint_level") or 0) >= 3 for a in recent):
            signals.append("frequent answer requests")

        return {
            "window": window,
            "consecutive_failures": consecutive_failures,
            "consecutive_high_hint": consecutive_high_hint,
            "signals": signals,
            "triggered": bool(signals),
        }

    def _prerequisite_status(self, learner_id: str, node_id: str | None) -> dict:
        if not node_id:
            return {"missing": [], "transfer_passed": False}
        rows = self._db.query(
            "SELECT pre_node_id FROM knowledge_edges "
            "WHERE post_node_id = ? AND relation_type = 'prerequisite'",
            (node_id,),
        )
        missing: list[str] = []
        for row in rows:
            stage = self._db.scalar(
                "SELECT evidence_stage FROM learner_knowledge_state "
                "WHERE learner_id = ? AND node_id = ?",
                (learner_id, row["pre_node_id"]),
                "estimated",
            )
            if stage_index(stage or "estimated") < stage_index("demonstrated"):
                missing.append(row["pre_node_id"])

        pass_score = float(self._get("transfer_pass_score", 0.70))
        best = self._db.scalar(
            "SELECT MAX(score) FROM transfer_results WHERE learner_id = ? AND node_id = ?",
            (learner_id, node_id),
        )
        return {
            "missing": missing,
            "transfer_passed": best is not None and float(best) >= pass_score,
            "best_transfer_score": best,
        }

    def _transfer_requirement(self, node: Mapping[str, Any] | None, session_id: str | None = None) -> bool:
        from leap.runtime.state_guard import transfer_required

        if not node:
            return False
        return bool(transfer_required(node, self._session_cfg(session_id)))

    def _session_cfg(self, session_id: str | None) -> Any:
        """A read-only config view with the session's overrides applied.

        Used where a helper expects a ``cfg`` object rather than a single key.
        """
        overrides = self.session_overrides(session_id) if session_id else {}
        if not overrides:
            return self._cfg
        return _OverrideView(self._cfg, overrides)

    def learning_preferences(self, session_id: str) -> dict:
        """Strategy/action preferences attached to the session's mode.

        These do **not** bypass State Guard checks - they are guidance for the
        host agent's presentation choice.
        """
        raw = self._db.scalar(
            "SELECT policy_overrides FROM learning_sessions WHERE session_id = ?", (session_id,)
        )
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        prefs = parsed.get("preferences") if isinstance(parsed, dict) else None
        return dict(prefs) if isinstance(prefs, dict) else {}


class _OverrideView:
    """Minimal ``cfg``-shaped view: session overrides shadow global config."""

    def __init__(self, base: Any, overrides: Mapping[str, Any]) -> None:
        self._base = base
        self._overrides = dict(overrides)

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._overrides:
            return self._overrides[key]
        return self._base.get(key, default) if hasattr(self._base, "get") else default

    def as_dict(self) -> dict:
        base = self._base.as_dict() if hasattr(self._base, "as_dict") else {}
        base.update(self._overrides)
        return base
