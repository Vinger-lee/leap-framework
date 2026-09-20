"""Artifact storage backends (section 35.6).

P0 keeps artefacts in the local SQLite ``artifacts`` table. The
:class:`~leap.runtime.contracts.ArtifactStore` protocol is what lets a
deployment swap in object storage or a knowledge base without touching the
tool layer.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from leap.storage.database import Database, now_ts

__all__ = ["LocalArtifactStore"]


class LocalArtifactStore:
    """SQLite-backed artefact store (the P0 default)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def save(
        self,
        *,
        artifact_id: str,
        learner_id: str | None,
        session_id: str | None,
        artifact_type: str,
        path_or_uri: str | None = None,
        content: str | None = None,
        metadata: Any = None,
        version: str = "1",
    ) -> str:
        import json

        self._db.execute(
            "INSERT INTO artifacts "
            "(artifact_id, learner_id, session_id, artifact_type, path_or_uri, content, "
            " metadata, version, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                artifact_id, learner_id, session_id, artifact_type, path_or_uri, content,
                json.dumps(metadata, ensure_ascii=False, default=str) if metadata is not None else None,
                version, now_ts(),
            ),
        )
        return artifact_id

    def load(self, artifact_id: str) -> Mapping[str, Any] | None:
        row = self._db.query_one("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,))
        return dict(row) if row else None

    def list_for_session(
        self, session_id: str, artifact_type: str | None = None
    ) -> Iterable[Mapping[str, Any]]:
        if artifact_type:
            rows = self._db.query(
                "SELECT artifact_id, artifact_type, path_or_uri, version, created_at "
                "FROM artifacts WHERE session_id = ? AND artifact_type = ? ORDER BY created_at DESC",
                (session_id, artifact_type),
            )
        else:
            rows = self._db.query(
                "SELECT artifact_id, artifact_type, path_or_uri, version, created_at "
                "FROM artifacts WHERE session_id = ? ORDER BY created_at DESC",
                (session_id,),
            )
        return [dict(r) for r in rows]
