"""Shared prerequisite evidence lookup for guards and pedagogical policy."""

from __future__ import annotations

from leap.runtime.evidence import stage_index
from leap.storage import Database


def unmet_prerequisites(db: Database, learner_id: str, node_id: str) -> list[str]:
    """Read prerequisite stages in one query, preserving edge insertion order."""
    rows = db.query(
        "SELECT edge.pre_node_id, state.evidence_stage FROM knowledge_edges AS edge "
        "LEFT JOIN learner_knowledge_state AS state "
        "ON state.node_id = edge.pre_node_id AND state.learner_id = ? "
        "WHERE edge.post_node_id = ? AND edge.relation_type = 'prerequisite' "
        "ORDER BY edge.rowid",
        (learner_id, node_id),
    )
    return [
        row["pre_node_id"] for row in rows
        if stage_index(row["evidence_stage"] or "estimated") < stage_index("demonstrated")
    ]
