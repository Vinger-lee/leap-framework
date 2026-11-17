"""LEAP MCP Server (stdio transport).

Exposes the runtime to any host agent over the Model Context Protocol. P0 uses
**stdio only** - no HTTP/SSE, no authentication, single-machine trusted
environment (section 3.1).

Design: this file is a thin adapter. All logic lives in
:mod:`leap.tools`, so every tool can be tested without a transport.

Run::

    python -m leap.server
    # or, after installation:
    leap-mcp
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import inspect
import json
import logging
import os
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Sequence

from mcp.server.mcpserver import MCPServer

from leap import __version__
from leap.config import load_config, resolve_path
from leap.runtime.profiles import ALL_TOOL_NAMES, allowed_tool_names, available_profiles, resolve_profile
from leap.tools import LeapService, ToolError, build_service
from leap.tools.base import PartialResultError

__all__ = [
    "server",
    "main",
    "get_service",
    "get_server",
    "build_server",
    "registered_tool_names",
]

logger = logging.getLogger("leap.server")

_service: LeapService | None = None
_service_lock = threading.Lock()

#: Built-in default for each pluggable seam. A configured name that is not
#: registered falls back to this value with a warning instead of killing the
#: server at startup (``get_plugin_info`` documented that fallback; now it is
#: true).
_SEAM_DEFAULTS: dict[str, str] = {
    "mastery_estimator": "simplified_bkt",
    "score_aggregator": "weighted",
    "policy_engine": "rule_based",
    "review_scheduler": "py-fsrs",
    "storage_backend": "sqlite",
    "artifact_store": "local",
}


def _effective_config():
    """Load config, replacing unregistered seam names with their defaults.

    A typo in ``config/default.yaml`` must not turn into "MCP server failed to
    start" with only a traceback on stderr: warn, keep serving, and let
    ``get_plugin_info`` report which implementation is actually active.
    """
    cfg = load_config()
    try:
        from leap.runtime.plugins import describe_plugins

        available = describe_plugins()
    except Exception:  # pragma: no cover - registry import must not break startup
        return cfg
    overrides: dict[str, str] = {}
    for kind, default in _SEAM_DEFAULTS.items():
        configured = cfg.get(kind)
        if configured and str(configured) not in available.get(kind, []):
            logger.warning(
                "configured %s=%r is not registered (available: %s); falling back to %r",
                kind,
                configured,
                ", ".join(available.get(kind, ()) or ("(none)",)),
                default,
            )
            overrides[kind] = default
    return load_config(overrides=overrides) if overrides else cfg


def get_service() -> LeapService:
    """Return the process-wide service, creating it on first use."""
    global _service
    with _service_lock:
        if _service is None:
            cfg = _effective_config()
            raw_path = str(cfg.get("database_path", "data/leap.db"))
            db_path = resolve_path(raw_path)
            _service = build_service(db_path, cfg)
            logger.info(
                "LEAP runtime ready: db=%s (configured as %r, LEAP_HOME=%s) schema=%s",
                db_path,
                raw_path,
                os.environ.get("LEAP_HOME") or "(unset)",
                __version__,
            )
        return _service


class _DeferredContext:
    """Resolve dependencies when a tool runs, keeping catalog inspection read-only."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_service().ctx, name)


#: How a raw sqlite failure is presented to the host. A driver-level error
#: must never leak as an opaque ``internal_error``: the host needs to know
#: whether it can retry and what to fix.
def _sqlite_error(exc: BaseException, tool: str) -> ToolError:
    message = str(exc)
    lowered = message.lower()
    if isinstance(exc, sqlite3.OperationalError) and ("locked" in lowered or "busy" in lowered):
        return ToolError(
            "database_busy",
            f"the database is locked by another process; retry shortly ({message})",
            {"tool": tool, "retryable": True},
            retryable=True,
        )
    if isinstance(exc, sqlite3.IntegrityError):
        return ToolError(
            "data_integrity_error",
            f"the write violates a database invariant: {message}",
            {"tool": tool, "hint": "check ids belong to this session and retry with fresh ids",
             "retryable": False},
            retryable=False,
        )
    return ToolError(
        "database_error",
        f"database error while running {tool}: {message}",
        {"tool": tool, "retryable": True},
        retryable=True,
    )


def _call_idempotently(
    fn: Callable[..., Any], request_id: str, arguments: dict[str, Any]
) -> dict:
    """Commit the SQLite writes and their replay receipt in the same transaction."""
    tool_name = fn.__name__
    encoded = json.dumps(arguments, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    arguments_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    db = get_service().db
    with db.transaction():
        stored = db.request_record(request_id)
        if stored is not None:
            if stored["tool_name"] != tool_name or stored["arguments_hash"] != arguments_hash:
                raise ToolError(
                    "request_id_conflict", "request_id belongs to another call; use a fresh request_id"
                )
            return {**json.loads(stored["response"]), "idempotent_replay": True, "replayed_tool": tool_name}

        try:
            result = fn(**arguments)
        except PartialResultError as exc:
            # The facade has deliberately kept an attempt for host-side recovery.
            # Persist the failure receipt so a timeout cannot duplicate that attempt.
            result = exc.as_dict()
        session_id = arguments.get("session_id") or result.get("session_id")
        db.remember_request(
            request_id, tool_name, session_id, json.dumps(result, ensure_ascii=False),
            arguments_hash=arguments_hash,
        )
        return result


def _guard(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Return structured errors and replay completed writes with a request ID."""
    mcp_signature = getattr(fn, "__mcp_signature__", None)
    signature = mcp_signature or inspect.signature(fn, eval_str=True)

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = dict(bound.arguments)
            request_id = arguments.get("request_id")
            if request_id:
                return _call_idempotently(fn, request_id, arguments)
            return fn(**arguments)
        except ToolError as exc:
            return exc.as_dict()
        except FileNotFoundError as exc:
            return ToolError("not_found", str(exc)).as_dict()
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
            logger.exception("tool %s hit a database error", fn.__name__)
            return _sqlite_error(exc, fn.__name__).as_dict()
        except Exception as exc:  # pragma: no cover - defensive boundary
            logger.exception("tool %s failed", fn.__name__)
            return ToolError("internal_error", str(exc), {"tool": fn.__name__}).as_dict()

    if mcp_signature is not None:
        wrapper.__signature__ = mcp_signature
    return wrapper


# ---------------------------------------------------------------------------
# Tool profiles
# ---------------------------------------------------------------------------
def _configured_profile() -> str | None:
    """Read ``tool_profile`` from configuration, tolerating a broken config."""
    try:
        value = load_config().get("tool_profile")
    except Exception:  # pragma: no cover - a broken config surfaces in the tool calls
        return None
    return str(value) if value else None


def registered_tool_names(server: MCPServer) -> list[str]:
    """Return the tool names a built server currently exposes.

    This supports startup diagnostics without an async ``list_tools()`` round
    trip. The mcp package (>=2) keeps its registry in ``ToolManager._tools``;
    the profile tests fail loudly if a future version changes that, instead of
    silently exposing the whole surface.
    """
    tools = getattr(getattr(server, "_tool_manager", None), "_tools", None)
    if not isinstance(tools, dict):
        raise RuntimeError(
            "the installed mcp package exposes no synchronous tool registry; "
            "tool profiles require mcp>=2 (see tests/test_tool_profiles.py)"
        )
    return list(tools)


def _tool_names_for_profile(profile: str) -> tuple[str, ...]:
    """Validate a profile and select its tools before building their schemas."""
    allowed = allowed_tool_names(profile)
    if allowed is None:
        return ALL_TOOL_NAMES
    unknown = sorted(allowed - set(ALL_TOOL_NAMES))
    if unknown:
        raise RuntimeError(f"tool profile {profile!r} lists unregistered tools: {unknown}")
    return tuple(name for name in ALL_TOOL_NAMES if name in allowed)


# ---------------------------------------------------------------------------
# Server definition
# ---------------------------------------------------------------------------
def build_server(profile: str | None = None) -> MCPServer:
    """Create and register the MCP server.

    ``profile`` selects how much of the tool surface an MCP client sees (see
    :mod:`leap.runtime.profiles`): ``full`` exposes everything registered,
    ``quickstart`` exposes the coarse tutor API plus the setup tools a complete
    lesson needs. Only selected schemas are built; the underlying service keeps
    every capability, so an integration can move from ``quickstart`` to ``full``
    without a data migration.

    Resolution order: ``profile`` argument > ``LEAP_TOOL_PROFILE`` environment
    variable > ``tool_profile`` in ``config/default.yaml`` > ``full``.
    """
    resolved = resolve_profile(profile, fallback=_configured_profile())
    names = _tool_names_for_profile(resolved)
    logger.info("registering MCP tools for profile %r", resolved)
    server = MCPServer(
        name="leap-framework",
        title="LEAP - Learning Evolution & Adaptation Pipeline",
        version=__version__,
        instructions=(
            "LEAP is a state-driven tutoring runtime. Runtime owns persistent state, evidence, "
            "mastery estimation and State Guard transitions. Use the current state and policy. "
            "For detailed workflows, load the repository's leap-tutor Skill when supported; "
            "otherwise consult the Host Agent integration guide. Skill availability is host-dependent. "
            "Domain Grounding requires a current reviewed source pack. Call get_grounding_sources, "
            "read the located passages, independently solve the checks, and call save_benchmark_report "
            "with course_revision, chunk_ids and check_answers. If evidence is unavailable, pause. "
            "The server guards diagnostics and teaching entry points. Register each generated item "
            "via save_assessment_item before delivery; independently solve it, check boundary cases, "
            "options and counterexamples. Free-text reasoning needs semantic review by the host, "
            "not keyword scoring. LEAP validates records and estimates state; it does not verify "
            "the truth of supplied mathematical answers. mastery_probability is "
            "computed server-side from evidence you submit via commit_assessment - never "
            "send your own probability. Always pass raw_answer when committing an assessment."
            " Never bypass a State Guard rejection or claim success without the matching receipt. "
            "Preserve IDs after partial failures and recover from the failed step instead of "
            "repeating successful writes. Check actual profile availability before following next_call. "
            "Generate the final report and close the session separately; confirm each result. "
            "Call get_teaching_delivery_policy once before authoring; its permanent requirements "
            "apply to every subject and mode, including core_only. Register the reviewed canonical "
            "Markdown and HTML returned by get_grounding_sources(include_lesson=true) before items. "
            "Keep new host-authored material as drafts. Tool responses carry only policy_version; re-fetch the "
            "policy explicitly when you need the full contract."
        ),
    )

    service = LeapService(_DeferredContext())
    for name in names:
        server.tool()(_guard(getattr(service, name)))

    return server


_server: MCPServer | None = None


def get_server() -> MCPServer:
    """Return the process-wide default server (built on first use)."""
    global _server
    if _server is None:
        _server = build_server()
    return _server


def __getattr__(name: str) -> Any:
    """Lazily expose ``leap.server.server`` without paying the build at import.

    The MCP CLI builds exactly the requested profile; an eager default server
    would build a second, unused tool registry (and its schemas) on every
    ``--tool-profile`` run.
    """
    if name == "server":
        return get_server()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main(argv: Sequence[str] | None = None) -> None:
    """Entry point: run the MCP server over stdio."""
    parser = argparse.ArgumentParser(description="Run the LEAP MCP server over stdio.")
    parser.add_argument(
        "--tool-profile",
        choices=available_profiles(),
        default=None,
        help=(
            "how much of the tool surface the client sees (default: LEAP_TOOL_PROFILE, "
            "then tool_profile in config/default.yaml, then full)"
        ),
    )
    args, extra = parser.parse_known_args(argv)

    logging.basicConfig(
        level=os.environ.get("LEAP_LOG_LEVEL", "INFO").upper(),
        stream=sys.stderr,  # stdout is reserved for the MCP protocol
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if extra:
        logger.warning("ignoring unrecognised arguments: %s", extra)
    transport = os.environ.get("LEAP_MCP_TRANSPORT", "stdio")
    if transport != "stdio":
        logger.warning(
            "P0 supports stdio only; requested transport %r. Falling back to stdio.", transport
        )
    # Build only the resolved profile: the default server is created lazily, so
    # an explicit profile does not pay for a second unused registry.
    active = build_server(args.tool_profile)
    logger.info(
        "LEAP MCP server ready: profile=%s tools=%d",
        resolve_profile(args.tool_profile, fallback=_configured_profile()),
        len(registered_tool_names(active)),
    )
    get_service()
    active.run(transport="stdio")


if __name__ == "__main__":
    main()
