"""Event log (LEAP-Framework-V2 section 18).

The event log is the append-only audit trail that makes every state change
replayable. It is deliberately separate from business state: business tables
hold *current* truth, the event log holds *how we got there*.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from leap.storage import Database, new_id, now_ts

__all__ = ["EVENT_TYPES", "EventLog"]

# Event vocabulary from section 18.1
EVENT_TYPES: frozenset[str] = frozenset(
    {
        "session_created",
        "goal_created",
        "diagnostic_started",
        "diagnostic_completed",
        "node_started",
        "attempt_submitted",
        "assessment_committed",
        "misconception_detected",
        "policy_evaluated",
        "policy_committed",
        "action_executed",
        "review_due",
        "review_started",
        "review_completed",
        "transfer_started",
        "transfer_completed",
        "reflection_recorded",
        "unit_advanced",
        "unit_rollback",
        "artifact_saved",
        "session_completed",
        "learning_configuration_changed",
        # runtime-level events not listed in 18.1 but required by the guard rails
        "state_guard_rejected",
        "domain_grounding_started",
        "domain_grounding_completed",
        "knowledge_dag_saved",
        "knowledge_dag_validated",
        "schema_initialized",
    }
)


class EventLog:
    """Append-only writer/reader for the ``event_log`` table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    # -- write -------------------------------------------------------------
    def emit(
        self,
        event_type: str,
        *,
        session_id: str | None = None,
        learner_id: str | None = None,
        node_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> str:
        """Append one event and return its id.

        Unknown event types are accepted (the vocabulary is a convention, not
        a hard constraint) but should be avoided so that the log stays
        analysable.
        """
        event_id = new_id("evt")
        self._db.execute(
            "INSERT INTO event_log "
            "(event_id, event_type, session_id, learner_id, node_id, payload, request_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                event_type,
                session_id,
                learner_id,
                node_id,
                json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
                request_id,
                now_ts(),
            ),
        )
        return event_id

    def emit_many(self, events: Iterable[tuple[str, Mapping[str, Any]]], **common: Any) -> list[str]:
        """Emit several ``(event_type, payload)`` pairs sharing common fields."""
        return [self.emit(event_type, payload=payload, **common) for event_type, payload in events]

    # -- read --------------------------------------------------------------
    def recent(self, session_id: str, limit: int = 50) -> list[dict]:
        rows = self._db.query(
            "SELECT * FROM event_log WHERE session_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (session_id, limit),
        )
        return [self._decode(r) for r in rows]

    def by_type(self, event_type: str, session_id: str | None = None, limit: int = 100) -> list[dict]:
        if session_id is None:
            rows = self._db.query(
                "SELECT * FROM event_log WHERE event_type = ? ORDER BY created_at DESC LIMIT ?",
                (event_type, limit),
            )
        else:
            rows = self._db.query(
                "SELECT * FROM event_log WHERE event_type = ? AND session_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (event_type, session_id, limit),
            )
        return [self._decode(r) for r in rows]

    def count(self, session_id: str, event_type: str | None = None) -> int:
        if event_type is None:
            return int(
                self._db.scalar(
                    "SELECT COUNT(*) FROM event_log WHERE session_id = ?", (session_id,), 0
                )
            )
        return int(
            self._db.scalar(
                "SELECT COUNT(*) FROM event_log WHERE session_id = ? AND event_type = ?",
                (session_id, event_type),
                0,
            )
        )

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _decode(row: Any) -> dict:
        data = dict(row)
        raw = data.get("payload")
        if raw:
            try:
                data["payload"] = json.loads(raw)
            except (TypeError, ValueError):
                pass
        return data
