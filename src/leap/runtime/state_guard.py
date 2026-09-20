"""Server-side State Guard (section 19).

The guard is the *only* component allowed to authorise a state transition.
The host agent may propose ``advance_unit``; the runtime decides.

Two invariants matter here:

* **Hard invariant** - prerequisites met, assessment sufficient, evidence
  sufficient, transfer completed when required, state version valid. These are
  enforced structurally and cannot be switched off by prompt text.
* **Configurable policy** - thresholds, whether transfer is required, which
  nodes are mandatory, manual override rights. These are read from config so
  the Pedagogical Policy engine can shape them (section 19.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from leap.runtime.evidence import stage_index
from leap.storage import Database, now_ts

__all__ = ["GuardDecision", "StateGuard", "BLOOM_ORDER", "bloom_rank", "transfer_required"]

#: Bloom levels, English and Chinese labels, lowest to highest.
BLOOM_ORDER: tuple[str, ...] = (
    "remember", "understand", "apply", "analyze", "evaluate", "create",
)

_BLOOM_ALIASES: dict[str, str] = {
    "remember": "remember", "knowledge": "remember", "记忆": "remember", "识记": "remember",
    "understand": "understand", "comprehension": "understand", "理解": "understand", "领会": "understand",
    "apply": "apply", "application": "apply", "应用": "apply", "运用": "apply",
    "analyze": "analyze", "analysis": "analyze", "分析": "analyze",
    "evaluate": "evaluate", "evaluation": "evaluate", "评价": "evaluate",
    "create": "create", "synthesis": "create", "创造": "create", "综合": "create",
}


def bloom_rank(level: str | None) -> int:
    """Return the ordinal position of a Bloom level, or -1 when unknown."""
    if not level:
        return -1
    key = _BLOOM_ALIASES.get(str(level).strip().lower())
    if key is None:
        return -1
    return BLOOM_ORDER.index(key)


def transfer_required(node: Mapping[str, Any], cfg: Any) -> bool:
    """Reference rule for ``default_transfer_requirement = conditional`` (13.6).

    Transfer is required when the node targets ``application`` or above *and*
    is not a pure memory/comprehension node. A node may also opt in explicitly
    through its ``transfer_requirements`` column. The Policy engine may
    override this entirely.
    """
    explicit = str(node.get("transfer_requirements") or "").strip().lower()
    if explicit in {"required", "true", "yes", "1", "必须", "是"}:
        return True
    if explicit in {"none", "false", "no", "0", "不需要", "否", "skip"}:
        return False

    get = cfg.get if cfg is not None and hasattr(cfg, "get") else (lambda _k, d=None: d)
    mode = str(get("default_transfer_requirement", "conditional")).lower()
    if mode in {"never", "false", "off"}:
        return False
    if mode in {"always", "true", "on"}:
        return True

    rank = bloom_rank(node.get("bloom_level"))
    if rank < 0:
        # Unknown level: be conservative and require transfer only if the node
        # explicitly claims an application-level objective.
        objective = str(node.get("learning_objective") or "").lower()
        return "apply" in objective or "应用" in objective
    return rank >= BLOOM_ORDER.index("apply")


@dataclass
class GuardDecision:
    """Structured outcome of a guard check (mirrors section 19.5)."""

    decision: str
    reason: str
    checks: dict[str, bool] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    node_id: str | None = None

    @property
    def allowed(self) -> bool:
        return self.decision == "ALLOW"

    def as_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "node_id": self.node_id,
            **self.checks,
            "details": self.details,
        }

    @classmethod
    def allow(cls, reason: str = "all invariants satisfied", **kwargs: Any) -> "GuardDecision":
        return cls(decision="ALLOW", reason=reason, **kwargs)

    @classmethod
    def reject(cls, reason: str, **kwargs: Any) -> "GuardDecision":
        return cls(decision="REJECT", reason=reason, **kwargs)


class StateGuard:
    """Enforces the invariants that keep learner state consistent."""

    def __init__(self, db: Database, cfg: Any, events: Any = None, translator: Any = None) -> None:
        self._db = db
        self._cfg = cfg
        self._events = events
        if translator is None:
            from leap.i18n import translator_for

            translator = translator_for(cfg)
        self._i18n = translator

    def _t(self, key: str, **kwargs: Any) -> str:
        """Translate a learner-visible message."""
        return self._i18n.t(key, **kwargs)

    def _get(self, key: str, default: Any = None) -> Any:
        return self._cfg.get(key, default) if hasattr(self._cfg, "get") else default

    # ------------------------------------------------------------------
    # Domain grounding pre-check (section 19.2-1)
    # ------------------------------------------------------------------
    def check_domain_grounding(self, session_id: str) -> GuardDecision:
        """Block learner diagnostics until agent self-calibration is done."""
        session = self._db.query_one(
            "SELECT allow_skip_domain_grounding, domain_grounding_stage, "
            "benchmark_report_artifact_id FROM learning_sessions WHERE session_id = ?",
            (session_id,),
        )
        if session is None:
            return GuardDecision.reject(f"unknown session: {session_id}")

        allow_skip = bool(session["allow_skip_domain_grounding"])
        stage = session["domain_grounding_stage"]
        report_id = session["benchmark_report_artifact_id"]

        checks = {
            "allow_skip_domain_grounding": allow_skip,
            "domain_grounding_completed": stage == "completed",
            "benchmark_report_present": bool(report_id),
        }
        details = {"domain_grounding_stage": stage, "benchmark_report_artifact_id": report_id}

        if allow_skip:
            return GuardDecision.allow(
                self._t("domain_grounding.allow.waived"),
                checks=checks,
                details=details,
            )
        if stage != "completed" or not report_id:
            return GuardDecision.reject(
                self._t("domain_grounding.reject.not_completed"),
                checks=checks,
                details=details,
            )
        return GuardDecision.allow(
            self._t("domain_grounding.allow.completed"),
            checks=checks,
            details=details,
        )

    # ------------------------------------------------------------------
    # Optimistic concurrency (section 19.4)
    # ------------------------------------------------------------------
    def check_state_version(self, session_id: str, expected_version: int | None) -> GuardDecision:
        if expected_version is None:
            return GuardDecision.allow("no expected version supplied")
        current = self._db.scalar(
            "SELECT state_version FROM learning_sessions WHERE session_id = ?", (session_id,)
        )
        if current is None:
            return GuardDecision.reject(f"unknown session: {session_id}")
        if int(current) != int(expected_version):
            return GuardDecision.reject(
                f"stale state_version: expected {expected_version}, current {current}",
                details={"expected": expected_version, "current": int(current)},
            )
        return GuardDecision.allow("state_version matches")

    # ------------------------------------------------------------------
    # Node-level checks
    # ------------------------------------------------------------------
    def check_node(
        self,
        session_id: str,
        node_id: str,
        *,
        manual_override: bool = False,
        expected_state_version: int | None = None,
    ) -> GuardDecision:
        """Run every node-level invariant for a single knowledge node."""
        session = self._db.query_one(
            "SELECT learner_id, state_version FROM learning_sessions WHERE session_id = ?",
            (session_id,),
        )
        if session is None:
            return GuardDecision.reject(f"unknown session: {session_id}", node_id=node_id)

        learner_id = session["learner_id"]
        node = self._db.query_one(
            "SELECT * FROM knowledge_nodes WHERE node_id = ?", (node_id,)
        )
        if node is None:
            return GuardDecision.reject(f"unknown node: {node_id}", node_id=node_id)
        node = dict(node)

        # --- 1. prerequisites -------------------------------------------------
        missing = self._unmet_prerequisites(learner_id, node_id)
        prerequisites_met = not missing

        # --- 2. assessment sufficiency ---------------------------------------
        assessment_count = int(
            self._db.scalar(
                "SELECT COUNT(*) FROM assessment_results ar "
                "JOIN learning_attempts la ON la.attempt_id = ar.attempt_id "
                "WHERE la.session_id = ? AND la.node_id = ?",
                (session_id, node_id),
                0,
            )
        )
        assessment_sufficient = assessment_count >= 1

        # --- 3. evidence sufficiency -----------------------------------------
        state_row = self._db.query_one(
            "SELECT * FROM learner_knowledge_state WHERE learner_id = ? AND node_id = ?",
            (learner_id, node_id),
        )
        state = dict(state_row) if state_row else {}
        stage = state.get("evidence_stage", "estimated")
        evidence_sufficient = stage_index(stage) >= stage_index("demonstrated")

        # --- 4/5. transfer ----------------------------------------------------
        needs_transfer = transfer_required(node, self._cfg)
        transfer_done = True
        best_transfer = None
        if needs_transfer:
            pass_score = float(self._get("transfer_pass_score", 0.70))
            best_transfer = self._db.scalar(
                "SELECT MAX(score) FROM transfer_results WHERE learner_id = ? AND node_id = ?",
                (learner_id, node_id),
            )
            transfer_done = best_transfer is not None and float(best_transfer) >= pass_score

        # --- 6. state version -------------------------------------------------
        version_valid = True
        if expected_state_version is not None:
            version_valid = int(session["state_version"]) == int(expected_state_version)

        checks = {
            "prerequisites_met": prerequisites_met,
            "assessment_sufficient": assessment_sufficient,
            "evidence_sufficient": evidence_sufficient,
            "transfer_required": needs_transfer,
            "transfer_completed": transfer_done,
            "current_state_version_valid": version_valid,
            "manual_override": manual_override,
        }
        details = {
            "missing_prerequisites": missing,
            "assessment_count": assessment_count,
            "evidence_stage": stage,
            "best_transfer_score": best_transfer,
        }

        if manual_override:
            return GuardDecision.allow(
                "manual override applied; recorded for audit",
                checks=checks,
                details=details,
                node_id=node_id,
            )

        failures: list[str] = []
        if not prerequisites_met:
            failures.append(f"unmet prerequisites: {', '.join(missing)}")
        if not assessment_sufficient:
            failures.append("no assessment evidence recorded for this node")
        if not evidence_sufficient:
            failures.append(f"evidence stage '{stage}' is below 'demonstrated'")
        if needs_transfer and not transfer_done:
            failures.append(
                "required transfer evidence is missing"
                if best_transfer is None
                else f"transfer score {best_transfer} is below the required threshold"
            )
        if not version_valid:
            failures.append("stale state_version")

        if failures:
            return GuardDecision.reject(
                "; ".join(failures), checks=checks, details=details, node_id=node_id
            )
        return GuardDecision.allow(
            "all node invariants satisfied", checks=checks, details=details, node_id=node_id
        )

    # ------------------------------------------------------------------
    # Unit-level (batch) checks
    # ------------------------------------------------------------------
    def unit_node_ids(self, session_id: str, unit_tag: str) -> list[str]:
        rows = self._db.query(
            "SELECT node_id FROM knowledge_nodes WHERE session_id = ? AND unit_tag = ? "
            "ORDER BY node_id",
            (session_id, unit_tag),
        )
        return [r["node_id"] for r in rows]

    def check_unit(
        self,
        session_id: str,
        unit_tag: str,
        *,
        manual_override: bool = False,
        expected_state_version: int | None = None,
    ) -> GuardDecision:
        """``advance_unit`` semantics: every node in the unit must pass.

        This is a *business-level batch wrapper* - there is deliberately no
        separate unit table (section 6.6).
        """
        node_ids = self.unit_node_ids(session_id, unit_tag)
        if not node_ids:
            return GuardDecision.reject(f"unit '{unit_tag}' has no nodes in this session")

        per_node: dict[str, dict] = {}
        failures: list[str] = []
        for node_id in node_ids:
            decision = self.check_node(
                session_id,
                node_id,
                manual_override=manual_override,
                expected_state_version=expected_state_version,
            )
            per_node[node_id] = decision.as_dict()
            if not decision.allowed:
                failures.append(f"{node_id}: {decision.reason}")

        checks = {
            "all_nodes_pass": not failures,
            "node_count": len(node_ids),
        }
        details = {"unit_tag": unit_tag, "nodes": per_node}

        if failures:
            return GuardDecision.reject(
                "unit rejected because not every node passed: " + " | ".join(failures),
                checks=checks,
                details=details,
            )
        return GuardDecision.allow(
            f"all {len(node_ids)} node(s) in unit '{unit_tag}' passed",
            checks=checks,
            details=details,
        )

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------
    def bump_state_version(self, session_id: str) -> int:
        """Increment and return the session's state version (optimistic lock)."""
        with self._db.transaction():
            self._db.execute(
                "UPDATE learning_sessions SET state_version = state_version + 1, updated_at = ? "
                "WHERE session_id = ?",
                (now_ts(), session_id),
            )
        return int(
            self._db.scalar(
                "SELECT state_version FROM learning_sessions WHERE session_id = ?",
                (session_id,),
                0,
            )
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _unmet_prerequisites(self, learner_id: str, node_id: str) -> list[str]:
        """Prerequisite nodes that have not yet reached ``demonstrated``."""
        rows = self._db.query(
            "SELECT pre_node_id FROM knowledge_edges "
            "WHERE post_node_id = ? AND relation_type = 'prerequisite'",
            (node_id,),
        )
        unmet: list[str] = []
        for row in rows:
            pre_id = row["pre_node_id"]
            stage = self._db.scalar(
                "SELECT evidence_stage FROM learner_knowledge_state "
                "WHERE learner_id = ? AND node_id = ?",
                (learner_id, pre_id),
                "estimated",
            )
            if stage_index(stage or "estimated") < stage_index("demonstrated"):
                unmet.append(pre_id)
        return unmet

    def unmet_prerequisites_for_nodes(
        self, learner_id: str, node_ids: Iterable[str]
    ) -> dict[str, list[str]]:
        return {nid: self._unmet_prerequisites(learner_id, nid) for nid in node_ids}
