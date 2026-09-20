"""Assessment tools (section 22.6 / 22.8) and state estimation glue.

Two responsibilities are kept apart (section 10.1)::

    Assessment      -> produces evidence about THIS attempt
    State estimation -> folds that evidence into long-term learner state

``assess_response`` normalises and validates the agent's multi-dimensional
judgement; ``commit_assessment`` persists it and drives the server-side BKT
update. ``mastery_probability`` is therefore never authored by the LLM
(section 10.2-1).
"""

from __future__ import annotations

from typing import Any, Mapping

from leap.runtime.evidence import EvidenceInput, evaluate_stage, stage_index
from leap.storage import new_id, now_ts
from leap.tools.base import LeapToolMixin, ToolError

__all__ = ["AssessmentTools", "ASSESSOR_TYPES", "SCORE_DIMENSIONS"]

ASSESSOR_TYPES: tuple[str, ...] = ("human", "model", "rule", "hybrid", "external_estimator")

#: Dimensions that participate in ``overall_score`` (section 10.3-1).
#: ``transfer`` and ``hint_dependency`` are deliberately excluded - they are
#: separate Policy inputs, not part of the aggregate.
SCORE_DIMENSIONS: tuple[str, ...] = (
    "correctness",
    "conceptual_understanding",
    "reasoning_quality",
    "application",
)

#: Smoothing factor for the running hint-dependency estimate. Engineering
#: heuristic: a single heavily-hinted attempt should not erase a clean history.
_HINT_DEPENDENCY_ALPHA = 0.4

#: An attempt counts as "successful" for evidence purposes at or above this.
_SUCCESS_SCORE = 0.60

#: A success at or below this hint level counts as independent (section 11.4).
_INDEPENDENT_HINT_MAX = 1


class AssessmentTools(LeapToolMixin):
    """Multi-dimensional assessment and learner-state updating."""

    # ------------------------------------------------------------------
    # 22.6 Assessment generation
    # ------------------------------------------------------------------
    def generate_assessment(
        self,
        session_id: str,
        node_id: str | None = None,
        *,
        question_type: str | None = None,
        count: int = 1,
    ) -> dict:
        """Return an assessment blueprint for the host agent to materialise."""
        session = self.require_session(session_id)
        node_id = node_id or session.get("current_node_id")
        node = self.require_node(node_id) if node_id else None

        return self.ok(
            session_id=session_id,
            node_id=node_id,
            count=count,
            question_type=question_type,
            dimensions=list(SCORE_DIMENSIONS) + ["transfer", "hint_dependency", "confidence"],
            excluded_from_overall_score=["transfer", "hint_dependency"],
            rubric={
                "general": ["correctness", "conceptual_understanding", "reasoning_quality",
                            "application", "transfer", "hint_dependency", "confidence"],
                "math": ["concept", "condition_identification", "formula_selection", "derivation",
                         "computation", "conclusion", "transfer"],
                "coding": ["functional_correctness", "logic", "edge_cases", "explanation",
                           "complexity", "debugging", "independence"],
                "open_ended": ["conclusion", "evidence", "reasoning", "concept", "support", "expression"],
            },
            node=node,
            guidance=(
                "Ask the learner, judge each dimension in [0,1], then call assess_response "
                "followed by commit_assessment with the raw answer text."
            ),
        )

    def generate_transfer_probe(
        self, session_id: str, node_id: str | None = None
    ) -> dict:
        """Return a transfer-probe blueprint (section 13.6)."""
        session = self.require_session(session_id)
        node_id = node_id or session.get("current_node_id")
        node = self.require_node(node_id) if node_id else None

        from leap.runtime.state_guard import transfer_required

        required = bool(node) and transfer_required(node, self.cfg)
        return self.ok(
            session_id=session_id,
            node_id=node_id,
            transfer_required=required,
            transfer_levels=["near", "variation", "far", "integrated"],
            variations=[
                "restate the task in different wording",
                "change parameters or input data",
                "change the scenario or domain framing",
                "embed the node inside an integrated multi-node task",
            ],
            pass_score=float(self.conf("transfer_pass_score", 0.70)),
            node=node,
        )

    # ------------------------------------------------------------------
    # 22.6 Assessment normalisation
    # ------------------------------------------------------------------
    def assess_response(
        self,
        session_id: str,
        scores: Mapping[str, Any],
        *,
        raw_answer: str | None = None,
        assessor_type: str = "model",
        assessor_confidence: float = 1.0,
    ) -> dict:
        """Validate dimension scores and compute the weighted ``overall_score``.

        This does **not** persist anything and does **not** touch learner state;
        it exists so the host agent can see exactly what will be committed.
        """
        self.require_session(session_id)
        self._check_assessor_type(assessor_type)
        normalised = self._normalise_scores(scores)
        overall = self._overall_score(normalised)

        return self.ok(
            session_id=session_id,
            scores=normalised,
            overall_score=overall,
            weights=self.conf("overall_score_weights", {}),
            excluded_from_overall_score=["transfer", "hint_dependency"],
            assessor_type=assessor_type,
            assessor_confidence=float(assessor_confidence),
            raw_answer_present=bool(raw_answer),
            warning=None if raw_answer else "raw_answer is required when committing this assessment",
        )

    # ------------------------------------------------------------------
    # 22.8 Attempt + commit
    # ------------------------------------------------------------------
    def submit_attempt(
        self,
        session_id: str,
        answer: str,
        *,
        item_id: str | None = None,
        node_id: str | None = None,
        hint_level: int = 0,
        response_time: float | None = None,
        predicted_performance: float | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Record a learner attempt and return its id for assessment."""
        session = self.require_session(session_id)
        answer = self.require_text(answer, "answer")
        node_id = node_id or session.get("current_node_id")

        max_hint = int(self.conf("max_hint_level", 3))
        if not 0 <= int(hint_level) <= max_hint + 1:
            raise ToolError(
                "invalid_hint_level",
                f"hint_level must be between 0 and {max_hint + 1}",
            )

        attempt_index = int(
            self.db.scalar(
                "SELECT COUNT(*) FROM learning_attempts WHERE session_id = ? AND node_id IS ?",
                (session_id, node_id),
                0,
            )
        ) + 1
        attempt_id = new_id("att")
        ts = now_ts()

        with self.db.transaction():
            self.db.execute(
                "INSERT INTO learning_attempts "
                "(attempt_id, session_id, item_id, node_id, answer, response_time, hint_level, "
                " attempt_index, predicted_performance, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (attempt_id, session_id, item_id, node_id, answer, response_time, int(hint_level),
                 attempt_index, predicted_performance, ts),
            )
            self.db.execute(
                "UPDATE learning_sessions SET updated_at = ? WHERE session_id = ?", (ts, session_id)
            )
        self.events.emit(
            "attempt_submitted", session_id=session_id, learner_id=session["learner_id"],
            node_id=node_id,
            payload={"attempt_id": attempt_id, "hint_level": int(hint_level),
                     "attempt_index": attempt_index},
            request_id=request_id,
        )
        return self.ok(attempt_id=attempt_id, attempt_index=attempt_index, node_id=node_id)

    def commit_assessment(
        self,
        attempt_id: str,
        raw_answer: str,
        *,
        assessor_type: str = "model",
        correctness: float | None = None,
        conceptual_understanding: float | None = None,
        reasoning_quality: float | None = None,
        application: float | None = None,
        transfer: float | None = None,
        hint_dependency: float | None = None,
        confidence: float | None = None,
        assessor_confidence: float = 1.0,
        expected_state_version: int | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Persist assessment evidence and update learner state.

        ``raw_answer`` and ``assessor_type`` are mandatory (section 22.8): the
        original learner response is never discarded, so every state change can
        be audited later.
        """
        attempt_id = self.require_text(attempt_id, "attempt_id")
        raw_answer = self.require_text(raw_answer, "raw_answer")
        self._check_assessor_type(assessor_type)

        attempt = self.db.query_one(
            "SELECT * FROM learning_attempts WHERE attempt_id = ?", (attempt_id,)
        )
        if attempt is None:
            raise ToolError("unknown_attempt", f"attempt not found: {attempt_id}")
        attempt = dict(attempt)

        session_id = attempt["session_id"]
        node_id = attempt.get("node_id")
        session = self.require_session(session_id)

        if expected_state_version is not None:
            version_check = self.guard.check_state_version(session_id, expected_state_version)
            if not version_check.allowed:
                raise ToolError("stale_state_version", version_check.reason, version_check.as_dict())

        scores = self._normalise_scores(
            {
                "correctness": correctness,
                "conceptual_understanding": conceptual_understanding,
                "reasoning_quality": reasoning_quality,
                "application": application,
                "transfer": transfer,
                "hint_dependency": hint_dependency,
                "confidence": confidence,
            }
        )
        overall = self._overall_score(scores)

        learner_id = session["learner_id"]
        previous_state = self._load_state(learner_id, node_id) if node_id else None
        stage_before = (previous_state or {}).get("evidence_stage", "estimated")

        # --- snapshot stage for THIS attempt (immutable history) -----------
        snapshot_stage = self._snapshot_stage(attempt, scores, overall)

        result_id = new_id("res")
        ts = now_ts()
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO assessment_results "
                "(result_id, attempt_id, correctness, conceptual_understanding, reasoning_quality, "
                " application, transfer, hint_dependency, confidence, overall_score, evidence_stage, "
                " assessor_type, raw_answer, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    result_id, attempt_id, scores["correctness"],
                    scores["conceptual_understanding"], scores["reasoning_quality"],
                    scores["application"], scores["transfer"], scores["hint_dependency"],
                    scores["confidence"], overall, snapshot_stage, assessor_type, raw_answer, ts,
                ),
            )

        new_state = None
        if node_id:
            new_state = self._update_learner_state(
                learner_id=learner_id,
                node_id=node_id,
                session_id=session_id,
                previous=previous_state,
                scores=scores,
                overall=overall,
                assessor_confidence=float(assessor_confidence),
                hint_level=int(attempt.get("hint_level") or 0),
                attempt_created_at=int(attempt.get("created_at") or ts),
            )

        self.events.emit(
            "assessment_committed", session_id=session_id, learner_id=learner_id, node_id=node_id,
            payload={
                "result_id": result_id, "attempt_id": attempt_id,
                "overall_score": overall, "assessor_type": assessor_type,
                "stage_before": stage_before,
                "stage_after": (new_state or {}).get("evidence_stage", stage_before),
            },
            request_id=request_id,
        )
        self.guard.bump_state_version(session_id)

        return self.ok(
            result_id=result_id,
            attempt_id=attempt_id,
            overall_score=overall,
            scores=scores,
            evidence_stage_snapshot=snapshot_stage,
            learner_state=new_state,
            stage_before=stage_before,
            stage_after=(new_state or {}).get("evidence_stage", stage_before),
        )

    # ------------------------------------------------------------------
    # Misconceptions
    # ------------------------------------------------------------------
    def assess_misconception(
        self,
        learner_id: str,
        node_id: str,
        misconception: str,
        *,
        severity: float = 0.5,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Record an active misconception in its authoritative table (23.7)."""
        learner_id = self.require_text(learner_id, "learner_id")
        node_id = self.require_text(node_id, "node_id")
        misconception = self.require_text(misconception, "misconception")
        self.require_node(node_id)
        ts = now_ts()

        with self.db.transaction():
            existing = self.db.query_one(
                "SELECT id FROM misconceptions WHERE learner_id = ? AND node_id = ? "
                "AND misconception = ? AND status = 'active'",
                (learner_id, node_id, misconception),
            )
            if existing:
                misconception_id = int(existing["id"])
                self.db.execute(
                    "UPDATE misconceptions SET severity = ?, last_seen_at = ? WHERE id = ?",
                    (float(severity), ts, misconception_id),
                )
            else:
                cursor = self.db.execute(
                    "INSERT INTO misconceptions "
                    "(learner_id, node_id, misconception, severity, status, last_seen_at) "
                    "VALUES (?,?,?,?,'active',?)",
                    (learner_id, node_id, misconception, float(severity), ts),
                )
                misconception_id = int(cursor.lastrowid)

        self._refresh_misconception_cache(learner_id, node_id)
        self.events.emit(
            "misconception_detected", session_id=session_id, learner_id=learner_id, node_id=node_id,
            payload={"misconception_id": misconception_id, "misconception": misconception,
                     "severity": float(severity)},
            request_id=request_id,
        )
        return self.ok(misconception_id=misconception_id, learner_id=learner_id, node_id=node_id)

    def resolve_misconception(
        self, misconception_id: int, *, session_id: str | None = None
    ) -> dict:
        row = self.db.query_one("SELECT * FROM misconceptions WHERE id = ?", (misconception_id,))
        if row is None:
            raise ToolError("unknown_misconception", f"misconception not found: {misconception_id}")
        ts = now_ts()
        with self.db.transaction():
            self.db.execute(
                "UPDATE misconceptions SET status = 'resolved', resolved_at = ? WHERE id = ?",
                (ts, int(misconception_id)),
            )
        self._refresh_misconception_cache(row["learner_id"], row["node_id"])
        return self.ok(misconception_id=int(misconception_id), status="resolved")

    # ------------------------------------------------------------------
    # Read models
    # ------------------------------------------------------------------
    def get_mastery_status(self, session_id: str, node_id: str | None = None) -> dict:
        session = self.require_session(session_id)
        learner_id = session["learner_id"]
        if node_id:
            state = self._load_state(learner_id, node_id)
            # misconception_ids comes from the authoritative table, so it is
            # reported even before a knowledge-state row exists.
            active = self._active_misconception_ids(learner_id, node_id)
            if state is None:
                return self.ok(
                    session_id=session_id, node_id=node_id,
                    learner_state=None, misconception_ids=active,
                )
            return self.ok(
                session_id=session_id, node_id=node_id, learner_state=state,
                misconception_ids=active,
            )
        rows = self.rows(
            "SELECT * FROM learner_knowledge_state WHERE learner_id = ? ORDER BY node_id",
            (learner_id,),
        )
        return self.ok(session_id=session_id, learner_id=learner_id, count=len(rows), states=rows)

    def get_assessment_history(self, session_id: str, node_id: str | None = None, limit: int = 50) -> dict:
        self.require_session(session_id)
        if node_id:
            rows = self.rows(
                "SELECT ar.*, la.node_id, la.hint_level, la.attempt_index, la.created_at AS attempt_at "
                "FROM assessment_results ar JOIN learning_attempts la ON la.attempt_id = ar.attempt_id "
                "WHERE la.session_id = ? AND la.node_id = ? ORDER BY ar.created_at DESC LIMIT ?",
                (session_id, node_id, limit),
            )
        else:
            rows = self.rows(
                "SELECT ar.*, la.node_id, la.hint_level, la.attempt_index, la.created_at AS attempt_at "
                "FROM assessment_results ar JOIN learning_attempts la ON la.attempt_id = ar.attempt_id "
                "WHERE la.session_id = ? ORDER BY ar.created_at DESC LIMIT ?",
                (session_id, limit),
            )
        return self.ok(session_id=session_id, count=len(rows), results=rows)

    # ------------------------------------------------------------------
    # Transfer + reflection (22.8)
    # ------------------------------------------------------------------
    def record_transfer_result(
        self,
        learner_id: str,
        node_id: str,
        transfer_type: str,
        score: float,
        *,
        task_context: str | None = None,
        result: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        learner_id = self.require_text(learner_id, "learner_id")
        node_id = self.require_text(node_id, "node_id")
        if transfer_type not in {"near", "variation", "far", "integrated"}:
            raise ToolError(
                "invalid_transfer_type",
                "transfer_type must be one of near | variation | far | integrated",
            )
        self.require_node(node_id)
        ts = now_ts()

        self.events.emit(
            "transfer_started", session_id=session_id, learner_id=learner_id, node_id=node_id,
            payload={"transfer_type": transfer_type, "score": float(score),
                     "task_context": task_context},
            request_id=request_id,
        )

        with self.db.transaction():
            self.db.execute(
                "INSERT INTO transfer_results "
                "(learner_id, node_id, transfer_type, score, task_context, result, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (learner_id, node_id, transfer_type, float(score), task_context, result, ts),
            )

        stage_after = self.reevaluate_evidence_stage(learner_id, node_id, session_id)
        self.events.emit(
            "transfer_completed", session_id=session_id, learner_id=learner_id, node_id=node_id,
            payload={"transfer_type": transfer_type, "score": float(score), "stage_after": stage_after},
            request_id=request_id,
        )
        return self.ok(
            learner_id=learner_id, node_id=node_id, transfer_type=transfer_type,
            score=float(score), evidence_stage=stage_after,
        )

    def record_reflection(
        self,
        session_id: str,
        reflection: Any,
        *,
        node_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        session = self.require_session(session_id)
        artifact_id = new_id("art")
        ts = now_ts()
        content = reflection if isinstance(reflection, str) else self._dumps(reflection)
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO artifacts "
                "(artifact_id, learner_id, session_id, artifact_type, path_or_uri, content, created_at) "
                "VALUES (?,?,?,'reflection',NULL,?,?)",
                (artifact_id, session["learner_id"], session_id, content, ts),
            )
        self.events.emit(
            "reflection_recorded", session_id=session_id, learner_id=session["learner_id"],
            node_id=node_id, payload={"artifact_id": artifact_id}, request_id=request_id,
        )
        return self.ok(artifact_id=artifact_id)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _check_assessor_type(self, assessor_type: str) -> None:
        if assessor_type not in ASSESSOR_TYPES:
            raise ToolError(
                "invalid_assessor_type",
                f"assessor_type must be one of {ASSESSOR_TYPES}, got {assessor_type!r}",
            )

    @staticmethod
    def _dumps(value: Any) -> str:
        import json

        return json.dumps(value, ensure_ascii=False, default=str)

    def _normalise_scores(self, scores: Mapping[str, Any]) -> dict:
        out: dict[str, float | None] = {}
        for key in (*SCORE_DIMENSIONS, "transfer", "hint_dependency", "confidence"):
            value = scores.get(key)
            if value is None:
                out[key] = None
                continue
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ToolError("invalid_score", f"'{key}' must be numeric, got {value!r}") from exc
            if not 0.0 <= number <= 1.0:
                raise ToolError("invalid_score", f"'{key}' must be within [0, 1], got {number}")
            out[key] = number
        return out

    def _overall_score(self, scores: Mapping[str, float | None]) -> float | None:
        """Aggregate via the configured ScoreAggregator (section 35.2 seam).

        The default implementation is the weighted mean of section 10.3-1,
        which renormalises over whichever dimensions were actually judged and
        excludes ``transfer`` / ``hint_dependency`` from the aggregate.
        """
        return self.aggregator.aggregate(scores)

    def _snapshot_stage(self, attempt: Mapping[str, Any], scores: Mapping[str, Any], overall: float | None) -> str:
        """Immutable per-attempt stage recorded on ``assessment_results``."""
        hint_level = int(attempt.get("hint_level") or 0)
        if overall is None:
            return "estimated"
        if overall >= float(self.conf("mastery_threshold", 0.80)) and hint_level <= _INDEPENDENT_HINT_MAX:
            return "demonstrated"
        return "practiced"

    def _load_state(self, learner_id: str, node_id: str) -> dict | None:
        row = self.db.query_one(
            "SELECT * FROM learner_knowledge_state WHERE learner_id = ? AND node_id = ?",
            (learner_id, node_id),
        )
        return dict(row) if row else None

    def _active_misconception_ids(self, learner_id: str, node_id: str) -> list[int]:
        rows = self.db.query(
            "SELECT id FROM misconceptions WHERE learner_id = ? AND node_id = ? AND status = 'active'",
            (learner_id, node_id),
        )
        return [int(r["id"]) for r in rows]

    def _refresh_misconception_cache(self, learner_id: str, node_id: str) -> None:
        """Refresh the read-only cache on ``learner_knowledge_state`` (23.6)."""
        ids = self._active_misconception_ids(learner_id, node_id)
        self.db.execute(
            "UPDATE learner_knowledge_state SET misconception_state = ?, updated_at = ? "
            "WHERE learner_id = ? AND node_id = ?",
            (self._dumps(ids) if ids else None, now_ts(), learner_id, node_id),
        )

    def _update_learner_state(
        self,
        *,
        learner_id: str,
        node_id: str,
        session_id: str,
        previous: Mapping[str, Any] | None,
        scores: Mapping[str, Any],
        overall: float | None,
        assessor_confidence: float,
        hint_level: int,
        attempt_created_at: int,
    ) -> dict:
        estimator = self._estimator()
        prev = dict(previous) if previous else {}

        prior_mastery = prev.get("mastery_probability")
        last_assessed = prev.get("last_assessed_at")
        elapsed_days = 0.0
        if last_assessed:
            elapsed_days = max(0.0, (attempt_created_at - int(last_assessed)) / 86400.0)

        observation = overall if overall is not None else scores.get("correctness")
        if observation is None:
            mastery = prior_mastery if prior_mastery is not None else estimator.initial()
        else:
            mastery = estimator.confidence_weighted(
                prior_mastery,
                score=float(observation),
                assessor_confidence=float(assessor_confidence),
                elapsed_days=elapsed_days,
            )

        # Running hint dependency: smoothed so one heavily-hinted attempt does
        # not wipe out an otherwise independent history.
        observed_hint = min(1.0, hint_level / max(1, int(self.conf("max_hint_level", 3))))
        prev_hint = prev.get("hint_dependency")
        hint_dependency = (
            observed_hint
            if prev_hint is None
            else round((1 - _HINT_DEPENDENCY_ALPHA) * float(prev_hint)
                       + _HINT_DEPENDENCY_ALPHA * observed_hint, 6)
        )

        evidence = self._evidence_input(learner_id, node_id, session_id, mastery, hint_dependency)
        evaluation = evaluate_stage(prev.get("evidence_stage", "estimated"), evidence, self.cfg)

        ts = now_ts()
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO learner_knowledge_state "
                "(learner_id, node_id, mastery_probability, reasoning_quality, application_level, "
                " transfer_level, hint_dependency, confidence, evidence_stage, last_assessed_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(learner_id, node_id) DO UPDATE SET "
                " mastery_probability = excluded.mastery_probability, "
                " reasoning_quality   = COALESCE(excluded.reasoning_quality, learner_knowledge_state.reasoning_quality), "
                " application_level   = COALESCE(excluded.application_level, learner_knowledge_state.application_level), "
                " transfer_level      = COALESCE(excluded.transfer_level, learner_knowledge_state.transfer_level), "
                " hint_dependency     = excluded.hint_dependency, "
                " confidence          = COALESCE(excluded.confidence, learner_knowledge_state.confidence), "
                " evidence_stage      = excluded.evidence_stage, "
                " last_assessed_at    = excluded.last_assessed_at, "
                " updated_at          = excluded.updated_at",
                (
                    learner_id, node_id, mastery,
                    scores.get("reasoning_quality"), scores.get("application"),
                    scores.get("transfer"), hint_dependency, scores.get("confidence"),
                    evaluation.stage, ts, ts,
                ),
            )
        self._refresh_misconception_cache(learner_id, node_id)

        state = self._load_state(learner_id, node_id) or {}
        state["_stage_evaluation"] = evaluation.as_dict()

        # Keep the review queue in step with the evidence stage.
        if stage_index(evaluation.stage) >= stage_index("demonstrated"):
            try:
                self.schedule_review(  # type: ignore[attr-defined]
                    learner_id=learner_id, node_id=node_id, session_id=session_id
                )
            except Exception:  # pragma: no cover - review sync must not break assessment
                pass
        return state

    def _estimator(self) -> Any:
        """Return the configured mastery estimator (section 35.1 seam)."""
        return self.estimator

    def _evidence_input(
        self,
        learner_id: str,
        node_id: str,
        session_id: str,
        mastery: float,
        hint_dependency: float,
    ) -> EvidenceInput:
        attempts = self.rows(
            "SELECT la.hint_level, ar.overall_score FROM learning_attempts la "
            "LEFT JOIN assessment_results ar ON ar.attempt_id = la.attempt_id "
            "WHERE la.session_id = ? AND la.node_id = ?",
            (session_id, node_id),
        )
        valid_attempts = 0
        unassisted = 0
        for attempt in attempts:
            score = attempt.get("overall_score")
            hint = int(attempt.get("hint_level") or 0)
            if score is None or hint_dependency >= 0.9:
                continue
            valid_attempts += 1
            if float(score) >= _SUCCESS_SCORE and hint <= _INDEPENDENT_HINT_MAX:
                unassisted += 1

        probes = self.rows(
            "SELECT score FROM transfer_results WHERE learner_id = ? AND node_id = ?",
            (learner_id, node_id),
        )
        transfer_scores = [float(p["score"]) for p in probes if p["score"] is not None]
        best_transfer = max(transfer_scores) if transfer_scores else None
        latest_failed = bool(transfer_scores) and transfer_scores[-1] < float(
            self.conf("transfer_pass_score", 0.70)
        )

        review = self.db.query_one(
            "SELECT * FROM review_items WHERE learner_id = ? AND node_id = ? "
            "ORDER BY updated_at DESC LIMIT 1",
            (learner_id, node_id),
        )
        retention_confirmed = False
        retention_lapsed = False
        if review:
            review = dict(review)
            retention_confirmed = int(review.get("review_count") or 0) >= 2
            next_at = review.get("next_review_at")
            if next_at and not retention_confirmed:
                overdue_days = (now_ts() - int(next_at)) / 86400.0
                retention_lapsed = overdue_days > float(self.conf("retention_interval_days", 1.0)) * 7

        last_assessed = self.db.scalar(
            "SELECT last_assessed_at FROM learner_knowledge_state "
            "WHERE learner_id = ? AND node_id = ?",
            (learner_id, node_id),
        )
        days_since = (now_ts() - int(last_assessed)) / 86400.0 if last_assessed else None

        return EvidenceInput(
            mastery_probability=mastery,
            hint_dependency=hint_dependency,
            valid_attempts=valid_attempts,
            unassisted_successes=unassisted,
            transfer_probes=len(transfer_scores),
            transfer_score=best_transfer,
            retention_confirmed=retention_confirmed,
            days_since_last_assessment=days_since,
            retention_lapsed=retention_lapsed,
            latest_transfer_failed=latest_failed,
        )

    def reevaluate_evidence_stage(
        self, learner_id: str, node_id: str, session_id: str | None = None
    ) -> str:
        state = self._load_state(learner_id, node_id)
        if state is None:
            return "estimated"
        evidence = self._evidence_input(
            learner_id, node_id, session_id or "",
            float(state.get("mastery_probability") or 0.0),
            float(state.get("hint_dependency") or 0.0),
        )
        evaluation = evaluate_stage(state.get("evidence_stage", "estimated"), evidence, self.cfg)
        self.db.execute(
            "UPDATE learner_knowledge_state SET evidence_stage = ?, updated_at = ? "
            "WHERE learner_id = ? AND node_id = ?",
            (evaluation.stage, now_ts(), learner_id, node_id),
        )
        return evaluation.stage
