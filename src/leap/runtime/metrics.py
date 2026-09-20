"""Learning-outcome metrics (LEAP-Framework-V2 section 26).

Section 26 is explicit that the system's evaluation goal is **not** "the API
responds" or "the page opens", but whether the teaching strategy actually
improved learning. The nine core indicators are::

    Immediate Performance
    Delayed Retention
    Transfer Performance
    Time to Target Evidence
    Attempts to Target Evidence
    Hint Dependency
    Misconception Resolution
    Confidence Calibration
    Learning Gain

Everything here is derived from evidence the runtime already stores, so the
numbers are reproducible and auditable rather than self-reported.

Ordering note: timestamps are Unix **seconds** project-wide, so several events
can share a ``created_at``. Any "before/after" split therefore uses event
``rowid`` (append order), never the timestamp alone.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

__all__ = ["LearningMetrics", "diagnostic_split", "TARGET_STAGE"]

#: The evidence stage used as the "target" for the time/attempts metrics.
TARGET_STAGE = "demonstrated"

_STAGE_ORDER = ("estimated", "practiced", "demonstrated", "retained", "transferred")


def _rank(stage: str | None) -> int:
    try:
        return _STAGE_ORDER.index(stage or "estimated")
    except ValueError:
        return 0


def diagnostic_split(db: Any, session_id: str) -> tuple[list[dict], list[dict], Any]:
    """Split assessment results into pre-diagnostic and post-diagnostic.

    Returns ``(baseline_results, post_results, diagnostic_completed_at)``.
    The split point is the position of the first ``diagnostic_completed`` event
    in the append-ordered event log, mapped onto the attempts recorded before
    it. Using rowid rather than ``created_at`` matters because a whole teaching
    turn can land inside the same second.
    """
    marker = db.query_one(
        "SELECT rowid, created_at FROM event_log "
        "WHERE session_id = ? AND event_type = 'diagnostic_completed' ORDER BY rowid LIMIT 1",
        (session_id,),
    )
    results = [
        dict(r)
        for r in db.query(
            "SELECT ar.*, la.node_id, la.hint_level FROM assessment_results ar "
            "JOIN learning_attempts la ON la.attempt_id = ar.attempt_id "
            "WHERE la.session_id = ? ORDER BY ar.rowid",
            (session_id,),
        )
    ]
    if marker is None:
        return [], results, None

    baseline_count = int(
        db.scalar(
            "SELECT COUNT(*) FROM event_log "
            "WHERE session_id = ? AND event_type = 'attempt_submitted' AND rowid < ?",
            (session_id, int(marker["rowid"])),
            0,
        )
    )
    return results[:baseline_count], results[baseline_count:], marker["created_at"]


def _mean(values: Iterable[float]) -> float | None:
    items = [float(v) for v in values]
    if not items:
        return None
    return round(sum(items) / len(items), 4)


class LearningMetrics:
    """Computes the section 26.1 indicator set for a session."""

    def __init__(self, db: Any, cfg: Any = None) -> None:
        self._db = db
        self._cfg = cfg

    def _get(self, key: str, default: Any = None) -> Any:
        return self._cfg.get(key, default) if hasattr(self._cfg, "get") else default

    # ------------------------------------------------------------------
    def compute(self, session_id: str, learner_id: str | None = None) -> dict:
        session = self._db.query_one(
            "SELECT * FROM learning_sessions WHERE session_id = ?", (session_id,)
        )
        if session is None:
            raise KeyError(f"unknown session: {session_id}")
        session = dict(session)
        learner_id = learner_id or session["learner_id"]

        baseline, post, diagnostic_at = diagnostic_split(self._db, session_id)
        all_results = baseline + post

        return {
            "session_id": session_id,
            "learner_id": learner_id,
            "target_stage": TARGET_STAGE,
            "immediate_performance": self.immediate_performance(post or all_results),
            "delayed_retention": self.delayed_retention(learner_id),
            "transfer_performance": self.transfer_performance(learner_id),
            "time_to_target_evidence": self.time_to_target_evidence(session_id),
            "attempts_to_target_evidence": self.attempts_to_target_evidence(session_id),
            "hint_dependency": self.hint_dependency(all_results),
            "misconception_resolution": self.misconception_resolution(learner_id),
            "confidence_calibration": self.confidence_calibration(all_results),
            "learning_gain": self.learning_gain(baseline, post),
            "diagnostic_completed_at": diagnostic_at,
            "note": (
                "All values are derived from recorded evidence. mastery-based figures are model "
                "estimates, not measured facts."
            ),
        }

    # ------------------------------------------------------------------
    # 26.2 individual definitions
    # ------------------------------------------------------------------
    def immediate_performance(self, results: list[dict]) -> dict:
        """Performance on the tasks just attempted."""
        scores = [r["overall_score"] for r in results if r.get("overall_score") is not None]
        recent = scores[-3:] if scores else []
        return {
            "mean_overall_score": _mean(scores),
            "recent_mean_overall_score": _mean(recent),
            "evidence_points": len(scores),
        }

    def delayed_retention(self, learner_id: str) -> dict:
        """Retrieval performance after a spacing interval (section 13)."""
        rows = [
            dict(r)
            for r in self._db.query(
                "SELECT * FROM review_items WHERE learner_id = ? AND review_count > 0 "
                "ORDER BY last_review_at",
                (learner_id,),
            )
        ]
        interval_days = float(self._get("retention_interval_days", 1.0))
        spaced = []
        for row in rows:
            last, first_seen = row.get("last_review_at"), row.get("created_at")
            if last and first_seen and (int(last) - int(first_seen)) / 86400.0 >= interval_days:
                spaced.append(row)
        ratings = [float(r["last_rating"]) for r in spaced if r.get("last_rating") is not None]
        return {
            "review_items": len(rows),
            "spaced_review_items": len(spaced),
            "mean_rating": _mean(ratings),
            "rating_scale": "1=Again 2=Hard 3=Good 4=Easy",
            "spacing_threshold_days": interval_days,
            "note": "null until at least one review has happened after the configured interval",
        }

    def transfer_performance(self, learner_id: str) -> dict:
        rows = [
            dict(r)
            for r in self._db.query(
                "SELECT transfer_type, score FROM transfer_results WHERE learner_id = ?",
                (learner_id,),
            )
        ]
        scores = [r["score"] for r in rows if r.get("score") is not None]
        by_type: dict[str, list[float]] = {}
        for row in rows:
            if row.get("score") is not None:
                by_type.setdefault(str(row.get("transfer_type")), []).append(float(row["score"]))
        return {
            "attempts": len(rows),
            "mean_score": _mean(scores),
            "by_type": {k: _mean(v) for k, v in sorted(by_type.items())},
            "pass_score": float(self._get("transfer_pass_score", 0.70)),
        }

    def time_to_target_evidence(self, session_id: str) -> dict:
        """Seconds from a node's first attempt to reaching the target stage."""
        per_node = self._time_and_attempts(session_id)
        seconds = [v["seconds"] for v in per_node.values() if v["seconds"] is not None]
        return {
            "target_stage": TARGET_STAGE,
            "nodes_reached": len(seconds),
            "nodes_measured": len(per_node),
            "mean_seconds": _mean(seconds),
            "mean_hours": round(_mean(seconds) / 3600.0, 4) if seconds else None,
            "per_node": per_node,
        }

    def attempts_to_target_evidence(self, session_id: str) -> dict:
        """Effective attempts needed to reach the target stage."""
        per_node = self._time_and_attempts(session_id)
        counts = [v["attempts"] for v in per_node.values() if v["attempts"] is not None]
        return {
            "target_stage": TARGET_STAGE,
            "nodes_reached": len(counts),
            "mean_attempts": _mean(counts),
            "per_node": {k: v["attempts"] for k, v in per_node.items()},
        }

    def hint_dependency(self, results: list[dict]) -> dict:
        values = [r["hint_dependency"] for r in results if r.get("hint_dependency") is not None]
        mean = _mean(values)
        threshold = float(self._get("hint_dependency_high", 0.70))
        return {
            "mean": mean,
            "samples": len(values),
            "high_threshold": threshold,
            "above_threshold": (mean is not None and mean > threshold),
        }

    def misconception_resolution(self, learner_id: str) -> dict:
        rows = [
            dict(r)
            for r in self._db.query(
                "SELECT status, resolved_at, last_seen_at FROM misconceptions WHERE learner_id = ?",
                (learner_id,),
            )
        ]
        resolved = [r for r in rows if r.get("status") == "resolved"]
        active = [r for r in rows if r.get("status") == "active"]
        total = len(rows)
        return {
            "total": total,
            "active": len(active),
            "resolved": len(resolved),
            "resolution_rate": round(len(resolved) / total, 4) if total else None,
        }

    def confidence_calibration(self, results: list[dict]) -> dict:
        pairs = [
            (float(r["confidence"]), float(r["overall_score"]))
            for r in results
            if r.get("confidence") is not None and r.get("overall_score") is not None
        ]
        if not pairs:
            return {"samples": 0, "mean_absolute_error": None}
        errors = [abs(c - a) for c, a in pairs]
        return {
            "samples": len(pairs),
            "mean_absolute_error": _mean(errors),
            "note": (
                "engineering indicator only; not a judgement about the learner "
                "(section 14.2)"
            ),
        }

    def learning_gain(self, baseline: list[dict], post: list[dict]) -> dict:
        base = [r["overall_score"] for r in baseline if r.get("overall_score") is not None]
        after = [r["overall_score"] for r in post if r.get("overall_score") is not None]
        base_mean, post_mean = _mean(base), _mean(after)
        gain = round(post_mean - base_mean, 4) if base_mean is not None and post_mean is not None else None
        return {
            "baseline_mean_score": base_mean,
            "post_mean_score": post_mean,
            "absolute_gain": gain,
            "baseline_points": len(base),
            "post_points": len(after),
        }

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _time_and_attempts(self, session_id: str) -> dict[str, dict]:
        """Per node: when it reached the target stage, and how many attempts it took.

        ``assessment_committed`` events carry ``stage_after``, so the first such
        event at (or above) the target stage marks the moment the node got
        there. Attempts are counted from the append-ordered event log.
        """
        events = [
            dict(r)
            for r in self._db.query(
                "SELECT rowid, event_type, node_id, payload, created_at FROM event_log "
                "WHERE session_id = ? ORDER BY rowid",
                (session_id,),
            )
        ]

        first_attempt: dict[str, int] = {}
        attempts: dict[str, int] = {}
        reached: dict[str, int] = {}

        import json as _json

        for event in events:
            node_id = event.get("node_id")
            if not node_id:
                continue
            if event["event_type"] == "attempt_submitted":
                first_attempt.setdefault(node_id, int(event["created_at"]))
                attempts[node_id] = attempts.get(node_id, 0) + 1
            elif event["event_type"] == "assessment_committed" and node_id not in reached:
                try:
                    payload = _json.loads(event.get("payload") or "{}")
                except (TypeError, ValueError):
                    payload = {}
                if _rank(payload.get("stage_after")) >= _rank(TARGET_STAGE):
                    reached[node_id] = int(event["created_at"])

        out: dict[str, dict] = {}
        for node_id in sorted(set(first_attempt) | set(reached)):
            start = first_attempt.get(node_id)
            end = reached.get(node_id)
            out[node_id] = {
                "seconds": (end - start) if (start is not None and end is not None) else None,
                "attempts": attempts.get(node_id) if node_id in reached else None,
                "total_attempts": attempts.get(node_id, 0),
            }
        return out
