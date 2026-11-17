"""Shared plumbing for the LEAP tool implementations.

The tools are plain Python methods on mixin classes. ``leap.server`` is a thin
MCP wrapper around them, which keeps every tool unit-testable without a
transport in the loop.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Mapping, Sequence

from leap.config import Config, load_config
from leap.runtime.events import EventLog
from leap.runtime.state_guard import StateGuard
from leap.storage import new_id, new_request_id, now_ts

__all__ = ["ToolError", "ToolContext", "LeapToolMixin", "json_dumps", "mcp_parameters"]


@lru_cache(maxsize=1)
def compact_policy() -> dict:
    """The small every-response policy receipt.

    Responses used to embed the whole ~2.4 KB delivery summary, which dominates
    the token cost of a lesson. Every response now carries only the identity of
    the active policy; the full contract is served by
    ``get_teaching_delivery_policy`` (and stays in the server instructions).
    """
    from leap.runtime.delivery import delivery_policy

    policy = delivery_policy()
    return {
        "policy_id": policy.get("policy_id"),
        "version": policy.get("version"),
        "mandatory": True,
    }


def mcp_parameters(
    *, first: tuple[str, ...], defaults: Mapping[str, Any],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Preserve an MCP parameter layout while keeping Python positional callers."""
    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        signature = inspect.signature(fn, eval_str=True)
        parameters = {name: parameter for name, parameter in signature.parameters.items() if name != "self"}
        ordered = [*first, *(name for name in parameters if name not in first)]
        fn.__mcp_signature__ = signature.replace(parameters=[
            parameters[name].replace(
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=defaults.get(name, parameters[name].default),
            ) for name in ordered
        ])
        return fn
    return decorate


class ToolError(Exception):
    """Structured, client-safe error returned by a LEAP tool.

    The runtime must never turn a failure into a silent state update
    (section 29.1), so every tool either returns a value or raises this.
    ``retryable`` tells the host whether repeating the identical call can work.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: Mapping[str, Any] | None = None,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})
        self.retryable = bool(retryable)

    def as_dict(self) -> dict:
        payload = {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "retryable": self.retryable,
            },
            "policy_version": compact_policy()["version"],
            "teaching_delivery_policy": compact_policy(),
        }
        return payload


class PartialResultError(ToolError):
    """The tool deliberately persisted an artifact whose ID is in the error receipt."""


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
        strict_grounding: bool = True,
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
            guard=StateGuard(db, cfg, events, translator=translator, strict_grounding=strict_grounding),
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

    def require_node(self, node_id: str, session_id: str | None = None) -> dict:
        """Return a knowledge node, optionally enforcing session ownership.

        Node ids are global primary keys, so an unscoped lookup lets session A
        focus on session B's node. Every tool that receives a ``node_id`` from
        the host must pass the session it is acting on.
        """
        if session_id is None:
            row = self.db.query_one(
                "SELECT * FROM knowledge_nodes WHERE node_id = ?", (node_id,)
            )
        else:
            row = self.db.query_one(
                "SELECT * FROM knowledge_nodes WHERE node_id = ? AND session_id = ?",
                (node_id, session_id),
            )
        if row is None:
            if session_id is None:
                raise ToolError("unknown_node", f"knowledge node not found: {node_id}")
            raise ToolError(
                "invalid_node",
                f"knowledge node {node_id} does not belong to this session",
                {"node_id": node_id, "session_id": session_id},
            )
        return dict(row)

    def session_of_node(self, node_id: str) -> str | None:
        """Return the session that owns a node id (nodes live in one session)."""
        return self.db.scalar(
            "SELECT session_id FROM knowledge_nodes WHERE node_id = ?", (node_id,)
        )

    def require_active_session(self, session: Mapping[str, Any]) -> dict:
        """Reject teaching calls on a closed session with a recoverable error."""
        status = str(session.get("status") or "active")
        if status in {"completed", "abandoned"}:
            raise ToolError(
                "session_closed",
                f"session is {status}; teaching is closed. Start a new session or "
                "reopen this one with complete_session(status='active', reopen=True).",
                {"session_id": session.get("session_id"), "status": status,
                 "retryable": False},
            )
        return dict(session)

    def final_report_artifact_id(self, session_id: str) -> str | None:
        return self.db.scalar(
            "SELECT artifact_id FROM artifacts WHERE session_id = ? "
            "AND artifact_type = 'final_report' ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (session_id,),
        )

    def diagnostic_completed(self, session_id: str) -> bool:
        """True once a diagnostic summary was persisted for the session."""
        return bool(
            self.db.query_one(
                "SELECT 1 FROM artifacts WHERE session_id = ? AND artifact_type = 'diagnostic_result' "
                "UNION ALL "
                "SELECT 1 FROM event_log WHERE session_id = ? AND event_type = 'diagnostic_completed' "
                "LIMIT 1",
                (session_id, session_id),
            )
        )

    # -- effective configuration ------------------------------------------
    def effective_conf(self, session_id: str | None, key: str, default: Any = None) -> Any:
        """Read a config value through the session's learning-mode overrides.

        The policy engine already resolves overrides this way; tools and the
        State Guard must use the same value or a mode silently stops working.
        """
        if session_id:
            from leap.runtime.state_guard import session_overrides

            overrides = session_overrides(self.db, session_id)
            if key in overrides:
                return overrides[key]
        return self.conf(key, default)

    def require_grounding(self, session_id: str) -> dict:
        decision = self.guard.check_domain_grounding(session_id)
        if not decision.allowed:
            raise ToolError(decision.details.get("error_code", "domain_grounding_required"),
                            decision.reason, decision.as_dict())
        return decision.details

    def require_reviewed_package(self, session_id: str, package_id: str, grounding: dict) -> None:
        row = self.db.query_one(
            "SELECT metadata FROM artifacts WHERE artifact_id=? AND session_id=? AND artifact_type='teaching_package'",
            (package_id, session_id),
        )
        metadata = json.loads(row["metadata"] or "{}") if row else {}
        if metadata.get("course_revision") != grounding["course_revision"]:
            raise ToolError("grounding_unreviewed_content", "Register the reviewed lesson for the current source revision")

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

    # -- response envelope -------------------------------------------------
    @staticmethod
    def ok(**payload: Any) -> dict:
        """Return the success envelope.

        Carries the compact policy receipt (identity only) instead of the whole
        delivery contract; the full contract is one explicit call away.
        """
        return {
            "ok": True,
            **payload,
            "policy_version": compact_policy()["version"],
            "teaching_delivery_policy": compact_policy(),
        }

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
