"""Tool profiles: progressive exposure of the MCP surface.

The runtime registers a large, deliberately fine-grained tool surface (62 tools
before the coarse facade existed) because every state change has to be auditable
on its own. That is the right internal shape, but it is a hard entry point: the
host agent must pick the correct tool out of dozens on every turn.

A **tool profile** decides how much of that surface an MCP client sees. The
implementation is unchanged - filtering only happens when the server is built -
so no capability is removed from the runtime, and a host agent can move to
``full`` later without a data migration.

Profiles
--------
``quickstart``
    The coarse tutor API (``start_learning``, ``continue_lesson``,
    ``submit_answer``, ``advance_lesson``, ...) plus the authoring and setup
    tools a complete lesson genuinely needs: domain grounding, the knowledge
    DAG, the canonical teaching package, assessment items, diagnosis, transfer,
    reflection and the closing report. ~25 tools instead of 70.
``full``
    Every registered tool. This is the default, so an existing integration is
    never silently narrowed.

Selection order: explicit argument > ``LEAP_TOOL_PROFILE`` environment variable
> ``tool_profile`` in ``config/default.yaml`` > :data:`DEFAULT_PROFILE`.
"""

from __future__ import annotations

import os
from typing import Iterable

__all__ = [
    "PROFILES",
    "DEFAULT_PROFILE",
    "FACADE_TOOL_NAMES",
    "QUICKSTART_SETUP_TOOL_NAMES",
    "QUICKSTART_TOOL_NAMES",
    "available_profiles",
    "resolve_profile",
    "allowed_tool_names",
]

#: The coarse tutor API (see :mod:`leap.tools.facade`).
FACADE_TOOL_NAMES: tuple[str, ...] = (
    "start_learning",
    "continue_lesson",
    "log_teaching_action",
    "submit_answer",
    "advance_lesson",
    "get_review_queue",
    "review_answer",
    "get_learner_snapshot",
)

#: Everything a complete lesson needs beyond the coarse loop.
QUICKSTART_SETUP_TOOL_NAMES: tuple[str, ...] = (
    # Domain grounding + delivery contract
    "save_benchmark_report",
    "get_teaching_delivery_policy",
    "get_subject_catalog",
    # Knowledge structure
    "decompose_topic",
    "save_knowledge_nodes",
    "save_knowledge_edges",
    "validate_knowledge_dag",
    # Canonical lesson + registered items
    "save_teaching_package",
    "save_assessment_item",
    # Diagnosis
    "generate_diagnostic",
    "submit_diagnostic",
    "save_diagnostic_result",
    # Unit entry, transfer, reflection, closing report
    "start_unit",
    "generate_transfer_probe",
    "record_transfer_result",
    "record_reflection",
    "generate_final_report",
)

QUICKSTART_TOOL_NAMES: tuple[str, ...] = FACADE_TOOL_NAMES + QUICKSTART_SETUP_TOOL_NAMES

#: Profile name -> allowed tool names (``None`` means "everything registered").
PROFILES: dict[str, tuple[str, ...] | None] = {
    "quickstart": QUICKSTART_TOOL_NAMES,
    "full": None,
}

DEFAULT_PROFILE = "full"


def available_profiles() -> tuple[str, ...]:
    """Return the profile names this build knows, in a stable order."""
    return tuple(PROFILES)


def resolve_profile(name: str | None = None, *, fallback: str | None = None) -> str:
    """Resolve a profile name, raising on an unknown one.

    Unknown names are refused instead of silently falling back to ``full``: a
    typo that quietly exposes 70 tools while the operator believes the surface
    is narrow is worse than a startup error.
    """
    candidate = (name or os.environ.get("LEAP_TOOL_PROFILE") or fallback or DEFAULT_PROFILE).strip()
    if candidate not in PROFILES:
        raise ValueError(
            f"unknown tool profile {candidate!r}; available: {', '.join(available_profiles())}"
        )
    return candidate


def allowed_tool_names(profile: str) -> frozenset[str] | None:
    """Return the tool names a profile exposes (``None`` = every tool)."""
    resolved = resolve_profile(profile)
    names = PROFILES[resolved]
    return None if names is None else frozenset(names)


def excluded_tool_names(profile: str, registered: Iterable[str]) -> tuple[str, ...]:
    """Return the registered tools that a profile hides."""
    allowed = allowed_tool_names(profile)
    if allowed is None:
        return ()
    return tuple(sorted(set(registered) - allowed))
