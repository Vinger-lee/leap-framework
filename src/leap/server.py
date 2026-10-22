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
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

from mcp.server.mcpserver import MCPServer

from leap import __version__
from leap.config import REPO_ROOT, load_config
from leap.runtime.profiles import ALL_TOOL_NAMES, allowed_tool_names, available_profiles, resolve_profile
from leap.tools import LeapService, ToolError, build_service

__all__ = ["server", "main", "get_service", "build_server", "registered_tool_names"]

logger = logging.getLogger("leap.server")

_service: LeapService | None = None


# ---------------------------------------------------------------------------
# Service bootstrap
# ---------------------------------------------------------------------------
def get_service() -> LeapService:
    """Return the process-wide service, creating it on first use."""
    global _service
    if _service is None:
        cfg = load_config()
        raw_path = str(cfg.get("database_path", "data/leap.db"))
        db_path = Path(raw_path)
        if not db_path.is_absolute():
            db_path = REPO_ROOT / db_path
        _service = build_service(db_path, cfg)
        logger.info("LEAP runtime ready: db=%s schema=%s", db_path, __version__)
    return _service


class _DeferredContext:
    """Resolve dependencies when a tool runs, keeping catalog inspection read-only."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_service().ctx, name)


def _guard(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Convert runtime errors into structured, client-safe responses.

    Section 29.1: a failed tool call must return a structured error and must
    never be turned into a silent state update.
    """

    signature = getattr(fn, "__mcp_signature__", None)

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            if signature is not None:
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                return fn(**bound.arguments)
            return fn(*args, **kwargs)
        except ToolError as exc:
            return exc.as_dict()
        except FileNotFoundError as exc:
            return ToolError("not_found", str(exc)).as_dict()
        except Exception as exc:  # pragma: no cover - defensive boundary
            logger.exception("tool %s failed", fn.__name__)
            return ToolError("internal_error", str(exc), {"tool": fn.__name__}).as_dict()

    if signature is not None:
        wrapper.__signature__ = signature
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

    Synchronous on purpose: profiles are applied while the server is being
    built, so an async ``list_tools()`` round trip is not available there. The
    mcp package (>=2) keeps its registry in ``ToolManager._tools``; the profile
    tests fail loudly if a future version changes that, instead of silently
    exposing the whole surface.
    """
    tools = getattr(getattr(server, "_tool_manager", None), "_tools", None)
    if not isinstance(tools, dict):
        raise RuntimeError(
            "the installed mcp package exposes no synchronous tool registry; "
            "tool profiles require mcp>=2 (see tests/test_tool_profiles.py)"
        )
    return list(tools)


def _apply_profile(server: MCPServer, profile: str) -> None:
    """Hide the tools a profile does not expose.

    Registration above always covers the complete surface, so the runtime keeps
    every capability; only the MCP catalog the client sees is narrowed.
    """
    allowed = allowed_tool_names(profile)
    if allowed is None:
        return
    registered = registered_tool_names(server)
    unknown = sorted(set(allowed) - set(registered))
    if unknown:
        raise RuntimeError(f"tool profile {profile!r} lists unregistered tools: {unknown}")
    for name in sorted(set(registered) - set(allowed)):
        server.remove_tool(name)


# ---------------------------------------------------------------------------
# Server definition
# ---------------------------------------------------------------------------
def build_server(profile: str | None = None) -> MCPServer:
    """Create and register the MCP server.

    ``profile`` selects how much of the tool surface an MCP client sees (see
    :mod:`leap.runtime.profiles`): ``full`` exposes everything registered,
    ``quickstart`` exposes the coarse tutor API plus the setup tools a complete
    lesson needs. Registration is identical in both cases - only the catalog is
    filtered - so an integration can move from ``quickstart`` to ``full``
    without a data migration.

    Resolution order: ``profile`` argument > ``LEAP_TOOL_PROFILE`` environment
    variable > ``tool_profile`` in ``config/default.yaml`` > ``full``.
    """
    resolved = resolve_profile(profile, fallback=_configured_profile())
    logger.info("registering MCP tools for profile %r", resolved)
    server = MCPServer(
        name="leap-framework",
        title="LEAP - Learning Evolution & Adaptation Pipeline",
        version=__version__,
        instructions=(
            "LEAP is a state-driven tutoring runtime. Follow the lifecycle: "
            "Goal -> Domain Grounding -> Diagnostic -> Knowledge DAG -> State Init -> "
            "Teaching loop -> Retention/Transfer -> Reflection -> Persistence. "
            "Domain Grounding is mandatory unless the session allows skipping it; the "
            "Read relevant authoritative sources yourself using host tools; record precise locators, "
            "excerpts, source-linked claims, worked checks and limitations via save_benchmark_report "
            "(verification). Saving prose alone does not complete grounding. Never claim source "
            "reading or syllabus alignment without evidence, and never enable skipping on your own. "
            "The server guards diagnostics and teaching entry points. Register each generated item "
            "via save_assessment_item before delivery; independently solve it, check boundary cases, "
            "options and counterexamples. Free-text reasoning needs semantic review by the host, "
            "not keyword scoring. LEAP validates records and estimates state; it does not verify "
            "the truth of supplied mathematical answers. mastery_probability is "
            "computed server-side from evidence you submit via commit_assessment - never "
            "send your own probability. Always pass raw_answer when committing an assessment."
            " Permanent delivery policy 3.0 applies to every subject and learning mode: fetch "
            "get_teaching_delivery_policy; teach prerequisites and principles with complete explained "
            "steps, worked checks, misconceptions, boundaries, contrasts and graduated transfer. "
            "Write the full Obsidian Markdown knowledge source before a shorter interactive offline "
            "HTML projection; both need verified relevant videos or precise core/extension/advanced "
            "search keywords at the top, reciprocal wikilinks, meaningful labeled controllable "
            "visualizations, wide desktop and mobile layouts. Register both bodies through "
            "save_teaching_package and verify every interaction. Never reduce these rules for core_only."
        ),
    )

    service = LeapService(_DeferredContext())
    for name in ALL_TOOL_NAMES:
        server.tool()(_guard(getattr(service, name)))

    _apply_profile(server, resolved)
    return server


server = build_server()


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
    active = server if args.tool_profile is None else build_server(args.tool_profile)
    logger.info(
        "LEAP MCP server ready: profile=%s tools=%d",
        resolve_profile(args.tool_profile, fallback=_configured_profile()),
        len(registered_tool_names(active)),
    )
    get_service()
    active.run(transport="stdio")


if __name__ == "__main__":
    main()
