"""LEAP tool implementations.

``LeapService`` composes every tool mixin into one object. ``leap.server``
exposes it over MCP; tests call it directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from leap.config import Config, load_config
from leap.storage import Database
from leap.tools.assessment import AssessmentTools
from leap.tools.artifact import ArtifactTools
from leap.tools.base import LeapToolMixin, ToolContext, ToolError
from leap.tools.evidence import EvidenceTools
from leap.tools.knowledge import KnowledgeTools
from leap.tools.retention import RetentionTools
from leap.tools.session import SessionTools
from leap.tools.teaching import TeachingTools

__all__ = [
    "LeapService",
    "ToolContext",
    "ToolError",
    "SessionTools",
    "KnowledgeTools",
    "AssessmentTools",
    "RetentionTools",
    "TeachingTools",
    "EvidenceTools",
    "ArtifactTools",
    "build_service",
]


class LeapService(
    SessionTools,
    KnowledgeTools,
    AssessmentTools,
    RetentionTools,
    TeachingTools,
    EvidenceTools,
    ArtifactTools,
):
    """The complete LEAP runtime API surface (section 22)."""

    def __init__(self, ctx: ToolContext) -> None:
        super().__init__(ctx)

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        self.db.close()


def build_service(
    database_path: str | Path = ":memory:",
    config: Config | dict[str, Any] | None = None,
    *,
    initialize: bool = True,
) -> LeapService:
    """Create a ready-to-use service.

    ``database_path`` defaults to an in-memory database, which is what tests
    and examples use. Production runs point it at ``data/leap.db``.

    The concrete storage backend, estimator, aggregator, policy engine,
    scheduler and artifact store are all resolved from configuration through
    the plugin registry (section 35).
    """
    if isinstance(config, Config):
        cfg = config
    elif isinstance(config, dict):
        cfg = load_config(overrides=config)
    else:
        cfg = load_config()

    ctx = ToolContext.build(None, cfg, database_path=str(database_path))
    if initialize:
        ctx.db.initialize()
    return LeapService(ctx)
