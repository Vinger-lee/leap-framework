"""Retention tools (section 22.7) built on the FSRS scheduler (section 13).

``review_items`` is the single source of truth for review state.
``learner_knowledge_state.next_review_at`` is only a cache that the runtime
refreshes here - business code must never write it directly (section 23.6).
"""

from __future__ import annotations

from typing import Any

from leap.storage import new_id, now_ts
from leap.tools.base import LeapToolMixin, ToolError

__all__ = ["RetentionTools"]


class RetentionTools(LeapToolMixin):
    """Review scheduling, submission and due-item queries."""

    # ------------------------------------------------------------------
    def get_review_state(
        self, learner_id: str, node_id: str | None = None
    ) -> dict:
        """Return review items with current retrievability and due status."""
        learner_id = self.require_text(learner_id, "learner_id")
        if node_id:
            rows = self.rows(
                "SELECT * FROM review_items WHERE learner_id = ? AND node_id = ? "
                "ORDER BY next_review_at",
                (learner_id, node_id),
            )
        else:
            rows = self.rows(
                "SELECT * FROM review_items WHERE learner_id = ? ORDER BY next_review_at",
                (learner_id,),
            )
        for row in rows:
            row["retrievability_now"] = self.scheduler.retrievability(
                stability=row.get("stability"), last_review_at=row.get("last_review_at")
            )
            row["is_due"] = self.scheduler.is_due(row.get("next_review_at"))
        return self.ok(learner_id=learner_id, count=len(rows), review_items=rows)

    def schedule_review(
        self,
        learner_id: str,
        node_id: str,
        *,
        session_id: str | None = None,
        item_ref: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Create a review item for a node if one does not exist yet."""
        learner_id = self.require_text(learner_id, "learner_id")
        node_id = self.require_text(node_id, "node_id")
        if session_id:
            self.require_node(node_id, session_id)
        else:
            self.require_node(node_id)

        existing = self.db.query_one(
            "SELECT * FROM review_items WHERE learner_id = ? AND node_id = ? LIMIT 1",
            (learner_id, node_id),
        )
        if existing:
            if item_ref:
                self.db.execute(
                    "UPDATE review_items SET item_ref = ?, updated_at = ? WHERE review_item_id = ?",
                    (item_ref, now_ts(), existing["review_item_id"]),
                )
            self._sync_review_cache(learner_id, node_id)
            return self.ok(
                review_item_id=existing["review_item_id"],
                created=False,
                review_item=dict(self.db.query_one(
                    "SELECT * FROM review_items WHERE review_item_id = ?",
                    (existing["review_item_id"],),
                )),
            )

        # A fresh card: derive the first interval from the scheduler rather than
        # hardcoding 1/3/7 days (section 13.5).
        outcome = self.scheduler.review(rating=3, review_count=0)
        review_item_id = new_id("rev")
        ts = now_ts()
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO review_items "
                "(review_item_id, learner_id, node_id, item_ref, stability, difficulty, "
                " retrievability, last_review_at, next_review_at, review_count, last_rating, "
                " scheduler_version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    review_item_id, learner_id, node_id, item_ref, outcome.stability,
                    outcome.difficulty, outcome.retrievability, None, outcome.due_at,
                    0, None, outcome.scheduler_version, ts, ts,
                ),
            )
        self._sync_review_cache(learner_id, node_id)
        self.events.emit(
            "review_scheduled", session_id=session_id, learner_id=learner_id, node_id=node_id,
            payload={"review_item_id": review_item_id, "next_review_at": outcome.due_at},
            request_id=request_id,
        )
        return self.ok(
            review_item_id=review_item_id,
            created=True,
            next_review_at=outcome.due_at,
            interval_days=outcome.interval_days,
        )

    def submit_review(
        self,
        review_item_id: str,
        rating: int,
        *,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Submit an FSRS rating (1=Again, 2=Hard, 3=Good, 4=Easy) and reschedule."""
        with self.db.transaction():
            row = self.db.query_one(
                "SELECT * FROM review_items WHERE review_item_id = ?", (review_item_id,)
            )
            if row is None:
                raise ToolError("unknown_review_item", f"review item not found: {review_item_id}")
            row = dict(row)
            node = self.require_node(row["node_id"], session_id)
            resolved_session_id = node["session_id"]
            if self.guard.strict_grounding:
                self.require_grounding(resolved_session_id)
                from leap.runtime.grounding import course_node_id

                if row["node_id"] != course_node_id(resolved_session_id):
                    raise ToolError("grounding_coverage_missing", "The review belongs to a historical node outside the current course")

            try:
                rating_int = int(rating)
            except (TypeError, ValueError) as exc:
                raise ToolError("invalid_rating", "rating must be an integer 1-4") from exc
            if not 1 <= rating_int <= 4:
                raise ToolError("invalid_rating", f"rating must be within 1..4, got {rating_int}")

            self.events.emit(
                "review_started", session_id=resolved_session_id, learner_id=row["learner_id"],
                node_id=row["node_id"],
                payload={"review_item_id": review_item_id, "rating": rating_int,
                         "review_count": int(row.get("review_count") or 0)},
                request_id=request_id,
            )

            outcome = self.scheduler.review(
                rating=rating_int,
                stability=row.get("stability"),
                difficulty=row.get("difficulty"),
                due_at=row.get("next_review_at"),
                last_review_at=row.get("last_review_at"),
                review_count=int(row.get("review_count") or 0),
            )
            ts = now_ts()
            self.db.execute(
                "UPDATE review_items SET stability=?, difficulty=?, retrievability=?, "
                " last_review_at=?, next_review_at=?, review_count=review_count+1, last_rating=?, "
                " scheduler_version=?, updated_at=? WHERE review_item_id=?",
                (
                    outcome.stability, outcome.difficulty, outcome.retrievability,
                    outcome.last_review_at, outcome.due_at, outcome.rating,
                    outcome.scheduler_version, ts, review_item_id,
                ),
            )
            self._sync_review_cache(row["learner_id"], row["node_id"])

            # A successful spaced review is retention evidence (section 11.4).
            # The owning session is resolved from the node when the caller omitted
            # it: passing an empty session made the evidence query see zero attempts
            # and demoted the node to `estimated` on a perfectly good review.
            stage_after = None
            if rating_int >= 2:
                stage_after = self.reevaluate_evidence_stage(  # type: ignore[attr-defined]
                    row["learner_id"], row["node_id"], resolved_session_id
                )

            self.events.emit(
                "review_completed", session_id=resolved_session_id, learner_id=row["learner_id"],
                node_id=row["node_id"],
                payload={"review_item_id": review_item_id, "rating": rating_int,
                         "interval_days": outcome.interval_days, "stage_after": stage_after},
                request_id=request_id,
            )
            return self.ok(
                review_item_id=review_item_id,
                rating=rating_int,
                next_review_at=outcome.due_at,
                interval_days=outcome.interval_days,
                stability=outcome.stability,
                difficulty=outcome.difficulty,
                evidence_stage=stage_after,
                session_id=resolved_session_id,
                session_inferred=session_id is None,
            )

    def get_due_reviews(
        self, learner_id: str, *, limit: int = 50, session_id: str | None = None
    ) -> dict:
        """List due review items.

        A non-empty result does not block new learning globally - blocking is a
        per-node Policy + State Guard decision.
        """
        learner_id = self.require_text(learner_id, "learner_id")
        due = self.policy.due_reviews(learner_id)
        if session_id is not None:
            session = self.require_session(session_id)
            if session["learner_id"] != learner_id:
                raise ToolError("invalid_session", "session does not belong to the learner")
            node_ids = {row["node_id"] for row in self.db.query(
                "SELECT node_id FROM knowledge_nodes WHERE session_id = ?", (session_id,)
            )}
            due = [item for item in due if item["node_id"] in node_ids]
        due = due[:limit]
        for item in due:
            item["retrievability_now"] = self.scheduler.retrievability(
                stability=item.get("stability"), last_review_at=item.get("last_review_at")
            )
        return self.ok(
            learner_id=learner_id,
            count=len(due),
            due_reviews=due,
            blocks_new_learning=False,
            note=(
                "Due reviews do not block all new learning. Blocking is decided per node by "
                "Policy + State Guard, e.g. when the current node depends on the overdue one."
            ),
        )

    def recalculate_review_schedule(
        self, learner_id: str, *, now: int | None = None
    ) -> dict:
        """Recompute retrievability for every review item of a learner."""
        learner_id = self.require_text(learner_id, "learner_id")
        rows = self.rows(
            "SELECT * FROM review_items WHERE learner_id = ?", (learner_id,)
        )
        reference = now if now is not None else now_ts()
        updated = 0
        for row in rows:
            value = self.scheduler.retrievability(
                stability=row.get("stability"),
                last_review_at=row.get("last_review_at"),
                now=reference,
            )
            if value is not None:
                self.db.execute(
                    "UPDATE review_items SET retrievability = ?, updated_at = ? "
                    "WHERE review_item_id = ?",
                    (value, reference, row["review_item_id"]),
                )
                updated += 1
        for node_id in {r["node_id"] for r in rows}:
            self._sync_review_cache(learner_id, node_id)
        return self.ok(learner_id=learner_id, reviewed_items=len(rows), updated=updated)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _sync_review_cache(self, learner_id: str, node_id: str) -> None:
        """Refresh the read-only ``next_review_at`` cache (section 23.6)."""
        next_at = self.db.scalar(
            "SELECT MIN(next_review_at) FROM review_items WHERE learner_id = ? AND node_id = ?",
            (learner_id, node_id),
        )
        self.db.execute(
            "UPDATE learner_knowledge_state SET next_review_at = ?, updated_at = ? "
            "WHERE learner_id = ? AND node_id = ?",
            (next_at, now_ts(), learner_id, node_id),
        )
