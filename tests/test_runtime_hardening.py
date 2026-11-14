"""Regression tests for the 2026-11-08 runtime hardening pass.

Each test pins one finding from ``.leap-review/runtime.md``:

* P0 parallel tool calls must not corrupt the shared SQLite connection.
* P1 retry safety: duplicate commit, request_id replay, optimistic lock.
* P1 "guided next_call must not damage state": transfer/review without a
  session, grounding downgrade, learning-gain baseline.
* P1/P2 guard reachability, advance semantics, closed sessions, envelopes.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest

from leap.runtime.bkt import BKTEstimator, BKTParams
from leap.runtime.learning_modes import resolve_mode
from leap.runtime.metrics import diagnostic_split
from leap.runtime.state_guard import effective_config, transfer_required
from leap.storage import Database, now_ts
from leap.tools import LeapService, ToolError, build_service

REFS = [
    {
        "source": "runtime hardening fixture",
        "source_type": "test_fixture",
        "locator": "fixture ch.1",
        "excerpt": "3x+5=20 has solution x=5",
    }
]
VERIFICATION = {
    "scope": "single linear equation fixture",
    "claims": [{"claim": "solution is x=5", "source_index": 0}],
    "worked_examples": [
        {"problem": "3x+5=20", "solution": "x=5", "check_method": "substitution",
         "check_result": "3*5+5=20"}
    ],
    "limitations": ["synthetic fixture; not a real source reading"],
}


def _grounded(service: LeapService, learner: str = "hardening-learner", topic: str = "hardening"):
    session = service.create_session(learner, topic)
    session_id = session["session_id"]
    service.save_benchmark_report(
        session_id, "# baseline", source_refs=REFS, verification=VERIFICATION
    )
    return session_id


def _nodes(service: LeapService, session_id: str, nodes: list[dict], edges: list[dict] | None = None):
    service.save_knowledge_nodes(session_id, nodes)
    if edges:
        service.save_knowledge_edges(session_id, edges)


def _commit(service: LeapService, session_id: str, node_id: str, score: float = 0.9, **kwargs):
    answer = f"answer {time.time_ns()}"
    attempt = service.submit_attempt(session_id, answer, node_id=node_id)
    return service.commit_assessment(
        attempt["attempt_id"], answer, correctness=score, reasoning_quality=0.9,
        application=0.9, conceptual_understanding=0.9, **kwargs,
    )


# ---------------------------------------------------------------------------
# P0 - parallel tool calls
# ---------------------------------------------------------------------------
class TestParallelWrites:
    def test_parallel_submit_answer_rows_are_all_recorded_once(self):
        service = build_service(":memory:")
        session_id = _grounded(service)
        _nodes(service, session_id, [{"node_id": "par.n1", "title": "t", "unit_tag": "u1"}])
        barrier = threading.Barrier(9)
        errors: list[str] = []

        def worker(index: int):
            barrier.wait()
            try:
                service.submit_answer(
                    session_id, f"parallel answer {index}", node_id="par.n1", correctness=0.9
                )
            except Exception as exc:  # noqa: BLE001 - surfaced by the assertion below
                errors.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        assert errors == []
        attempts = service.db.query(
            "SELECT attempt_index FROM learning_attempts WHERE session_id = ? ORDER BY attempt_index",
            (session_id,),
        )
        assert [row["attempt_index"] for row in attempts] == [1, 2, 3, 4, 5, 6, 7, 8]
        service.close()

    def test_database_rejects_duplicate_attempt_index(self):
        db = Database(":memory:").initialize()
        db.execute(
            "INSERT INTO learners (learner_id, name, created_at, updated_at) VALUES ('l','l',1,1)"
        )
        db.execute(
            "INSERT INTO learning_sessions (session_id, learner_id, topic, status, state_version, "
            "domain_grounding_stage, created_at, updated_at) "
            "VALUES ('s','l','t','active',1,'pending',1,1)"
        )
        row = ("a1", "s", "n", "answer", 0, 1, 1)
        db.execute(
            "INSERT INTO learning_attempts (attempt_id, session_id, node_id, answer, hint_level, "
            "attempt_index, created_at) VALUES (?,?,?,?,?,?,?)",
            row,
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO learning_attempts (attempt_id, session_id, node_id, answer, hint_level, "
                "attempt_index, created_at) VALUES (?,?,?,?,?,?,?)",
                ("a2", "s", "n", "answer2", 0, 1, 1),
            )
        db.close()

    def test_parallel_reads_do_not_raise_on_the_shared_connection(self):
        service = build_service(":memory:")
        session_id = _grounded(service)
        errors: list[str] = []
        barrier = threading.Barrier(9)

        def worker():
            barrier.wait()
            try:
                service.get_learner_snapshot(session_id)
                service.get_session_info(session_id)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        service.close()
        assert errors == []


# ---------------------------------------------------------------------------
# P1 - retry safety
# ---------------------------------------------------------------------------
class TestRetrySafety:
    def test_duplicate_commit_returns_the_existing_result(self, dag, grounded_service):
        attempt = grounded_service.submit_attempt(dag, "same answer", node_id="n2")
        first = grounded_service.commit_assessment(
            attempt["attempt_id"], "same answer", correctness=1.0, reasoning_quality=0.9
        )
        second = grounded_service.commit_assessment(
            attempt["attempt_id"], "same answer", correctness=0.1
        )
        assert second["already_assessed"] is True
        assert second["result_id"] == first["result_id"]
        assert grounded_service.db.scalar(
            "SELECT COUNT(*) FROM assessment_results WHERE attempt_id = ?", (attempt["attempt_id"],)
        ) == 1
        # A replay must not move the learner state again.
        state = grounded_service.get_mastery_status(dag, "n2")["learner_state"]
        assert state["mastery_probability"] == pytest.approx(
            first["learner_state"]["mastery_probability"]
        )

    def test_evidence_counting_ignores_duplicate_results(self, grounded_service, dag):
        attempt = grounded_service.submit_attempt(dag, "answer", node_id="n2")
        grounded_service.commit_assessment(
            attempt["attempt_id"], "answer", correctness=0.9, reasoning_quality=0.9
        )
        evidence = grounded_service._evidence_input("learner-test", "n2", dag, 0.9, 0.0)
        assert evidence.valid_attempts == 1
        assert evidence.unassisted_successes == 1

    def test_expected_state_version_conflict_is_structured(self, tmp_path):
        database = tmp_path / "race.sqlite"
        service_a = build_service(str(database))
        service_b = build_service(str(database))
        session_id = _grounded(service_a, learner="race-learner", topic="race")
        _nodes(service_a, session_id, [{"node_id": "race.n1", "title": "t", "unit_tag": "u1"}])
        answers = ["answer A", "answer B"]
        attempts = [
            service_a.submit_attempt(session_id, answer, node_id="race.n1")["attempt_id"]
            for answer in answers
        ]
        version = int(
            service_a.db.scalar(
                "SELECT state_version FROM learning_sessions WHERE session_id = ?", (session_id,)
            )
        )
        barrier = threading.Barrier(3)
        results: dict[str, object] = {}

        def worker(name, service, attempt, answer):
            barrier.wait()
            try:
                results[name] = service.commit_assessment(
                    attempt, answer, correctness=1.0,
                    expected_state_version=version,
                )
            except ToolError as exc:
                results[name] = exc

        threads = [
            threading.Thread(target=worker, args=("A", service_a, attempts[0], answers[0])),
            threading.Thread(target=worker, args=("B", service_b, attempts[1], answers[1])),
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        service_b.close()
        service_a.close()

        failures = [value for value in results.values() if isinstance(value, ToolError)]
        successes = [value for value in results.values() if not isinstance(value, ToolError)]
        assert len(successes) == 1, results
        assert len(failures) == 1, results
        assert failures[0].code == "stale_state_version"
        assert failures[0].retryable is True

    def test_request_id_replay_returns_the_first_response(self, service, monkeypatch):
        import leap.server as server_module

        monkeypatch.setattr(server_module, "get_service", lambda: service)
        server = server_module.build_server("full")

        def call(arguments):
            async def exercise():
                response = await server.call_tool("create_session", arguments)
                return response.structured_content or json.loads(
                    next(block.text for block in response.content if block.type == "text")
                )

            return asyncio.run(exercise())

        arguments = {"learner_id": "replay-learner", "topic": "replay", "request_id": "fixed-rid"}
        first = call(arguments)
        second = call(arguments)
        assert first["ok"] is True
        assert second["ok"] is True
        assert second["idempotent_replay"] is True
        assert second["session_id"] == first["session_id"]
        assert service.find_session("replay-learner", "replay")["count"] == 1


    @pytest.mark.asyncio
    async def test_failed_receipt_write_rolls_back_the_tool(self, service, monkeypatch):
        import leap.server as server_module

        monkeypatch.setattr(server_module, "get_service", lambda: service)
        server = server_module.build_server("full")
        args = {"learner_id": "rollback", "topic": "retry", "request_id": "rollback-1"}

        def fail(*args, **kwargs):
            raise sqlite3.OperationalError("simulated receipt write failure")

        async def create():
            response = await server.call_tool("create_session", args)
            return response.structured_content or json.loads(
                next(block.text for block in response.content if block.type == "text")
            )

        with monkeypatch.context() as patch:
            patch.setattr(service.db, "remember_request", fail)
            assert (await create())["error"]["code"] == "database_error"
            assert service.find_session("rollback")["count"] == 0
        first = await create()
        assert first["ok"] is True
        assert (await create())["session_id"] == first["session_id"]


# ---------------------------------------------------------------------------
# P1 - guided next_call paths must not damage state
# ---------------------------------------------------------------------------
class TestGuidedPaths:
    def test_transfer_without_session_keeps_the_stage_and_infers_the_session(
        self, grounded_service, dag
    ):
        _commit(grounded_service, dag, "n2")
        before = grounded_service.get_mastery_status(dag, "n2")["learner_state"]["evidence_stage"]
        result = grounded_service.record_transfer_result(
            "learner-test", "n2", "near", 0.95
        )
        assert result["session_id"] == dag
        assert result["session_inferred"] is True
        after = grounded_service.get_mastery_status(dag, "n2")["learner_state"]["evidence_stage"]
        assert after == before
        assert after != "estimated"

    def test_review_without_session_keeps_the_stage(self, grounded_service, dag):
        _commit(grounded_service, dag, "n2")
        before = grounded_service.get_mastery_status(dag, "n2")["learner_state"]["evidence_stage"]
        scheduled = grounded_service.schedule_review("learner-test", "n2", session_id=dag)
        grounded_service.db.execute(
            "UPDATE review_items SET next_review_at = ? WHERE review_item_id = ?",
            (now_ts() - 60, scheduled["review_item_id"]),
        )
        answered = grounded_service.review_answer(scheduled["review_item_id"], 3)
        assert answered["session_id"] == dag
        after = grounded_service.get_mastery_status(dag, "n2")["learner_state"]["evidence_stage"]
        assert after != "estimated"
        assert after == before

    def test_review_queue_next_call_carries_the_session(self, grounded_service, dag):
        _commit(grounded_service, dag, "n2")
        scheduled = grounded_service.schedule_review("learner-test", "n2", session_id=dag)
        grounded_service.db.execute(
            "UPDATE review_items SET next_review_at = ? WHERE review_item_id = ?",
            (now_ts() - 60, scheduled["review_item_id"]),
        )
        queue = grounded_service.get_review_queue("learner-test", session_id=dag)
        next_call = queue["next_call"]
        assert next_call["arguments"]["session_id"] == dag
        assert next_call["allowed_ratings"] == [1, 2, 3, 4]
        # No placeholder rating: a forgetful host must not commit a fake recall.
        assert "rating" not in next_call["arguments"]
        assert next_call["required_arguments"] == ["rating"]

    def test_second_partial_report_cannot_reopen_grounding(self, grounded_service, session_id):
        result = grounded_service.save_benchmark_report(session_id, "follow-up note, prose only")
        assert result["domain_grounding_stage"] == "completed"
        assert result["stage_downgrade_guard"] is True
        assert result["stage_downgraded"] is False
        # The gate is still open.
        assert grounded_service.generate_diagnostic(session_id)["ok"] is True

    def test_learning_gain_uses_only_post_diagnostic_assessment_results(self):
        service = build_service(":memory:")
        session_id = _grounded(service)
        _nodes(service, session_id, [{"node_id": "g.n1", "title": "t", "unit_tag": "u1"}])
        # Documented stage 4: diagnostic answers are attempts, not assessments.
        for answer in ("diagnostic one", "diagnostic two"):
            service.submit_diagnostic(session_id, answer, node_id="g.n1")
        service.save_diagnostic_result(session_id, {"summary": "weak"})
        for _ in range(3):
            _commit(service, session_id, "g.n1", score=0.9)
        baseline, post, marker = diagnostic_split(service.db, session_id)
        assert marker is not None
        assert baseline == []
        assert len(post) == 3
        gain = service.get_learning_metrics(session_id)["learning_gain"]
        assert gain["baseline_points"] == 0
        assert gain["post_points"] == 3
        assert gain["absolute_gain"] is None
        service.close()


# ---------------------------------------------------------------------------
# P1 - the guard is not host-reachable
# ---------------------------------------------------------------------------
class TestGuardReachability:
    def test_manual_override_is_not_a_host_tool_argument(self):
        from leap.server import build_server, registered_tool_names

        names = registered_tool_names(build_server("full"))
        assert {"advance_lesson", "advance_unit", "check_advance_unit"} <= set(names)
        for method in (LeapService.advance_lesson, LeapService.advance_unit, LeapService.check_advance_unit):
            assert "manual_override" not in inspect.signature(method).parameters
        assert "manual_override" not in inspect.signature(LeapService.advance_lesson).parameters


# ---------------------------------------------------------------------------
# P2 - advance semantics, lifecycle guidance, session scoping
# ---------------------------------------------------------------------------
class TestAdvanceSemantics:
    def _session_with_two_units(self, service: LeapService) -> str:
        session_id = _grounded(service)
        _nodes(
            service,
            session_id,
            [
                {"node_id": "u1.b", "title": "b", "unit_tag": "u1", "bloom_level": "understand"},
                {"node_id": "u1.a", "title": "a", "unit_tag": "u1", "bloom_level": "understand"},
                {"node_id": "u2.only", "title": "c", "unit_tag": "u2", "bloom_level": "understand"},
            ],
            edges=[{"pre_node_id": "u1.a", "post_node_id": "u1.b", "relation_type": "prerequisite"}],
        )
        return session_id

    def test_start_unit_uses_dependency_order_not_node_id_sort(self):
        service = build_service(":memory:")
        session_id = self._session_with_two_units(service)
        result = service.start_unit(session_id, unit_tag="u1")
        assert result["current_node_id"] == "u1.a"
        service.close()

    def test_advance_moves_to_the_next_unit_and_reports_it(self, monkeypatch):
        from leap.runtime.state_guard import GuardDecision

        service = build_service(":memory:")
        session_id = self._session_with_two_units(service)
        service.start_unit(session_id, unit_tag="u1")
        monkeypatch.setattr(
            service.guard, "check_unit", lambda *args, **kwargs: GuardDecision.allow("test")
        )
        first = service.advance_lesson(session_id, unit_tag="u1")
        assert first["advanced"] is True
        assert first["next_unit_tag"] == "u2"
        assert first["has_next_unit"] is True
        assert first["next_node_id"] == "u2.only"
        assert first["next_call"]["tool"] == "continue_lesson"
        last = service.advance_lesson(session_id, unit_tag="u2")
        assert last["advanced"] is True
        assert last["has_next_unit"] is False
        assert last["next_node_id"] is None
        assert last["next_call"]["tool"] == "generate_final_report"
        service.close()

    def test_unit_advance_checks_version_under_the_write_transaction(self, tmp_path, monkeypatch):
        from leap.runtime.state_guard import GuardDecision

        database = tmp_path / "advance.sqlite"
        first = build_service(database)
        second = build_service(database)
        try:
            session_id = self._session_with_two_units(first)
            expected = first.get_session_info(session_id)["session"]["state_version"]
            entered = threading.Event()
            release = threading.Event()
            results = []

            def check(*args, expected_state_version, **kwargs):
                if first.get_session_info(session_id)["session"]["state_version"] != expected_state_version:
                    return GuardDecision.reject("stale state version")
                entered.set()
                assert release.wait(timeout=5)
                return GuardDecision.allow("test")

            monkeypatch.setattr(first.guard, "check_unit", check)
            monkeypatch.setattr(second.guard, "check_unit", check)

            def advance(service):
                results.append(service.advance_lesson(
                    session_id, unit_tag="u1", expected_state_version=expected,
                ))

            a = threading.Thread(target=advance, args=(first,))
            b = threading.Thread(target=advance, args=(second,))
            a.start()
            assert entered.wait(timeout=5)
            b.start()
            # A second connection cannot write while the first one is checking.
            probe = sqlite3.connect(database, timeout=0.05)
            try:
                with pytest.raises(sqlite3.OperationalError, match="locked"):
                    probe.execute(
                        "UPDATE learning_sessions SET updated_at=0 WHERE session_id=?", (session_id,)
                    )
            finally:
                probe.close()
                release.set()
                a.join(timeout=5)
                b.join(timeout=5)
            assert len(results) == 2
            assert sum(result["advanced"] for result in results) == 1
        finally:
            first.close()
            second.close()

    def test_next_step_after_diagnostic_points_to_start_unit(self):
        service = build_service(":memory:")
        session_id = _grounded(service)
        _nodes(service, session_id, [{"node_id": "d.n1", "title": "t", "unit_tag": "u1"}])
        assert service.get_session_info(session_id)["next_step"] == "diagnostic"
        service.save_diagnostic_result(session_id, {"summary": "done"})
        info = service.get_session_info(session_id)
        assert info["next_step"] == "unit_start"
        snapshot = service.get_learner_snapshot(session_id)
        assert snapshot["next_call"]["tool"] == "start_unit"
        service.close()

    def test_cross_session_node_ids_are_rejected(self):
        service = build_service(":memory:")
        session_a = _grounded(service, learner="a", topic="a")
        session_b = _grounded(service, learner="b", topic="b")
        _nodes(service, session_a, [{"node_id": "a.node", "title": "a", "unit_tag": "ua"}])
        _nodes(service, session_b, [{"node_id": "b.node", "title": "b", "unit_tag": "ub"}])
        for call in (
            lambda: service.get_teaching_context(session_a, "b.node"),
            lambda: service.start_unit(session_a, node_id="b.node"),
            lambda: service.rollback_unit(session_a, "b.node"),
            lambda: service.schedule_review("a", "b.node", session_id=session_a),
        ):
            with pytest.raises(ToolError) as excinfo:
                call()
            assert excinfo.value.code == "invalid_node"
        service.close()


# ---------------------------------------------------------------------------
# P2 - effective configuration, error mapping, envelopes
# ---------------------------------------------------------------------------
class TestEffectiveConfiguration:
    def test_learning_mode_overrides_reach_tools_and_guard(self):
        service = build_service(":memory:")
        session_id = _grounded(service)
        _nodes(
            service,
            session_id,
            [{"node_id": "mode.n1", "title": "t", "unit_tag": "u1", "bloom_level": "understand"}],
        )
        mode = service.set_learning_configuration(session_id, request="以项目实战为主")
        assert mode["mode"] == "project_based"
        assert service.effective_conf(session_id, "default_transfer_requirement") == "always"
        node = service.require_node("mode.n1")
        guard_cfg = effective_config(service.db, service.cfg, session_id)
        assert transfer_required(node, guard_cfg) is True
        assert service.policy._transfer_requirement(node, session_id) is True
        service.close()

    def test_exam_mode_narrows_the_hint_ceiling_in_submit_attempt(self):
        service = build_service(":memory:")
        session_id = _grounded(service)
        _nodes(service, session_id, [{"node_id": "hint.n1", "title": "t", "unit_tag": "u1"}])
        service.set_learning_configuration(session_id, request="我要准备考试")
        assert service.effective_conf(session_id, "max_hint_level") == 2
        with pytest.raises(ToolError) as excinfo:
            service.submit_attempt(session_id, "answer", node_id="hint.n1", hint_level=3)
        assert excinfo.value.code == "invalid_hint_level"
        service.close()

    def test_structural_failures_are_structured_not_internal(self):
        service = build_service(":memory:")
        session_a = _grounded(service, learner="a", topic="a")
        session_b = _grounded(service, learner="b", topic="b")
        _nodes(service, session_a, [{"node_id": "a.node", "title": "a", "unit_tag": "ua"}])
        _nodes(service, session_b, [{"node_id": "b.node", "title": "b", "unit_tag": "ub"}])
        with pytest.raises(ToolError) as foreign:
            service.submit_attempt(session_a, "answer", node_id="b.node")
        assert foreign.value.code == "invalid_node"
        assert service.db.scalar(
            "SELECT COUNT(*) FROM learning_attempts WHERE session_id = ?", (session_a,)
        ) == 0
        with pytest.raises(ToolError) as learner:
            service.record_transfer_result("not-the-owner", "a.node", "near", 0.9)
        assert learner.value.code == "invalid_learner"
        with pytest.raises(ToolError) as score:
            service.record_transfer_result("a", "a.node", "near", 99)
        assert score.value.code == "invalid_score"
        service.close()


class TestEnvelopeAndProfiles:
    def test_every_response_carries_only_a_compact_policy_receipt(self, service):
        response = service.create_session("envelope-learner", "envelope")
        policy = response["teaching_delivery_policy"]
        assert set(policy) == {"policy_id", "version", "mandatory"}
        assert response["policy_version"] == policy["version"]
        assert len(json.dumps(response, default=str)) < 1500

    def test_error_envelope_is_compact_and_retryable_is_explicit(self):
        payload = ToolError("unknown_session", "no such session").as_dict()
        assert payload["error"]["retryable"] is False
        assert set(payload["teaching_delivery_policy"]) == {"policy_id", "version", "mandatory"}

    def test_continue_lesson_is_summary_only_by_default(self, dag, grounded_service):
        summary = grounded_service.continue_lesson(dag, "n1")
        assert "teaching_context" not in summary
        assert summary["teaching_context_omitted"] is True
        assert summary["next_call"]["allowed_actions"]
        verbose = grounded_service.continue_lesson(dag, "n1", verbose=True)
        assert "teaching_context" in verbose

    def test_get_teaching_context_template_is_opt_in(self, dag, grounded_service):
        plain = grounded_service.get_teaching_context(dag, "n1")
        assert "teaching_point_template" not in plain
        full = grounded_service.get_teaching_context(dag, "n1", include_template=True)
        assert full["teaching_point_template"]

    def test_quickstart_exposes_the_grounding_decision_and_misconception_tools(self):
        from leap.server import build_server, registered_tool_names

        quickstart = set(registered_tool_names(build_server("quickstart")))
        for name in (
            "set_domain_grounding_skip",
            "assess_misconception",
            "find_session",
            "get_teaching_context",
        ):
            assert name in quickstart, name

    def test_unknown_seam_falls_back_with_a_warning(self, monkeypatch):
        import leap.server as server_module

        monkeypatch.setenv("LEAP__MASTERY_ESTIMATOR", "pfa-not-registered")
        cfg = server_module._effective_config()
        assert cfg.get("mastery_estimator") == "simplified_bkt"
        service = build_service(":memory:", cfg)
        assert service.estimator is not None
        service.close()

    def test_doctor_checks_the_mcp_sdk(self):
        import leap.doctor as doctor

        status, detail = doctor._mcp_sdk()
        assert status == "ok"
        assert "mcp.server.mcpserver" in detail

    def test_find_session_prefers_the_most_recent_tie(self, service):
        first = service.create_session("tie-learner", "tie")["session_id"]
        second = service.create_session("tie-learner", "tie")["session_id"]
        found = service.find_session("tie-learner", "tie")
        assert found["sessions"][0]["session_id"] == second
        assert {row["session_id"] for row in found["sessions"]} == {first, second}

    def test_start_learning_resumes_an_active_session(self, service):
        first = service.start_learning("resume-learner", "same topic")
        second = service.start_learning("resume-learner", "same topic")
        assert second["existing_session"] is True
        assert second["session_id"] == first["session_id"]
        forced = service.start_learning("resume-learner", "same topic", force_new=True)
        assert forced["existing_session"] is False
        assert forced["session_id"] != first["session_id"]

    def test_learning_mode_negation_is_not_misread(self):
        assert resolve_mode("我不想准备考试") is None
        assert resolve_mode("别用速成的方式") is None
        assert resolve_mode("我要准备考试") == "exam_prep"


# ---------------------------------------------------------------------------
# P2 - closing lifecycle, BKT interpretation, transfer evidence scoping
# ---------------------------------------------------------------------------
class TestClosingLifecycle:
    def test_closed_session_cannot_continue_teaching(self, service):
        session_id = _grounded(service)
        service.generate_final_report(session_id)
        service.complete_session(session_id)
        snapshot = service.get_learner_snapshot(session_id)
        assert snapshot["session_closed"] is True
        assert snapshot["next_call"] is None
        with pytest.raises(ToolError) as excinfo:
            service.continue_lesson(session_id)
        assert excinfo.value.code == "session_closed"

    def test_initialized_skip_decision_can_be_recorded_after_creation(self, service):
        created = service.create_session("skip-learner", "skip topic")
        session_id = created["session_id"]
        with pytest.raises(ToolError):
            service.generate_diagnostic(session_id)
        decision = service.set_domain_grounding_skip(session_id, True, reason="learner declined")
        assert decision["allow_skip_domain_grounding"] is True
        assert service.generate_diagnostic(session_id)["ok"] is True

    def test_retained_node_regresses_after_a_long_gap(self):
        service = build_service(":memory:")
        session_id = _grounded(service)
        _nodes(service, session_id, [{"node_id": "r.n1", "title": "t", "unit_tag": "u1"}])
        service.submit_attempt(session_id, "answer", node_id="r.n1")
        old = now_ts() - 40 * 86400
        service.db.execute(
            "INSERT INTO learner_knowledge_state (learner_id, node_id, mastery_probability, "
            "hint_dependency, evidence_stage, last_assessed_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("hardening-learner", "r.n1", 0.95, 0.0, "retained", old, old),
        )
        service.db.execute(
            "INSERT INTO review_items (review_item_id, learner_id, node_id, stability, difficulty, "
            "retrievability, last_review_at, next_review_at, review_count, scheduler_version, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("rev_lapsed", "hardening-learner", "r.n1", 10.0, 5.0, 0.9, old, old + 86400, 2, "fsrs-6", old, old),
        )
        stage = service.reevaluate_evidence_stage("hardening-learner", "r.n1", session_id)
        assert stage == "practiced"
        service.close()

    def test_transfer_scores_are_validated_and_session_scoped(self):
        service = build_service(":memory:")
        session_a = _grounded(service, learner="ts", topic="topic-a")
        session_b = _grounded(service, learner="ts", topic="topic-b")
        _nodes(service, session_a, [{"node_id": "tsna", "title": "a", "unit_tag": "u"}])
        _nodes(service, session_b, [{"node_id": "tsnb", "title": "b", "unit_tag": "u"}])
        with pytest.raises(ToolError):
            service.record_transfer_result("ts", "tsna", "near", 1.5)
        service.record_transfer_result("ts", "tsna", "near", 0.95)
        with pytest.raises(ToolError) as exc:
            service.record_transfer_result("ts", "tsna", "near", 0.95, session_id=session_b)
        assert exc.value.code == "invalid_node"
        metrics_b = service.get_learning_metrics(session_b)
        assert metrics_b["transfer_performance"]["attempts"] == 0
        metrics_a = service.get_learning_metrics(session_a)
        assert metrics_a["transfer_performance"]["attempts"] == 1
        service.close()


class TestBKTHardening:
    def test_decay_and_failure_stay_above_the_configured_floor(self):
        estimator = BKTEstimator(BKTParams(mastery_floor=0.08))
        assert estimator.time_decay(0.9, 1000) == pytest.approx(0.08)
        prior = None
        for _ in range(10):
            prior = estimator.update(prior, score=0.0)
        assert prior >= 0.08

    def test_mastery_interpretation_explains_the_model(self):
        estimator = BKTEstimator()
        interpretation = estimator.interpret(0.33)
        assert interpretation["lower_bound"] == estimator.params.mastery_floor
        assert interpretation["caveats"]
        assert "p_transit" in " ".join(interpretation["caveats"])

    def test_commit_response_labels_the_attempt_stage_explicitly(self, dag, grounded_service):
        attempt = grounded_service.submit_attempt(dag, "answer", node_id="n2")
        result = grounded_service.commit_assessment(
            attempt["attempt_id"], "answer", correctness=1.0, reasoning_quality=0.9
        )
        assert result["attempt_stage_label"] == result["evidence_stage_snapshot"]
        assert "immutable" in result["attempt_stage_label_note"]
        assert result["mastery_interpretation"]["value"] == pytest.approx(
            result["learner_state"]["mastery_probability"]
        )


# ---------------------------------------------------------------------------
# P2 - real stdio MCP server under parallel calls (the P0 reproduction)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_parallel_tool_calls_over_real_stdio_are_serialized(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "parallel.sqlite"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "leap.server"],
        env={**os.environ, "LEAP__DATABASE_PATH": str(database), "PYTHONPATH": str(root / "src")},
    )
    async with asyncio.timeout(60), stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def call(name, arguments):
                result = await session.call_tool(name, arguments)
                assert not result.is_error, result
                return result.structured_content or json.loads(
                    next(block.text for block in result.content if block.type == "text")
                )

            started = await call("start_learning", {"learner_id": "par", "topic": "par"})
            session_id = started["session_id"]
            await call(
                "save_benchmark_report",
                {"session_id": session_id, "report_text": "# r",
                 "source_refs": REFS, "verification": VERIFICATION},
            )
            await call(
                "save_knowledge_nodes",
                {"session_id": session_id, "nodes": [{"node_id": "p.n1", "title": "t", "unit_tag": "u1"}]},
            )
            responses = await asyncio.gather(
                *[
                    call("submit_answer", {"session_id": session_id, "node_id": "p.n1",
                                           "answer": f"parallel {index}", "correctness": 0.9})
                    for index in range(8)
                ]
            )
            assert all(response["ok"] is True for response in responses), responses
            with sqlite3.connect(database) as connection:
                attempts = connection.execute(
                    "SELECT attempt_index FROM learning_attempts WHERE session_id = ? "
                    "ORDER BY attempt_index",
                    (session_id,),
                ).fetchall()
            assert [row[0] for row in attempts] == [1, 2, 3, 4, 5, 6, 7, 8]

            args = {"session_id": session_id, "node_id": "p.n1", "answer": "retry",
                    "correctness": 0.9, "request_id": "retry-1"}
            receipts = await asyncio.gather(*(call("submit_answer", args) for _ in range(8)))
            assert all(receipt["ok"] for receipt in receipts)
            assert len({receipt["attempt_id"] for receipt in receipts}) == 1
            assert sum(bool(receipt.get("idempotent_replay")) for receipt in receipts) == 7
            conflict = await call("submit_answer", {**args, "answer": "different"})
            assert conflict["error"]["code"] == "request_id_conflict"
            with sqlite3.connect(database) as connection:
                assert connection.execute("SELECT COUNT(*) FROM learning_attempts").fetchone()[0] == 9
                assert connection.execute("SELECT COUNT(*) FROM assessment_results").fetchone()[0] == 9

# ---------------------------------------------------------------------------
# P1/P2 - schema migration guarantees + sqlite error mapping
# ---------------------------------------------------------------------------
class TestStorageGuards:
    def test_uniqueness_indexes_exist_after_initialize(self):
        db = Database(":memory:").initialize()
        names = {row["name"] for row in db.query(
            "SELECT name FROM sqlite_master WHERE type = 'index'")}
        assert "idx_results_attempt_unique" in names
        assert "idx_attempts_unique" in names
        assert "idx_transfer_session" in names
        db.close()

    def test_existing_database_is_migrated_in_place(self, tmp_path):
        database = tmp_path / "legacy.sqlite"
        legacy = sqlite3.connect(database)
        legacy.executescript(
            "CREATE TABLE learners (learner_id TEXT PRIMARY KEY, name TEXT NOT NULL, "
            "created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);"
            "CREATE TABLE learning_sessions (session_id TEXT PRIMARY KEY, "
            "learner_id TEXT NOT NULL, topic TEXT NOT NULL, status TEXT NOT NULL, "
            "state_version INTEGER NOT NULL DEFAULT 1, domain_grounding_stage TEXT, "
            "created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);"
        )
        legacy.execute(
            "CREATE TABLE transfer_results (id INTEGER PRIMARY KEY, learner_id TEXT NOT NULL, "
            "node_id TEXT NOT NULL, transfer_type TEXT NOT NULL, score REAL, created_at INTEGER NOT NULL)"
        )
        legacy.execute(
            "INSERT INTO transfer_results VALUES (1, 'learner', 'node', 'near', 0.9, 1)"
        )
        legacy.commit()
        legacy.close()
        db = Database(str(database)).initialize()
        assert db.scalar("SELECT score FROM transfer_results WHERE id = 1") == 0.9
        db.initialize()
        columns = {row["name"] for row in db.query("PRAGMA table_info(transfer_results)")}
        assert "session_id" in columns
        names = {row["name"] for row in db.query(
            "SELECT name FROM sqlite_master WHERE type = 'index'")}
        assert "idx_attempts_unique" in names
        db.close()

    def test_sqlite_errors_are_mapped_to_structured_codes(self):
        import leap.server as server_module

        busy = server_module._sqlite_error(sqlite3.OperationalError("database is locked"), "tool")
        assert busy.code == "database_busy"
        assert busy.retryable is True
        integrity = server_module._sqlite_error(
            sqlite3.IntegrityError("FOREIGN KEY constraint failed"), "tool")
        assert integrity.code == "data_integrity_error"
        assert integrity.retryable is False

    def test_default_database_path_resolution_is_documented(self, tmp_path, monkeypatch):
        from leap.config import resolve_path

        monkeypatch.delenv("LEAP_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        assert resolve_path("data/leap.db") == tmp_path / "data" / "leap.db"
        monkeypatch.setenv("LEAP_HOME", str(tmp_path / "home"))
        assert resolve_path("data/leap.db") == tmp_path / "home" / "data" / "leap.db"
        absolute = tmp_path / "abs.db"
        monkeypatch.setenv("LEAP_HOME", str(tmp_path / "home"))
        assert resolve_path(absolute) == absolute



@pytest.mark.parametrize("rating", [1, 2, 3, 4])
def test_review_rating_updates_the_owning_session(grounded_service, dag, rating):
    review = grounded_service.schedule_review("learner-test", "n2")["review_item_id"]
    result = grounded_service.review_answer(review, rating)
    assert result["ok"] and result["session_id"] == dag
    assert grounded_service.db.scalar(
        "SELECT review_count FROM review_items WHERE review_item_id = ?", (review,)
    ) == 1


def test_review_queue_and_submission_are_session_scoped(grounded_service, dag):
    review = grounded_service.schedule_review("learner-test", "n2")["review_item_id"]
    grounded_service.db.execute("UPDATE review_items SET next_review_at = ?", (now_ts() - 60,))
    other = _grounded(grounded_service, learner="learner-test", topic="other")
    assert grounded_service.get_review_queue("learner-test", session_id=other)["count"] == 0
    next_call = grounded_service.get_review_queue("learner-test", session_id=dag)["next_call"]
    assert next_call["arguments"] == {"review_item_id": review, "session_id": dag}
    with pytest.raises(ToolError) as exc:
        grounded_service.review_answer(review, 3, session_id=other)
    assert exc.value.code == "invalid_node"
    assert grounded_service.db.scalar("SELECT review_count FROM review_items") == 0


def test_closed_session_rejects_new_assessment(grounded_service, dag):
    attempt = grounded_service.submit_attempt(dag, "answer", node_id="n2")
    grounded_service.generate_final_report(dag)
    grounded_service.complete_session(dag)
    with pytest.raises(ToolError) as exc:
        grounded_service.commit_assessment(attempt["attempt_id"], "answer", correctness=0.9)
    assert exc.value.code == "session_closed"
    assert grounded_service.db.scalar("SELECT COUNT(*) FROM assessment_results") == 0


def test_fully_incorrect_answers_never_increase_mastery():
    estimator = BKTEstimator()
    prior = estimator.initial()
    for _ in range(6):
        before = prior
        prior = estimator.update(prior, score=0.0)
        assert estimator.params.mastery_floor <= prior <= before
    assert prior < estimator.initial()
