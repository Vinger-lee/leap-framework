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
from leap.runtime.profiles import allowed_tool_names, available_profiles, resolve_profile
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


def _guard(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Convert runtime errors into structured, client-safe responses.

    Section 29.1: a failed tool call must return a structured error and must
    never be turned into a silent state update.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ToolError as exc:
            return exc.as_dict()
        except FileNotFoundError as exc:
            return ToolError("not_found", str(exc)).as_dict()
        except Exception as exc:  # pragma: no cover - defensive boundary
            logger.exception("tool %s failed", fn.__name__)
            return ToolError("internal_error", str(exc), {"tool": fn.__name__}).as_dict()

    wrapper.__doc__ = fn.__doc__ or getattr(LeapService, fn.__name__).__doc__
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

    # -- 22.0 Coarse tutor API (facade) ------------------------------------
    # One call per teaching-loop step, composed server-side from the
    # fine-grained tools below. Same runtime, same State Guard, same evidence
    # rules - fewer calls to get right. See leap.tools.facade.
    @server.tool()
    @_guard
    def start_learning(
        learner_id: str,
        topic: str,
        goal: str | None = None,
        target_depth: str | None = None,
        target_domain: str | None = None,
        target_outcome: str | None = None,
        time_budget: int | None = None,
        prior_knowledge: str | None = None,
        constraints: str | None = None,
        mode: str | None = None,
        allow_skip_domain_grounding: bool | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().start_learning(
            learner_id, topic, goal=goal, target_depth=target_depth,
            target_domain=target_domain, target_outcome=target_outcome,
            time_budget=time_budget, prior_knowledge=prior_knowledge,
            constraints=constraints, mode=mode,
            allow_skip_domain_grounding=allow_skip_domain_grounding,
            request_id=request_id,
        )

    @server.tool()
    @_guard
    def continue_lesson(session_id: str, node_id: str | None = None) -> dict:
        return get_service().continue_lesson(session_id, node_id)

    @server.tool()
    @_guard
    def log_teaching_action(
        session_id: str,
        action: str | None = None,
        strategy: str | None = None,
        node_id: str | None = None,
        rationale: str | None = None,
        expected_outcome: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().log_teaching_action(
            session_id, action=action, strategy=strategy, node_id=node_id,
            rationale=rationale, expected_outcome=expected_outcome, request_id=request_id,
        )

    @server.tool()
    @_guard
    def submit_answer(
        session_id: str,
        answer: str,
        item_id: str | None = None,
        node_id: str | None = None,
        hint_level: int = 0,
        response_time: float | None = None,
        correctness: float | None = None,
        conceptual_understanding: float | None = None,
        reasoning_quality: float | None = None,
        application: float | None = None,
        transfer: float | None = None,
        hint_dependency: float | None = None,
        assessor_type: str = "model",
        assessor_confidence: float = 1.0,
        confidence: float | None = None,
        expected_state_version: int | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().submit_answer(
            session_id, answer, item_id=item_id, node_id=node_id, hint_level=hint_level,
            response_time=response_time, correctness=correctness,
            conceptual_understanding=conceptual_understanding,
            reasoning_quality=reasoning_quality, application=application, transfer=transfer,
            hint_dependency=hint_dependency, assessor_type=assessor_type,
            assessor_confidence=assessor_confidence, confidence=confidence,
            expected_state_version=expected_state_version, request_id=request_id,
        )

    @server.tool()
    @_guard
    def advance_lesson(
        session_id: str,
        unit_tag: str | None = None,
        node_id: str | None = None,
        manual_override: bool = False,
        request_id: str | None = None,
    ) -> dict:
        return get_service().advance_lesson(
            session_id, unit_tag=unit_tag, node_id=node_id,
            manual_override=manual_override, request_id=request_id,
        )

    @server.tool()
    @_guard
    def get_review_queue(
        learner_id: str, session_id: str | None = None, limit: int = 10
    ) -> dict:
        return get_service().get_review_queue(learner_id, session_id=session_id, limit=limit)

    @server.tool()
    @_guard
    def review_answer(
        review_item_id: str,
        rating: int,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().review_answer(
            review_item_id, rating, session_id=session_id, request_id=request_id
        )

    @server.tool()
    @_guard
    def get_learner_snapshot(session_id: str) -> dict:
        return get_service().get_learner_snapshot(session_id)

    # -- 22.1 Session / Goal ------------------------------------------------
    @server.tool()
    @_guard
    def create_session(
        learner_id: str,
        topic: str,
        learner_name: str | None = None,
        allow_skip_domain_grounding: bool | None = None,
        domain_grounding_warn_user: bool | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().create_session(
            learner_id, topic,
            learner_name=learner_name,
            allow_skip_domain_grounding=allow_skip_domain_grounding,
            domain_grounding_warn_user=domain_grounding_warn_user,
            request_id=request_id,
        )

    @server.tool()
    @_guard
    def find_session(learner_id: str, topic: str | None = None) -> dict:
        return get_service().find_session(learner_id, topic)

    @server.tool()
    @_guard
    def get_session_info(session_id: str) -> dict:
        return get_service().get_session_info(session_id)

    @server.tool()
    @_guard
    def save_learning_goal(
        session_id: str,
        goal: str | None = None,
        target_domain: str | None = None,
        target_outcome: str | None = None,
        target_depth: str | None = None,
        time_budget: int | None = None,
        prior_knowledge: str | None = None,
        constraints: str | None = None,
        materials: str | None = None,
        assessment_requirements: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().save_learning_goal(
            session_id, goal, target_domain=target_domain, target_outcome=target_outcome,
            target_depth=target_depth, time_budget=time_budget, prior_knowledge=prior_knowledge,
            constraints=constraints, materials=materials,
            assessment_requirements=assessment_requirements, request_id=request_id,
        )

    @server.tool()
    @_guard
    def get_learning_goal(session_id: str) -> dict:
        return get_service().get_learning_goal(session_id)

    @server.tool()
    @_guard
    def set_learning_configuration(
        session_id: str,
        request: str | None = None,
        mode: str | None = None,
        overrides: dict | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().set_learning_configuration(
            session_id, request=request, mode=mode, overrides=overrides, request_id=request_id
        )

    @server.tool()
    @_guard
    def get_learning_configuration(session_id: str) -> dict:
        return get_service().get_learning_configuration(session_id)

    # -- 22.2 Diagnostic ----------------------------------------------------
    @server.tool()
    @_guard
    def generate_diagnostic(session_id: str, request_id: str | None = None) -> dict:
        return get_service().generate_diagnostic(session_id, request_id=request_id)

    @server.tool()
    @_guard
    def submit_diagnostic(
        session_id: str,
        answer: str,
        item_id: str | None = None,
        node_id: str | None = None,
        question: str | None = None,
        hint_level: int = 0,
        response_time: float | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().submit_diagnostic(
            session_id, answer, item_id=item_id, node_id=node_id, question=question,
            hint_level=hint_level, response_time=response_time, request_id=request_id,
        )

    @server.tool()
    @_guard
    def get_diagnostic_result(session_id: str) -> dict:
        return get_service().get_diagnostic_result(session_id)

    @server.tool()
    @_guard
    def save_diagnostic_result(session_id: str, result: Any, request_id: str | None = None) -> dict:
        return get_service().save_diagnostic_result(session_id, result, request_id=request_id)

    # -- 22.3 Knowledge -----------------------------------------------------
    @server.tool()
    @_guard
    def decompose_topic(session_id: str, topic: str | None = None) -> dict:
        return get_service().decompose_topic(session_id, topic)

    @server.tool()
    @_guard
    def save_knowledge_nodes(
        session_id: str, nodes: list[dict], request_id: str | None = None
    ) -> dict:
        return get_service().save_knowledge_nodes(session_id, nodes, request_id=request_id)

    @server.tool()
    @_guard
    def save_knowledge_edges(
        session_id: str, edges: list[dict], request_id: str | None = None
    ) -> dict:
        return get_service().save_knowledge_edges(session_id, edges, request_id=request_id)

    @server.tool()
    @_guard
    def get_knowledge_nodes(session_id: str, unit_tag: str | None = None) -> dict:
        return get_service().get_knowledge_nodes(session_id, unit_tag)

    @server.tool()
    @_guard
    def get_knowledge_edges(session_id: str) -> dict:
        return get_service().get_knowledge_edges(session_id)

    @server.tool()
    @_guard
    def validate_knowledge_dag(session_id: str) -> dict:
        return get_service().validate_knowledge_dag(session_id)

    # -- 22.4 Teaching context ---------------------------------------------
    @server.tool()
    @_guard
    def get_teaching_context(session_id: str, node_id: str | None = None) -> dict:
        return get_service().get_teaching_context(session_id, node_id)

    # -- 22.5 Pedagogical policy -------------------------------------------
    @server.tool()
    @_guard
    def get_available_strategies() -> dict:
        return get_service().get_available_strategies()

    @server.tool()
    @_guard
    def get_available_actions() -> dict:
        return get_service().get_available_actions()

    @server.tool()
    @_guard
    def get_plugin_info() -> dict:
        return get_service().get_plugin_info()

    @server.tool()
    @_guard
    def evaluate_pedagogical_policy(
        session_id: str, node_id: str | None = None, trigger_event: str | None = None
    ) -> dict:
        return get_service().evaluate_pedagogical_policy(session_id, node_id, trigger_event=trigger_event)

    @server.tool()
    @_guard
    def commit_pedagogical_decision(
        session_id: str,
        selected_strategy: str | None = None,
        selected_action: str | None = None,
        node_id: str | None = None,
        trigger_event: str | None = None,
        rationale: str | None = None,
        expected_outcome: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().commit_pedagogical_decision(
            session_id, selected_strategy, selected_action, node_id=node_id,
            trigger_event=trigger_event, rationale=rationale,
            expected_outcome=expected_outcome, request_id=request_id,
        )

    @server.tool()
    @_guard
    def get_decision_log(session_id: str, limit: int = 50) -> dict:
        return get_service().get_decision_log(session_id, limit)

    # -- 22.6 Assessment ----------------------------------------------------
    @server.tool()
    @_guard
    def generate_assessment(
        session_id: str,
        node_id: str | None = None,
        question_type: str | None = None,
        count: int = 1,
    ) -> dict:
        return get_service().generate_assessment(session_id, node_id, question_type=question_type, count=count)

    @server.tool()
    @_guard
    def assess_response(
        session_id: str,
        scores: dict,
        raw_answer: str | None = None,
        assessor_type: str = "model",
        assessor_confidence: float = 1.0,
    ) -> dict:
        return get_service().assess_response(
            session_id, scores, raw_answer=raw_answer,
            assessor_type=assessor_type, assessor_confidence=assessor_confidence,
        )

    @server.tool()
    @_guard
    def assess_misconception(
        learner_id: str,
        node_id: str,
        misconception: str,
        severity: float = 0.5,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().assess_misconception(
            learner_id, node_id, misconception, severity=severity,
            session_id=session_id, request_id=request_id,
        )

    @server.tool()
    @_guard
    def resolve_misconception(misconception_id: int, session_id: str | None = None) -> dict:
        return get_service().resolve_misconception(misconception_id, session_id=session_id)

    @server.tool()
    @_guard
    def get_mastery_status(session_id: str, node_id: str | None = None) -> dict:
        return get_service().get_mastery_status(session_id, node_id)

    @server.tool()
    @_guard
    def get_assessment_history(
        session_id: str, node_id: str | None = None, limit: int = 50
    ) -> dict:
        return get_service().get_assessment_history(session_id, node_id, limit)

    @server.tool()
    @_guard
    def generate_transfer_probe(session_id: str, node_id: str | None = None) -> dict:
        return get_service().generate_transfer_probe(session_id, node_id)

    @server.tool()
    @_guard
    def save_assessment_item(
        session_id: str, item_id: str, question: str, expected_answer: str,
        solution: str, assumptions: list[str], verification_checks: list[dict],
        node_id: str | None = None, source_ids: list[str] | None = None,
        rejected_answers: list[dict] | None = None, assessor_scope: str = "host_semantic_review",
        teaching_package_id: str | None = None,
    ) -> dict:
        return get_service().save_assessment_item(
            session_id, item_id, question, expected_answer, solution, assumptions, verification_checks,
            node_id=node_id, source_ids=source_ids, rejected_answers=rejected_answers, assessor_scope=assessor_scope,
            teaching_package_id=teaching_package_id,
        )

    # -- 22.7 Retention -----------------------------------------------------
    @server.tool()
    @_guard
    def get_review_state(learner_id: str, node_id: str | None = None) -> dict:
        return get_service().get_review_state(learner_id, node_id)

    @server.tool()
    @_guard
    def schedule_review(
        learner_id: str,
        node_id: str,
        session_id: str | None = None,
        item_ref: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().schedule_review(
            learner_id, node_id, session_id=session_id, item_ref=item_ref, request_id=request_id
        )

    @server.tool()
    @_guard
    def submit_review(
        review_item_id: str, rating: int, session_id: str | None = None, request_id: str | None = None
    ) -> dict:
        return get_service().submit_review(
            review_item_id, rating, session_id=session_id, request_id=request_id
        )

    @server.tool()
    @_guard
    def get_due_reviews(learner_id: str, limit: int = 50, session_id: str | None = None) -> dict:
        return get_service().get_due_reviews(learner_id, limit=limit, session_id=session_id)

    @server.tool()
    @_guard
    def recalculate_review_schedule(learner_id: str, now: int | None = None) -> dict:
        return get_service().recalculate_review_schedule(learner_id, now=now)

    # -- 22.8 State Guard ---------------------------------------------------
    @server.tool()
    @_guard
    def start_unit(
        session_id: str,
        unit_tag: str | None = None,
        node_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().start_unit(
            session_id, unit_tag=unit_tag, node_id=node_id, request_id=request_id
        )

    @server.tool()
    @_guard
    def check_advance_unit(
        session_id: str,
        unit_tag: str | None = None,
        node_id: str | None = None,
        manual_override: bool = False,
        expected_state_version: int | None = None,
    ) -> dict:
        return get_service().check_advance_unit(
            session_id, unit_tag=unit_tag, node_id=node_id,
            manual_override=manual_override, expected_state_version=expected_state_version,
        )

    @server.tool()
    @_guard
    def submit_attempt(
        session_id: str,
        answer: str,
        item_id: str | None = None,
        node_id: str | None = None,
        hint_level: int = 0,
        response_time: float | None = None,
        predicted_performance: float | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().submit_attempt(
            session_id, answer, item_id=item_id, node_id=node_id, hint_level=hint_level,
            response_time=response_time, predicted_performance=predicted_performance,
            request_id=request_id,
        )

    @server.tool()
    @_guard
    def commit_assessment(
        attempt_id: str,
        raw_answer: str,
        assessor_type: str = "model",
        correctness: float | None = None,
        conceptual_understanding: float | None = None,
        reasoning_quality: float | None = None,
        application: float | None = None,
        transfer: float | None = None,
        hint_dependency: float | None = None,
        confidence: float | None = None,
        assessor_confidence: float = 1.0,
        expected_state_version: int | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().commit_assessment(
            attempt_id, raw_answer, assessor_type=assessor_type, correctness=correctness,
            conceptual_understanding=conceptual_understanding, reasoning_quality=reasoning_quality,
            application=application, transfer=transfer, hint_dependency=hint_dependency,
            confidence=confidence, assessor_confidence=assessor_confidence,
            expected_state_version=expected_state_version, request_id=request_id,
        )

    @server.tool()
    @_guard
    def advance_unit(
        session_id: str,
        unit_tag: str | None = None,
        node_id: str | None = None,
        manual_override: bool = False,
        expected_state_version: int | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().advance_unit(
            session_id, unit_tag=unit_tag, node_id=node_id, manual_override=manual_override,
            expected_state_version=expected_state_version, request_id=request_id,
        )

    @server.tool()
    @_guard
    def rollback_unit(
        session_id: str,
        target_node_id: str,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().rollback_unit(
            session_id, target_node_id, reason=reason, request_id=request_id
        )

    @server.tool()
    @_guard
    def record_transfer_result(
        learner_id: str,
        node_id: str,
        transfer_type: str,
        score: float,
        task_context: str | None = None,
        result: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().record_transfer_result(
            learner_id, node_id, transfer_type, score, task_context=task_context,
            result=result, session_id=session_id, request_id=request_id,
        )

    @server.tool()
    @_guard
    def record_reflection(
        session_id: str, reflection: Any, node_id: str | None = None, request_id: str | None = None
    ) -> dict:
        return get_service().record_reflection(
            session_id, reflection, node_id=node_id, request_id=request_id
        )

    @server.tool()
    @_guard
    def complete_session(
        session_id: str, status: str = "completed", request_id: str | None = None
    ) -> dict:
        return get_service().complete_session(session_id, status=status, request_id=request_id)

    # -- 22.9 Evidence / Grounding -----------------------------------------
    @server.tool()
    @_guard
    def save_benchmark_report(
        session_id: str,
        report_text: str,
        source_refs: list[dict] | None = None,
        request_id: str | None = None,
        verification: dict | None = None,
    ) -> dict:
        return get_service().save_benchmark_report(
            session_id, report_text, source_refs=source_refs, request_id=request_id,
            verification=verification,
        )

    @server.tool()
    @_guard
    def save_benchmark_claim(
        session_id: str,
        claim: str,
        source_id: str | None = None,
        confidence: float | None = None,
        knowledge_scope: str | None = None,
        conflicting_sources: Any = None,
        request_id: str | None = None,
    ) -> dict:
        return get_service().save_benchmark_claim(
            session_id, claim, source_id=source_id, confidence=confidence,
            knowledge_scope=knowledge_scope, conflicting_sources=conflicting_sources,
            request_id=request_id,
        )

    @server.tool()
    @_guard
    def get_evidence(session_id: str, node_id: str | None = None) -> dict:
        return get_service().get_evidence(session_id, node_id)

    @server.tool()
    @_guard
    def validate_claim(claim_id: str, verified: bool = True) -> dict:
        return get_service().validate_claim(claim_id, verified=verified)

    @server.tool()
    @_guard
    def record_source_conflict(
        claim_id: str, conflicting_sources: Any, uncertainty: str | None = None
    ) -> dict:
        return get_service().record_source_conflict(
            claim_id, conflicting_sources, uncertainty=uncertainty
        )

    # -- 22.10 Artifact -----------------------------------------------------

    @server.tool()
    @_guard
    def get_teaching_delivery_policy() -> dict:
        return get_service().get_teaching_delivery_policy()

    @server.tool()
    @_guard
    def get_subject_catalog(subject: str | None = None) -> dict:
        return get_service().get_subject_catalog(subject)

    @server.tool()
    @_guard
    def save_teaching_package(
        session_id: str, node_id: str, subject: str, markdown: str, html: str,
        manifest: dict, request_id: str | None = None,
    ) -> dict:
        return get_service().save_teaching_package(session_id, node_id, subject, markdown, html, manifest, request_id=request_id)
    @server.tool()
    @_guard
    def save_artifact(
        learner_id: str,
        artifact_type: str,
        session_id: str | None = None,
        path_or_uri: str | None = None,
        content: str | None = None,
        metadata: Any = None,
        version: str = "1",
        request_id: str | None = None,
    ) -> dict:
        return get_service().save_artifact(
            learner_id, session_id, artifact_type, path_or_uri=path_or_uri,
            content=content, metadata=metadata, version=version, request_id=request_id,
        )

    @server.tool()
    @_guard
    def get_artifact(artifact_id: str, include_content: bool = True) -> dict:
        return get_service().get_artifact(artifact_id, include_content=include_content)

    @server.tool()
    @_guard
    def list_artifacts(session_id: str, artifact_type: str | None = None) -> dict:
        return get_service().list_artifacts(session_id, artifact_type)

    @server.tool()
    @_guard
    def get_obsidian_structure() -> dict:
        return get_service().get_obsidian_structure()

    @server.tool()
    @_guard
    def get_web_component_spec() -> dict:
        return get_service().get_web_component_spec()

    @server.tool()
    @_guard
    def export_session_data(session_id: str, output_path: str | None = None) -> dict:
        return get_service().export_session_data(session_id, output_path=output_path)

    @server.tool()
    @_guard
    def generate_final_report(session_id: str, save_as_artifact: bool = True) -> dict:
        return get_service().generate_final_report(session_id, save_as_artifact=save_as_artifact)

    @server.tool()
    @_guard
    def get_learning_metrics(session_id: str) -> dict:
        return get_service().get_learning_metrics(session_id)

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
