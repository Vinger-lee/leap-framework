"""Skill workflow contracts over real stdio, using synthetic teaching evidence.

These tests exercise runtime behavior over the MCP transport: the coarse teaching
loop, the post-notice Domain Grounding decision, split assessment recovery,
misconception recording/resolution, spaced review, transfer, reflection, and the
closed-session contract. They do not test host skill activation or semantic
answer quality.
"""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from leap.tools.facade import LIFECYCLE_NEXT_CALL
from tests.teaching_fixture import teaching_pair


#: Explicit post-creation Domain Grounding decision (both profiles).
SKIP_TOOL = "set_domain_grounding_skip"


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["full", "quickstart"])
async def test_learning_recovery_and_closure_over_stdio(tmp_path, profile):
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "skill.sqlite"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(root / "tests" / "fixture_mcp_server.py"), "--tool-profile", profile],
        env={**os.environ, "LEAP__DATABASE_PATH": str(database), "PYTHONPATH": str(root / "src")},
    )
    async with asyncio.timeout(120), stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            catalog_tools = (await session.list_tools()).tools
            catalog = {tool.name for tool in catalog_tools}
            schemas = {
                tool.name: tool.model_dump(by_alias=True)["inputSchema"] for tool in catalog_tools
            }

            async def call(name, arguments, *, error=None):
                assert name in catalog, f"{profile} hides the next required call: {name}"
                result = await session.call_tool(name, arguments)
                assert not result.is_error, result
                data = result.structured_content or json.loads(
                    next(c.text for c in result.content if c.type == "text"))
                # Every response carries the compact policy receipt, never the full policy.
                assert data["policy_version"], data
                compact = data.get("teaching_delivery_policy") or {}
                assert set(compact) == {"policy_id", "version", "mandatory"}, compact
                assert len(json.dumps(compact, ensure_ascii=False)) < 200, compact
                if error:
                    assert data["ok"] is False and data["error"]["code"] == error, data
                    assert isinstance(data["error"]["retryable"], bool), data["error"]
                else:
                    assert data["ok"] is True, data
                check_next(data)
                return data

            def rows(query, parameters=()):
                # Test-only audit of the isolated database, never part of the skill.
                with sqlite3.connect(database) as connection:
                    return connection.execute(query, parameters).fetchall()

            def check_next(response):
                next_call = response.get("next_call")
                if not next_call:
                    return None
                tool = next_call.get("tool")
                if tool is None:
                    assert next_call.get("session_closed") is True, next_call
                    return next_call
                assert tool in catalog, f"{profile} next_call target missing: {tool}"
                assert set(next_call.get("follow_up", []) or []) <= catalog
                if "then" in next_call:
                    assert next_call["then"] in catalog
                arguments = next_call.get("arguments") or {}
                properties = schemas[tool].get("properties", {})
                unknown = sorted(set(arguments) - set(properties))
                assert not unknown, (tool, unknown, properties)
                return next_call

            for step in LIFECYCLE_NEXT_CALL.values():
                if step.get("tool") is not None:
                    assert step["tool"] in catalog
                assert set(step.get("follow_up", []) or []) <= catalog
                if step.get("then"):
                    assert step["then"] in catalog

            # --- session + post-notice skip decision -----------------------
            started = await call("start_learning", {
                "learner_id": "skill-fixture", "topic": "Synthetic equation",
                "goal": "Solve one equation"})
            sid = started["session_id"]
            assert started["domain_grounding_notice"]
            assert started["next_call"]["tool"] == "save_benchmark_report"
            resumed = await call("start_learning", {
                "learner_id": "skill-fixture", "topic": "Synthetic equation"})
            assert resumed["session_id"] == sid
            assert resumed["existing_session"] is True

            skipped = await call("start_learning", {
                "learner_id": "skip-fixture", "topic": "Skip probe"})
            skip_sid = skipped["session_id"]
            assert skipped["domain_grounding_notice"]
            recorded = await call(SKIP_TOOL, {
                "session_id": skip_sid, "allow_skip": True,
                "reason": "Synthetic learner chose to skip after the notice"})
            assert recorded["allow_skip_domain_grounding"] is True
            assert recorded["previous_allow_skip_domain_grounding"] is False
            # The gate is waived on the existing session: no second session needed.
            await call("generate_diagnostic", {"session_id": skip_sid})
            skip_snapshot = await call("get_learner_snapshot", {"session_id": skip_sid})
            assert skip_snapshot["session_status"] == "active"
            assert rows("SELECT allow_skip_domain_grounding FROM learning_sessions "
                        "WHERE session_id=?", (skip_sid,)) == [(1,)]
            assert len(rows("SELECT session_id FROM learning_sessions")) == 2

            # --- domain grounding + DAG + package + items ------------------
            await call("generate_diagnostic", {"session_id": sid}, error="domain_grounding_required")
            pending = await call("save_benchmark_report", {
                "session_id": sid, "report_text": "Synthetic evidence incomplete"})
            assert pending["domain_grounding_stage"] == "pending"
            assert pending["missing_evidence"]
            grounded = await call("save_benchmark_report", {
                "session_id": sid,
                "report_text": "Synthetic equation fixture; not real source reading.",
                "source_refs": [{"source": "test fixture", "source_type": "test_fixture",
                                 "locator": "equation", "excerpt": "3x+5=20 has solution x=5"}],
                "verification": {
                    "scope": "Controlled equation only",
                    "claims": [{"claim": "x=5", "source_index": 0}],
                    "worked_examples": [{
                        "problem": "3x+5=20", "solution": "x=5", "check_method": "substitution",
                        "check_result": "3*5+5=20"}],
                    "limitations": ["Synthetic test; does not verify subject correctness"]}})
            assert grounded["domain_grounding_stage"] == "completed"
            # A later incomplete report must not downgrade the completed gate.
            later = await call("save_benchmark_report", {
                "session_id": sid, "report_text": "Additional incomplete note"})
            assert later["domain_grounding_stage"] == "completed", later
            await call("get_learner_snapshot", {"session_id": sid})
            await call("save_knowledge_nodes", {"session_id": sid, "nodes": [
                {"node_id": "eq", "title": "Equation fixture", "unit_tag": "equations"}]})
            await call("save_knowledge_edges", {
                "session_id": sid,
                "edges": [{"pre_node_id": "eq", "post_node_id": "missing",
                           "relation_type": "prerequisite"}]},
                error="invalid_knowledge_dag")
            await call("save_knowledge_nodes", {"session_id": sid, "nodes": [
                {"node_id": "missing", "title": "Second fixture", "unit_tag": "equations"}]})
            await call("save_knowledge_edges", {"session_id": sid, "edges": [
                {"pre_node_id": "eq", "post_node_id": "missing",
                 "relation_type": "prerequisite"}]})
            await call("validate_knowledge_dag", {"session_id": sid})
            md, html, manifest = teaching_pair()
            manifest["source_ids"] = grounded["sources_saved"]
            package_args = {"session_id": sid, "node_id": "eq", "subject": "math",
                            "markdown": md, "html": html, "manifest": manifest}
            await call("save_teaching_package", {**package_args, "markdown": "incomplete"},
                       error="teaching_package_incomplete")
            package = await call("save_teaching_package", package_args)
            assert package["validation"]["content_verified_by_runtime"] is False
            item_id = "eq.v1"
            await call("save_assessment_item", {
                "session_id": sid, "item_id": item_id, "node_id": "eq",
                "question": "Explain 3x+5=20", "expected_answer": "x=5 with valid reasoning",
                "solution": "Subtract 5, then divide by 3", "assumptions": ["x is real"],
                "verification_checks": [{"method": "substitution", "result": "3*5+5=20"}],
                "assessor_scope": "host_semantic_review",
                "teaching_package_id": package["package_id"],
                "source_ids": grounded["sources_saved"]})

            # --- diagnostic completes and next_step moves to unit start ----
            await call("generate_diagnostic", {"session_id": sid})
            await call("submit_diagnostic", {"session_id": sid, "answer": "x=5", "item_id": item_id})
            await call("save_diagnostic_result", {
                "session_id": sid, "result": {"observed": "can solve one-step equations"}})
            after_diag = await call("get_learner_snapshot", {"session_id": sid})
            assert after_diag["next_step"] == "unit_start", after_diag["next_step"]
            assert after_diag["next_call"]["tool"] == "start_unit"

            # --- teaching loop -------------------------------------------
            await call("start_unit", {"session_id": sid, "node_id": "eq"})
            lesson = await call("continue_lesson", {"session_id": sid, "node_id": "eq"})
            assert lesson["teaching_context_omitted"] is True
            assert "teaching_context" not in lesson
            verbose = await call("continue_lesson", {"session_id": sid, "node_id": "eq",
                                                     "verbose": True})
            assert "teaching_context" in verbose
            context_lean = await call("get_teaching_context", {"session_id": sid,
                                                              "node_id": "eq"})
            assert "teaching_point_template" not in json.dumps(context_lean, ensure_ascii=False)
            context_full = await call("get_teaching_context", {
                "session_id": sid, "node_id": "eq", "include_template": True})
            assert "teaching_point_template" in context_full
            log_next = lesson["next_call"]
            assert log_next["tool"] == "log_teaching_action"
            allowed_actions = log_next.get("allowed_actions") or []
            assert allowed_actions
            await call("log_teaching_action", {
                "session_id": sid, "action": allowed_actions[0], "node_id": "eq"})
            bad_action = await call("log_teaching_action", {
                "session_id": sid, "action": "Not A Real Action"}, error="invalid_action")
            assert bad_action["error"]["details"]["allowed_actions"]

            answer = "  Subtract 5; 3x=15.\nDivide by 3: x=5.  "
            deferred = await call("submit_answer", {
                "session_id": sid, "node_id": "eq", "item_id": item_id, "answer": answer})
            assert deferred["assessed"] is False
            commit_next = deferred["next_call"]
            assert commit_next["tool"] == "commit_assessment"
            assert commit_next["arguments"]["raw_answer"] == answer
            await call(commit_next["tool"], {**commit_next["arguments"], "correctness": 1,
                                             "assessor_type": "rule"},
                       error="semantic_review_required")
            await call(commit_next["tool"], {**commit_next["arguments"], "correctness": 1,
                                             "reasoning_quality": 0.9,
                                             "assessor_type": "model"})
            partial_args = {
                "session_id": sid, "node_id": "eq", "item_id": item_id,
                "answer": "second pass", "correctness": 2.5, "request_id": "partial-skill-retry",
            }
            failed = await call("submit_answer", partial_args, error="invalid_score")
            replayed = await call("submit_answer", partial_args, error="invalid_score")
            assert replayed["idempotent_replay"] is True
            details = failed["error"]["details"]
            assert replayed["error"]["details"]["attempt_id"] == details["attempt_id"]
            assert details["failed_step"] == "commit_assessment"
            recovered = await call(details["failed_step"], {
                "attempt_id": details["attempt_id"], "raw_answer": "second pass",
                "correctness": 0.9})
            assert recovered["attempt_id"] == details["attempt_id"]
            stored_answers = [row[0] for row in rows(
                "SELECT answer FROM learning_attempts WHERE session_id=?", (sid,))]
            assert answer in stored_answers
            assert stored_answers.count("second pass") == 1

            # --- misconception: record in this profile, then resolve -------
            misconception = await call("assess_misconception", {
                "learner_id": "skill-fixture", "node_id": "eq", "session_id": sid,
                "misconception": "Subtracting from one side only"})
            mis_lesson = await call("continue_lesson", {"session_id": sid, "node_id": "eq"})
            assert mis_lesson["next_call"]["tool"] == "resolve_misconception"
            resolved = await call("resolve_misconception", {
                "misconception_id": misconception["misconception_id"], "session_id": sid})
            assert resolved["status"] == "resolved"
            after_resolve = await call("get_learner_snapshot", {"session_id": sid})
            assert after_resolve["next_call"]["tool"] != "resolve_misconception"

            # --- advance (guard decides) ----------------------------------
            refusal = await call("advance_lesson", {"session_id": sid, "unit_tag": "equations"})
            assert refusal["advanced"] is False and refusal["remediation"]

            # --- transfer + reflection ------------------------------------
            probe = await call("generate_transfer_probe", {"session_id": sid, "node_id": "eq"})
            assert "transfer_required" in probe
            await call("record_transfer_result", {
                "learner_id": "skill-fixture", "node_id": "eq", "transfer_type": "near",
                "score": 0.8, "session_id": sid, "result": "synthetic transfer"})
            await call("record_reflection", {
                "session_id": sid, "reflection": "Synthetic learner reflection"})

            # --- due review: next_call must carry session_id + real rating --
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "INSERT INTO review_items (review_item_id, learner_id, node_id, item_ref, "
                    "stability, difficulty, retrievability, last_review_at, next_review_at, "
                    "review_count, last_rating, scheduler_version, created_at, updated_at) "
                    "VALUES ('rev_skill','skill-fixture','eq',NULL,2.0,5.0,0.9,NULL,1,0,NULL,"
                    "'fsrs-6',0,0)")
                connection.commit()
            queue = await call("get_review_queue", {"learner_id": "skill-fixture",
                                                   "session_id": sid})
            assert queue["count"] >= 1
            review_next = queue["next_call"]
            assert review_next["tool"] == "review_answer"
            assert review_next["allowed_ratings"] == [1, 2, 3, 4]
            assert review_next["required_arguments"] == ["rating"]
            review_args = dict(review_next["arguments"])
            assert review_args["review_item_id"] == "rev_skill"
            assert review_args["session_id"] == sid
            # No score may be prefilled: the host must supply the observed recall.
            assert "rating" not in review_args
            review_args["rating"] = 3
            reviewed = await call("review_answer", review_args)
            assert reviewed["rating"] == 3
            snapshot = await call("get_learner_snapshot", {"session_id": sid})
            state = next(s for s in snapshot["node_states"] if s["node_id"] == "eq")
            assert state["evidence_stage"] != "estimated", state

            # --- closure: report required, idempotent, closed rejects teaching
            forced = await call("start_learning", {
                "learner_id": "skill-fixture", "topic": "Synthetic equation",
                "force_new": True})
            assert forced["session_id"] != sid
            assert forced["existing_session"] is False
            early = await call("start_learning", {"learner_id": "close-fixture",
                                                 "topic": "Close probe"})
            await call("complete_session", {"session_id": early["session_id"]},
                       error="final_report_required")
            report = await call("generate_final_report", {"session_id": sid})
            assert report["artifact_id"]
            closed = await call("complete_session", {"session_id": sid})
            assert closed["status"] == "completed"
            again = await call("complete_session", {"session_id": sid})
            assert again["already_applied"] is True
            assert rows("SELECT COUNT(*) FROM event_log WHERE event_type='session_completed' "
                        "AND session_id=?", (sid,)) == [(1,)]
            closed_snapshot = await call("get_learner_snapshot", {"session_id": sid})
            assert closed_snapshot["session_status"] == "completed"
            assert closed_snapshot["session_closed"] is True
            assert closed_snapshot["next_call"] is None
            await call("continue_lesson", {"session_id": sid}, error="session_closed")
            await call("submit_answer", {"session_id": sid, "answer": "too late"},
                       error="session_closed")
            reopened = await call("complete_session", {"session_id": sid,
                                                      "status": "active", "reopen": True})
            assert reopened["status"] == "active"
            reopened_snapshot = await call("get_learner_snapshot", {"session_id": sid})
            assert reopened_snapshot["session_status"] == "active"
            assert reopened_snapshot["next_call"] is not None
            # skill + skip + forced + close-probe sessions
            assert len(rows("SELECT session_id FROM learning_sessions")) == 4


@pytest.mark.asyncio
async def test_quickstart_and_full_expose_the_skill_loop_tools():
    root = Path(__file__).resolve().parents[1]

    async def catalog(profile):
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "leap.server", "--tool-profile", profile],
            env={**os.environ, "LEAP__TOOL_PROFILE": profile,
               "LEAP__DATABASE_PATH": str(Path(os.environ.get("TMP", "/tmp")) / f"leap-{profile}.sqlite"),
               "PYTHONPATH": str(root / "src")},
        )
        async with asyncio.timeout(45), stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return {tool.name for tool in (await session.list_tools()).tools}

    quickstart = await catalog("quickstart")
    full = await catalog("full")
    required = {
        "start_learning", "continue_lesson", "log_teaching_action", "submit_answer",
        "advance_lesson", "get_review_queue", "review_answer", "get_learner_snapshot",
        "get_grounding_sources", "save_benchmark_report", "get_teaching_delivery_policy", "get_subject_catalog",
        "decompose_topic", "save_knowledge_nodes", "save_knowledge_edges",
        "validate_knowledge_dag", "save_teaching_package", "save_assessment_item",
        "generate_diagnostic", "submit_diagnostic", "save_diagnostic_result", "start_unit",
        "generate_transfer_probe", "record_transfer_result", "record_reflection",
        "generate_final_report", "complete_session", "commit_assessment", "resolve_misconception",
        "assess_misconception", "find_session", SKIP_TOOL,
    }
    assert required <= quickstart, sorted(required - quickstart)
    assert required <= full, sorted(required - full)
    assert quickstart < full
    assert (len(full), len(quickstart)) == (75, 36)
    assert "get_teaching_context" in quickstart
