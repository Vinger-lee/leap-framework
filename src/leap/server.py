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

import functools
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from leap import __version__
from leap.config import REPO_ROOT, load_config
from leap.tools import LeapService, ToolError, build_service

__all__ = ["server", "main", "get_service", "build_server"]

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
            return {"ok": False, "error": {"code": "not_found", "message": str(exc), "details": {}}}
        except Exception as exc:  # pragma: no cover - defensive boundary
            logger.exception("tool %s failed", fn.__name__)
            return {
                "ok": False,
                "error": {"code": "internal_error", "message": str(exc), "details": {"tool": fn.__name__}},
            }

    return wrapper


# ---------------------------------------------------------------------------
# Server definition
# ---------------------------------------------------------------------------
def build_server() -> MCPServer:
    """Create and register the MCP server with the full tool set."""
    server = MCPServer(
        name="leap-framework",
        title="LEAP - Learning Evolution & Adaptation Pipeline",
        version=__version__,
        instructions=(
            "LEAP is a state-driven tutoring runtime. Follow the lifecycle: "
            "Goal -> Domain Grounding -> Diagnostic -> Knowledge DAG -> State Init -> "
            "Teaching loop -> Retention/Transfer -> Reflection -> Persistence. "
            "Domain Grounding is mandatory unless the session allows skipping it; the "
            "server will reject generate_diagnostic otherwise. mastery_probability is "
            "computed server-side from evidence you submit via commit_assessment - never "
            "send your own probability. Always pass raw_answer when committing an assessment."
        ),
    )

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
        """Create a learning session. learner_id is required (P0 is single-learner).

        Domain-grounding switches are stored per session, not globally. When
        domain_grounding_warn_user is true the returned notice must be shown to
        the user before the grounding stage starts.
        """
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
        """Find existing sessions by learner and optionally topic.

        Use this to recover a session id after a chat window is reopened.
        """
        return get_service().find_session(learner_id, topic)

    @server.tool()
    @_guard
    def get_session_info(session_id: str) -> dict:
        """Return session state, the latest goal, node count and the next lifecycle step."""
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
        """Persist the learning goal and its constraints (lifecycle Stage 1)."""
        return get_service().save_learning_goal(
            session_id, goal, target_domain=target_domain, target_outcome=target_outcome,
            target_depth=target_depth, time_budget=time_budget, prior_knowledge=prior_knowledge,
            constraints=constraints, materials=materials,
            assessment_requirements=assessment_requirements, request_id=request_id,
        )

    @server.tool()
    @_guard
    def get_learning_goal(session_id: str) -> dict:
        """Return the most recently saved learning goal for a session."""
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
        """Apply a learner's requested learning mode (section 32).

        Pass the learner's own words in `request` - e.g. "以项目实战为主",
        "我要准备考试", "只学核心内容，尽快学会". Recognised modes are
        project_based / exam_prep / core_only / balanced. Stored as
        session-level Learning Configuration + Policy Overrides; the program is
        never modified, and unrecognised requests are reported back.
        """
        return get_service().set_learning_configuration(
            session_id, request=request, mode=mode, overrides=overrides, request_id=request_id
        )

    @server.tool()
    @_guard
    def get_learning_configuration(session_id: str) -> dict:
        """Return the session's active learning mode, overrides and preferences."""
        return get_service().get_learning_configuration(session_id)

    # -- 22.2 Diagnostic ----------------------------------------------------
    @server.tool()
    @_guard
    def generate_diagnostic(session_id: str, request_id: str | None = None) -> dict:
        """Return a diagnostic blueprint.

        Rejected by the State Guard until Domain Grounding is completed, unless
        the session was created with allow_skip_domain_grounding=true.
        """
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
        """Record one diagnostic answer as a learner attempt."""
        return get_service().submit_diagnostic(
            session_id, answer, item_id=item_id, node_id=node_id, question=question,
            hint_level=hint_level, response_time=response_time, request_id=request_id,
        )

    @server.tool()
    @_guard
    def get_diagnostic_result(session_id: str) -> dict:
        """Return the stored diagnostic summary plus every diagnostic attempt."""
        return get_service().get_diagnostic_result(session_id)

    @server.tool()
    @_guard
    def save_diagnostic_result(session_id: str, result: Any, request_id: str | None = None) -> dict:
        """Persist the diagnostic summary and mark the diagnostic phase complete."""
        return get_service().save_diagnostic_result(session_id, result, request_id=request_id)

    # -- 22.3 Knowledge -----------------------------------------------------
    @server.tool()
    @_guard
    def decompose_topic(session_id: str, topic: str | None = None) -> dict:
        """Return a DAG template. Node content is generated by the host agent's LLM."""
        return get_service().decompose_topic(session_id, topic)

    @server.tool()
    @_guard
    def save_knowledge_nodes(
        session_id: str, nodes: list[dict], request_id: str | None = None
    ) -> dict:
        """Persist knowledge nodes. Each unit_tag must respect unit_concept_budget."""
        return get_service().save_knowledge_nodes(session_id, nodes, request_id=request_id)

    @server.tool()
    @_guard
    def save_knowledge_edges(
        session_id: str, edges: list[dict], request_id: str | None = None
    ) -> dict:
        """Persist knowledge edges. The DAG is validated first and rejected if invalid."""
        return get_service().save_knowledge_edges(session_id, edges, request_id=request_id)

    @server.tool()
    @_guard
    def get_knowledge_nodes(session_id: str, unit_tag: str | None = None) -> dict:
        """List knowledge nodes, optionally filtered by teaching unit."""
        return get_service().get_knowledge_nodes(session_id, unit_tag)

    @server.tool()
    @_guard
    def get_knowledge_edges(session_id: str) -> dict:
        """List knowledge edges (prerequisite / support / extension / related)."""
        return get_service().get_knowledge_edges(session_id)

    @server.tool()
    @_guard
    def validate_knowledge_dag(session_id: str) -> dict:
        """Validate the stored DAG: cycles, dangling edges, self-loops, isolated nodes."""
        return get_service().validate_knowledge_dag(session_id)

    # -- 22.4 Teaching context ---------------------------------------------
    @server.tool()
    @_guard
    def get_teaching_context(session_id: str, node_id: str | None = None) -> dict:
        """Return the full teaching context in one call to reduce round trips."""
        return get_service().get_teaching_context(session_id, node_id)

    # -- 22.5 Pedagogical policy -------------------------------------------
    @server.tool()
    @_guard
    def get_available_strategies() -> dict:
        """List the pedagogical strategies available to the policy engine."""
        return get_service().get_available_strategies()

    @server.tool()
    @_guard
    def get_available_actions() -> dict:
        """List the concrete teaching actions the host agent may execute."""
        return get_service().get_available_actions()

    @server.tool()
    @_guard
    def get_plugin_info() -> dict:
        """Report which implementation backs each pluggable seam (section 35).

        Covers state estimation, assessment aggregation, policy, review
        scheduling, storage and artifact storage.
        """
        return get_service().get_plugin_info()

    @server.tool()
    @_guard
    def evaluate_pedagogical_policy(
        session_id: str, node_id: str | None = None, trigger_event: str | None = None
    ) -> dict:
        """Evaluate the policy for the current state without persisting a decision."""
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
        """Record the decision actually acted on, for later replay."""
        return get_service().commit_pedagogical_decision(
            session_id, selected_strategy, selected_action, node_id=node_id,
            trigger_event=trigger_event, rationale=rationale,
            expected_outcome=expected_outcome, request_id=request_id,
        )

    @server.tool()
    @_guard
    def get_decision_log(session_id: str, limit: int = 50) -> dict:
        """Read the pedagogical decision history for a session."""
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
        """Return an assessment blueprint with the rubric dimensions to score."""
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
        """Validate dimension scores and compute the weighted overall_score.

        Does not persist anything. transfer and hint_dependency are excluded
        from the aggregate by design.
        """
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
        """Record an active misconception in its authoritative table."""
        return get_service().assess_misconception(
            learner_id, node_id, misconception, severity=severity,
            session_id=session_id, request_id=request_id,
        )

    @server.tool()
    @_guard
    def resolve_misconception(misconception_id: int, session_id: str | None = None) -> dict:
        """Mark a misconception as resolved and refresh the cached snapshot."""
        return get_service().resolve_misconception(misconception_id, session_id=session_id)

    @server.tool()
    @_guard
    def get_mastery_status(session_id: str, node_id: str | None = None) -> dict:
        """Return the server-estimated learner knowledge state."""
        return get_service().get_mastery_status(session_id, node_id)

    @server.tool()
    @_guard
    def get_assessment_history(
        session_id: str, node_id: str | None = None, limit: int = 50
    ) -> dict:
        """Return past assessment results, including the raw answer for audit."""
        return get_service().get_assessment_history(session_id, node_id, limit)

    @server.tool()
    @_guard
    def generate_transfer_probe(session_id: str, node_id: str | None = None) -> dict:
        """Return a transfer-probe blueprint (near / variation / far / integrated)."""
        return get_service().generate_transfer_probe(session_id, node_id)

    # -- 22.7 Retention -----------------------------------------------------
    @server.tool()
    @_guard
    def get_review_state(learner_id: str, node_id: str | None = None) -> dict:
        """Return review items with current retrievability and due status."""
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
        """Create a review item for a node if one does not exist yet."""
        return get_service().schedule_review(
            learner_id, node_id, session_id=session_id, item_ref=item_ref, request_id=request_id
        )

    @server.tool()
    @_guard
    def submit_review(
        review_item_id: str, rating: int, session_id: str | None = None, request_id: str | None = None
    ) -> dict:
        """Submit an FSRS rating (1=Again, 2=Hard, 3=Good, 4=Easy) and reschedule."""
        return get_service().submit_review(
            review_item_id, rating, session_id=session_id, request_id=request_id
        )

    @server.tool()
    @_guard
    def get_due_reviews(learner_id: str, limit: int = 50, session_id: str | None = None) -> dict:
        """List due review items.

        A non-empty result does not block new learning globally - blocking is a
        per-node Policy + State Guard decision.
        """
        return get_service().get_due_reviews(learner_id, limit=limit, session_id=session_id)

    @server.tool()
    @_guard
    def recalculate_review_schedule(learner_id: str, now: int | None = None) -> dict:
        """Recompute retrievability for every review item of a learner."""
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
        """Set the current teaching focus to a unit or node."""
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
        """Dry-run the State Guard for an advance request without changing state."""
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
        """Record a learner attempt and return its attempt_id for assessment."""
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
        """Commit assessment evidence and update learner state server-side.

        raw_answer and assessor_type are mandatory: the original learner
        response is stored for audit and never discarded. mastery_probability is
        computed by the runtime, not supplied by the caller.
        """
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
        """Request the next unit.

        Every node sharing the unit_tag must pass its own node-level guard;
        one failure rejects the whole request. There is no unit table.
        """
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
        """Move the teaching focus back to an earlier node."""
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
        """Record a transfer probe result; transfer_type is near/variation/far/integrated."""
        return get_service().record_transfer_result(
            learner_id, node_id, transfer_type, score, task_context=task_context,
            result=result, session_id=session_id, request_id=request_id,
        )

    @server.tool()
    @_guard
    def record_reflection(
        session_id: str, reflection: Any, node_id: str | None = None, request_id: str | None = None
    ) -> dict:
        """Store a learner reflection as an artifact."""
        return get_service().record_reflection(
            session_id, reflection, node_id=node_id, request_id=request_id
        )

    @server.tool()
    @_guard
    def complete_session(
        session_id: str, status: str = "completed", request_id: str | None = None
    ) -> dict:
        """Set the session status (active/paused/completed/abandoned)."""
        return get_service().complete_session(session_id, status=status, request_id=request_id)

    # -- 22.9 Evidence / Grounding -----------------------------------------
    @server.tool()
    @_guard
    def save_benchmark_report(
        session_id: str,
        report_text: str,
        source_refs: list[dict] | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Save the agent's domain grounding report and unlock diagnostics.

        The full text is stored as an artifact of type agent_benchmark_report;
        structured claims go to benchmark_claims.
        """
        return get_service().save_benchmark_report(
            session_id, report_text, source_refs=source_refs, request_id=request_id
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
        """Save one structured knowledge claim with its source and confidence."""
        return get_service().save_benchmark_claim(
            session_id, claim, source_id=source_id, confidence=confidence,
            knowledge_scope=knowledge_scope, conflicting_sources=conflicting_sources,
            request_id=request_id,
        )

    @server.tool()
    @_guard
    def get_evidence(session_id: str, node_id: str | None = None) -> dict:
        """Return grounding report metadata, claims and sources for a session."""
        return get_service().get_evidence(session_id, node_id)

    @server.tool()
    @_guard
    def validate_claim(claim_id: str, verified: bool = True) -> dict:
        """Check whether a claim is linked to a real evidence source."""
        return get_service().validate_claim(claim_id, verified=verified)

    @server.tool()
    @_guard
    def record_source_conflict(
        claim_id: str, conflicting_sources: Any, uncertainty: str | None = None
    ) -> dict:
        """Record conflicting sources instead of silently choosing one."""
        return get_service().record_source_conflict(
            claim_id, conflicting_sources, uncertainty=uncertainty
        )

    # -- 22.10 Artifact -----------------------------------------------------
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
        """Save a learning artefact (HTML, Markdown, chart, code, report...)."""
        return get_service().save_artifact(
            learner_id, session_id, artifact_type, path_or_uri=path_or_uri,
            content=content, metadata=metadata, version=version, request_id=request_id,
        )

    @server.tool()
    @_guard
    def get_artifact(artifact_id: str, include_content: bool = True) -> dict:
        """Fetch an artefact by id."""
        return get_service().get_artifact(artifact_id, include_content=include_content)

    @server.tool()
    @_guard
    def list_artifacts(session_id: str, artifact_type: str | None = None) -> dict:
        """List artefacts for a session, optionally filtered by type."""
        return get_service().list_artifacts(session_id, artifact_type)

    @server.tool()
    @_guard
    def get_obsidian_structure() -> dict:
        """Return the static Obsidian vault specification.

        Specification only - the runtime never reads or writes local vault files.
        """
        return get_service().get_obsidian_structure()

    @server.tool()
    @_guard
    def get_web_component_spec() -> dict:
        """Return the static web-component specification.

        Specification only - the runtime never generates HTML or reads front-end sources.
        """
        return get_service().get_web_component_spec()

    @server.tool()
    @_guard
    def export_session_data(session_id: str, output_path: str | None = None) -> dict:
        """Export the full session bundle as JSON, optionally to a file path."""
        return get_service().export_session_data(session_id, output_path=output_path)

    @server.tool()
    @_guard
    def generate_final_report(session_id: str, save_as_artifact: bool = True) -> dict:
        """Generate the closing report, separating observed evidence from estimates."""
        return get_service().generate_final_report(session_id, save_as_artifact=save_as_artifact)

    @server.tool()
    @_guard
    def get_learning_metrics(session_id: str) -> dict:
        """Return the section 26.1 learning-outcome indicators.

        Covers Immediate Performance, Delayed Retention, Transfer Performance,
        Time/Attempts to Target Evidence, Hint Dependency, Misconception
        Resolution, Confidence Calibration and Learning Gain.
        """
        return get_service().get_learning_metrics(session_id)

    return server


server = build_server()


def main() -> None:
    """Entry point: run the MCP server over stdio."""
    logging.basicConfig(
        level=os.environ.get("LEAP_LOG_LEVEL", "INFO").upper(),
        stream=sys.stderr,  # stdout is reserved for the MCP protocol
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    transport = os.environ.get("LEAP_MCP_TRANSPORT", "stdio")
    if transport != "stdio":
        logger.warning(
            "P0 supports stdio only; requested transport %r. Falling back to stdio.", transport
        )
    get_service()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
