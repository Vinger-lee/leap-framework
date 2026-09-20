"""Shared plumbing for the LEAP tool implementations.

The tools are plain Python methods on mixin classes. ``leap.server`` is a thin
MCP wrapper around them, which keeps every tool unit-testable without a
transport in the loop.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from leap.config import Config, load_config
from leap.runtime.events import EventLog
from leap.runtime.state_guard import StateGuard
from leap.storage import new_id, new_request_id, now_ts

__all__ = ["ToolError", "ToolContext", "LeapToolMixin", "json_dumps"]


class ToolError(Exception):
    """Structured, client-safe error returned by a LEAP tool.

    The runtime must never turn a failure into a silent state update
    (section 29.1), so every tool either returns a value or raises this.
    """

    def __init__(self, code: str, message: str, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def as_dict(self) -> dict:
        return {"ok": False, "error": {"code": self.code, "message": self.message, "details": self.details}}


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


@dataclass
class ToolContext:
    """Everything a tool needs, injected once.

    The swappable components are built through
    :mod:`leap.runtime.plugins` so that ``config/default.yaml`` decides which
    implementation is in use (section 35). Tools depend on the protocols in
    :mod:`leap.runtime.contracts`, never on a concrete class.
    """

    db: Any
    cfg: Config
    events: EventLog
    guard: StateGuard
    policy: Any
    scheduler: Any
    estimator: Any
    aggregator: Any
    artifacts: Any
    translator: Any

    @classmethod
    def build(
        cls,
        db: Any = None,
        cfg: Config | None = None,
        *,
        database_path: str = ":memory:",
    ) -> "ToolContext":
        from leap.i18n import translator_for
        from leap.runtime.plugins import (
            KIND_ARTIFACT_STORE,
            KIND_MASTERY_ESTIMATOR,
            KIND_POLICY_ENGINE,
            KIND_REVIEW_SCHEDULER,
            KIND_SCORE_AGGREGATOR,
            KIND_STORAGE_BACKEND,
            create_from_config,
        )

        cfg = cfg or load_config()
        if db is None:
            db = create_from_config(
                KIND_STORAGE_BACKEND, cfg, default="sqlite", path=database_path
            )

        events = EventLog(db)
        translator = translator_for(cfg)
        return cls(
            db=db,
            cfg=cfg,
            events=events,
            guard=StateGuard(db, cfg, events, translator=translator),
            policy=create_from_config(
                KIND_POLICY_ENGINE, cfg, db, default="rule_based", events=events
            ),
            scheduler=create_from_config(
                KIND_REVIEW_SCHEDULER, cfg, default="py-fsrs"
            ),
            estimator=create_from_config(
                KIND_MASTERY_ESTIMATOR, cfg, default="simplified_bkt"
            ),
            aggregator=create_from_config(
                KIND_SCORE_AGGREGATOR, cfg, default="weighted"
            ),
            artifacts=create_from_config(
                KIND_ARTIFACT_STORE, cfg, db, default="local"
            ),
            translator=translator,
        )


class LeapToolMixin:
    """Base class providing context access and common helpers."""

    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx

    # -- shorthand ---------------------------------------------------------
    @property
    def db(self) -> Any:
        return self.ctx.db

    @property
    def cfg(self) -> Config:
        return self.ctx.cfg

    @property
    def events(self) -> EventLog:
        return self.ctx.events

    @property
    def guard(self) -> StateGuard:
        return self.ctx.guard

    @property
    def policy(self) -> Any:
        return self.ctx.policy

    @property
    def scheduler(self) -> Any:
        return self.ctx.scheduler

    @property
    def estimator(self) -> Any:
        """Mastery estimator (section 35.1 seam)."""
        return self.ctx.estimator

    @property
    def aggregator(self) -> Any:
        """Score aggregator (section 35.2 seam)."""
        return self.ctx.aggregator

    @property
    def artifacts(self) -> Any:
        """Artifact store (section 35.6 seam)."""
        return self.ctx.artifacts

    @property
    def i18n(self) -> Any:
        """Translator for learner-visible text."""
        return self.ctx.translator

    def t(self, key: str, **kwargs: Any) -> str:
        """Shorthand for a translated message."""
        return self.ctx.translator.t(key, **kwargs)

    def conf(self, key: str, default: Any = None) -> Any:
        return self.cfg.get(key, default)

    # -- validation helpers ------------------------------------------------
    def require_session(self, session_id: str) -> dict:
        row = self.db.query_one(
            "SELECT * FROM learning_sessions WHERE session_id = ?", (session_id,)
        )
        if row is None:
            raise ToolError("unknown_session", f"session not found: {session_id}")
        return dict(row)

    def require_node(self, node_id: str) -> dict:
        row = self.db.query_one("SELECT * FROM knowledge_nodes WHERE node_id = ?", (node_id,))
        if row is None:
            raise ToolError("unknown_node", f"knowledge node not found: {node_id}")
        return dict(row)

    def require_learner(self, learner_id: str) -> dict:
        row = self.db.query_one("SELECT * FROM learners WHERE learner_id = ?", (learner_id,))
        if row is None:
            raise ToolError("unknown_learner", f"learner not found: {learner_id}")
        return dict(row)

    def ensure_learner(self, learner_id: str, name: str | None = None) -> dict:
        """Create the learner row on first sight (P0 is single-learner)."""
        row = self.db.query_one("SELECT * FROM learners WHERE learner_id = ?", (learner_id,))
        ts = now_ts()
        if row is None:
            self.db.execute(
                "INSERT INTO learners (learner_id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (learner_id, name or learner_id, ts, ts),
            )
            return {"learner_id": learner_id, "name": name or learner_id, "created_at": ts, "updated_at": ts}
        return dict(row)

    @staticmethod
    def require_text(value: Any, field: str) -> str:
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ToolError("invalid_argument", f"'{field}' is required and must be non-empty")
        return value if isinstance(value, str) else str(value)

    # -- idempotency -------------------------------------------------------
    def idempotent(
        self,
        key: str | None,
        tool_name: str,
        fn: Callable[[], dict],
        session_id: str | None = None,
    ) -> dict:
        """Replay the stored response when the same request arrives twice."""
        if not key:
            return fn()
        cached = self.db.lookup_request(key)
        if cached is not None:
            try:
                payload = json.loads(cached)
            except ValueError:
                payload = {"ok": True, "replayed": True, "raw": cached}
            payload["replayed"] = True
            return payload
        result = fn()
        try:
            self.db.remember_request(key, tool_name, session_id, json_dumps(result))
        except sqlite3.Error:
            # Idempotency bookkeeping must never break the business operation.
            pass
        return result

    # -- response envelope -------------------------------------------------
    @staticmethod
    def ok(**payload: Any) -> dict:
        return {"ok": True, **payload}

    def new_request_id(self) -> str:
        return new_request_id()

    def now(self) -> int:
        return now_ts()

    def next_id(self, prefix: str) -> str:
        return new_id(prefix)

    def as_list(self, value: Any) -> list:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    def decode_json_columns(self, row: Mapping[str, Any], *columns: str) -> dict:
        data = dict(row)
        for column in columns:
            raw = data.get(column)
            if isinstance(raw, str) and raw:
                try:
                    data[column] = json.loads(raw)
                except ValueError:
                    pass
        return data

    def rows(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        return [dict(r) for r in self.db.query(sql, params)]
