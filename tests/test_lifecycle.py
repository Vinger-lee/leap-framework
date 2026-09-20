"""End-to-end lifecycle and API contract tests.

These exercise the runtime the way a host agent would: create a session, ground
the domain, build a DAG, teach, assess, schedule retention and report.
"""

from __future__ import annotations

import json

import pytest

from leap.i18n import translator_for
from leap.tools import ToolError
from tests.conftest import answer_and_assess


class TestSessionLifecycle:
    def test_learner_id_is_mandatory(self, service):
        with pytest.raises(ToolError) as exc:
            service.create_session("", "recursion")
        assert exc.value.code == "invalid_argument"

    def test_topic_is_mandatory(self, service):
        with pytest.raises(ToolError):
            service.create_session("L1", "   ")

    def test_session_can_be_recovered_by_learner_and_topic(self, service):
        created = service.create_session("L1", "recursion")
        found = service.find_session("L1", "recursion")
        assert found["count"] == 1
        assert found["sessions"][0]["session_id"] == created["session_id"]

    def test_next_step_walks_the_lifecycle(self, grounded_service, session_id):
        assert grounded_service.get_session_info(session_id)["next_step"] == "knowledge_representation"
        grounded_service.save_knowledge_nodes(
            session_id, [{"node_id": "x1", "title": "t", "unit_tag": "u"}]
        )
        assert grounded_service.get_session_info(session_id)["next_step"] == "diagnostic"

    def test_unknown_session_raises(self, service):
        with pytest.raises(ToolError) as exc:
            service.get_session_info("ses_missing")
        assert exc.value.code == "unknown_session"

    def test_goal_round_trip(self, service):
        session = service.create_session("L1", "recursion")
        sid = session["session_id"]
        service.save_learning_goal(sid, "understand recursion", target_depth="application", time_budget=3600)
        goal = service.get_learning_goal(sid)["learning_goal"]
        assert goal["goal"] == "understand recursion"
        assert goal["time_budget"] == 3600

    def test_complete_session_validates_status(self, service):
        session = service.create_session("L1", "recursion")
        with pytest.raises(ToolError):
            service.complete_session(session["session_id"], status="finished")
        assert service.complete_session(session["session_id"])["status"] == "completed"


class TestAssessmentContract:
    def test_raw_answer_is_required(self, grounded_service, dag):
        attempt = grounded_service.submit_attempt(dag, "answer text", node_id="n1")
        with pytest.raises(ToolError) as exc:
            grounded_service.commit_assessment(attempt["attempt_id"], "")
        assert exc.value.code == "invalid_argument"

    def test_assessor_type_is_validated(self, grounded_service, dag):
        attempt = grounded_service.submit_attempt(dag, "answer", node_id="n1")
        with pytest.raises(ToolError) as exc:
            grounded_service.commit_assessment(attempt["attempt_id"], "answer", assessor_type="vibes")
        assert exc.value.code == "invalid_assessor_type"

    def test_raw_answer_is_stored_for_audit(self, grounded_service, dag):
        raw = "def fact(n): return 1 if n <= 1 else n * fact(n - 1)"
        attempt = grounded_service.submit_attempt(dag, raw, node_id="n1")
        grounded_service.commit_assessment(attempt["attempt_id"], raw, correctness=1.0)
        history = grounded_service.get_assessment_history(dag, "n1")["results"]
        assert history[0]["raw_answer"] == raw

    def test_scores_outside_unit_interval_are_rejected(self, grounded_service, dag):
        attempt = grounded_service.submit_attempt(dag, "a", node_id="n1")
        with pytest.raises(ToolError) as exc:
            grounded_service.commit_assessment(attempt["attempt_id"], "a", correctness=1.4)
        assert exc.value.code == "invalid_score"

    def test_overall_score_uses_configured_weights(self, grounded_service, session_id):
        result = grounded_service.assess_response(
            session_id,
            {"correctness": 1.0, "conceptual_understanding": 1.0,
             "reasoning_quality": 1.0, "application": 1.0},
        )
        assert result["overall_score"] == pytest.approx(1.0)

    def test_transfer_and_hint_dependency_are_excluded_from_overall(self, grounded_service, session_id):
        baseline = grounded_service.assess_response(
            session_id, {"correctness": 0.8, "conceptual_understanding": 0.8,
                         "reasoning_quality": 0.8, "application": 0.8}
        )["overall_score"]
        with_extra = grounded_service.assess_response(
            session_id, {"correctness": 0.8, "conceptual_understanding": 0.8,
                         "reasoning_quality": 0.8, "application": 0.8,
                         "transfer": 0.0, "hint_dependency": 1.0}
        )["overall_score"]
        assert baseline == with_extra
        assert "transfer" in grounded_service.assess_response(session_id, {})["excluded_from_overall_score"]

    def test_assess_response_does_not_persist(self, grounded_service, session_id):
        grounded_service.assess_response(session_id, {"correctness": 1.0})
        assert grounded_service.get_assessment_history(session_id)["count"] == 0

    def test_mastery_is_computed_server_side(self, grounded_service, dag):
        """The caller never supplies mastery; the runtime derives it."""
        before = grounded_service.get_mastery_status(dag, "n1")["learner_state"]
        assert before is None
        answer_and_assess(grounded_service, dag, "n1", correctness=1.0)
        after = grounded_service.get_mastery_status(dag, "n1")["learner_state"]
        assert 0.0 < after["mastery_probability"] <= 1.0

    def test_repeated_success_raises_mastery(self, grounded_service, dag):
        values = []
        for _ in range(4):
            answer_and_assess(grounded_service, dag, "n1", correctness=1.0)
            values.append(grounded_service.get_mastery_status(dag, "n1")["learner_state"]["mastery_probability"])
        assert values == sorted(values)
        assert values[-1] > values[0]

    def test_hint_dependency_is_smoothed(self, grounded_service, dag):
        answer_and_assess(grounded_service, dag, "n1", hint_level=0, correctness=1.0)
        clean = grounded_service.get_mastery_status(dag, "n1")["learner_state"]["hint_dependency"]
        answer_and_assess(grounded_service, dag, "n1", hint_level=3, correctness=0.2)
        after = grounded_service.get_mastery_status(dag, "n1")["learner_state"]["hint_dependency"]
        assert after > clean
        assert after < 1.0  # one bad attempt must not saturate the estimate


class TestMisconceptions:
    def test_misconception_is_recorded_in_the_authoritative_table(self, grounded_service, dag):
        result = grounded_service.assess_misconception(
            "learner-test", "n2", "recursive call has no termination condition",
            severity=0.8, session_id=dag,
        )
        assert result["misconception_id"] > 0
        active = grounded_service.get_mastery_status(dag, "n2")["misconception_ids"]
        assert active == [result["misconception_id"]]

    def test_misconception_cache_column_is_refreshed_on_assessment(self, grounded_service, dag):
        created = grounded_service.assess_misconception(
            "learner-test", "n2", "off-by-one base case", session_id=dag
        )
        answer_and_assess(grounded_service, dag, "n2", correctness=0.3)
        state = grounded_service.get_mastery_status(dag, "n2")["learner_state"]
        # misconception_state is a read-only JSON snapshot of the authoritative table.
        assert json.loads(state["misconception_state"]) == [created["misconception_id"]]

    def test_resolving_a_misconception_updates_status(self, grounded_service, dag):
        created = grounded_service.assess_misconception(
            "learner-test", "n2", "off-by-one base case", session_id=dag
        )
        resolved = grounded_service.resolve_misconception(created["misconception_id"])
        assert resolved["status"] == "resolved"
        assert grounded_service.get_mastery_status(dag, "n2")["misconception_ids"] == []

    def test_policy_prioritises_correction_for_active_misconceptions(self, grounded_service, dag):
        answer_and_assess(grounded_service, dag, "n2", correctness=0.2)
        grounded_service.assess_misconception(
            "learner-test", "n2", "recursion never terminates", severity=0.9, session_id=dag
        )
        decision = grounded_service.evaluate_pedagogical_policy(dag, "n2")["decision"]
        # Correction outranks prerequisite repair: a wrong mental model would
        # otherwise corrupt every later observation.
        assert decision["selected_strategy"] == "Correction"
        assert decision["selected_action"] == "Correct Misconception"


class TestPolicyAndTelemetry:
    def test_decision_is_persisted_and_replayable(self, grounded_service, dag):
        result = grounded_service.commit_pedagogical_decision(dag, node_id="n1")
        assert result["decision_id"]
        log = grounded_service.get_decision_log(dag)["decisions"]
        assert len(log) == 1
        assert log[0]["selected_action"]

    def test_unknown_strategy_is_rejected(self, grounded_service, dag):
        with pytest.raises(ToolError) as exc:
            grounded_service.commit_pedagogical_decision(dag, selected_strategy="Hypnosis")
        assert exc.value.code == "invalid_strategy"

    def test_action_vocabulary_is_exposed(self, grounded_service):
        actions = grounded_service.get_available_actions()["actions"]
        assert "Advance Unit" in actions
        assert "Provide Worked Example" in actions

    def test_strategy_library_is_seeded(self, grounded_service):
        strategies = grounded_service.get_available_strategies()
        assert strategies["count"] == 10
        assert "Retrieval Practice" in strategies["vocabulary"]

    def test_events_are_recorded_throughout(self, grounded_service, dag):
        answer_and_assess(grounded_service, dag, "n1")
        events = grounded_service.events.recent(dag, limit=100)
        types = {e["event_type"] for e in events}
        assert "session_created" in types
        assert "attempt_submitted" in types
        assert "assessment_committed" in types

    def test_state_version_advances_on_assessment(self, grounded_service, dag):
        before = grounded_service.get_session_info(dag)["session"]["state_version"]
        answer_and_assess(grounded_service, dag, "n1")
        after = grounded_service.get_session_info(dag)["session"]["state_version"]
        assert after > before


class TestRetention:
    def test_review_item_is_created_after_demonstration(self, grounded_service, dag):
        for _ in range(4):
            answer_and_assess(grounded_service, dag, "n1", correctness=1.0)
        items = grounded_service.get_review_state("learner-test", "n1")["review_items"]
        assert len(items) == 1
        assert items[0]["next_review_at"] is not None

    def test_submitting_a_review_reschedules_and_increments_count(self, grounded_service, dag):
        for _ in range(4):
            answer_and_assess(grounded_service, dag, "n1", correctness=1.0)
        item = grounded_service.get_review_state("learner-test", "n1")["review_items"][0]
        result = grounded_service.submit_review(item["review_item_id"], 3, session_id=dag)
        assert result["interval_days"] > 0
        refreshed = grounded_service.get_review_state("learner-test", "n1")["review_items"][0]
        assert refreshed["review_count"] == 1

    def test_invalid_rating_is_rejected(self, grounded_service, dag):
        grounded_service.schedule_review("learner-test", "n1", session_id=dag)
        item = grounded_service.get_review_state("learner-test", "n1")["review_items"][0]
        with pytest.raises(ToolError) as exc:
            grounded_service.submit_review(item["review_item_id"], 7)
        assert exc.value.code == "invalid_rating"

    def test_due_reviews_never_block_new_learning_globally(self, grounded_service, dag):
        result = grounded_service.get_due_reviews("learner-test")
        assert result["blocks_new_learning"] is False

    def test_review_cache_mirrors_the_authoritative_table(self, grounded_service, dag):
        grounded_service.schedule_review("learner-test", "n1", session_id=dag)
        item = grounded_service.get_review_state("learner-test", "n1")["review_items"][0]
        cached = grounded_service.get_mastery_status(dag, "n1")["learner_state"]
        if cached is not None:
            assert cached["next_review_at"] == item["next_review_at"]


class TestReportingAndArtifacts:
    def test_final_report_separates_evidence_from_estimates(self, grounded_service, dag):
        answer_and_assess(grounded_service, dag, "n1")
        report = grounded_service.generate_final_report(dag)["report"]
        assert report["observed_evidence"]["attempt_count"] >= 1
        assert "mastery" in report["estimated_state"]
        assert "not a measured fact" in report["estimated_state"]["mastery"]["note"]
        assert isinstance(report["remaining_uncertainty"], list)

    def test_report_marks_missing_retention_and_transfer_as_uncertain(self, grounded_service, dag):
        answer_and_assess(grounded_service, dag, "n1")
        uncertainty = " ".join(grounded_service.generate_final_report(dag)["report"]["remaining_uncertainty"])
        assert "transfer evidence" in uncertainty
        assert "retention evidence" in uncertainty

    def test_report_markdown_is_generated(self, grounded_service, dag):
        markdown = grounded_service.generate_final_report(dag)["markdown"]
        # Headings are localised, so assert against the active catalogue
        # rather than against one hard-coded language.
        t = translator_for(grounded_service.cfg)
        assert f"# {t.t('report.title')}" in markdown
        assert f"## {t.t('report.observed_evidence')}" in markdown
        assert f"## {t.t('report.remaining_uncertainty')}" in markdown

    def test_artifact_round_trip(self, grounded_service, session_id):
        saved = grounded_service.save_artifact(
            "learner-test", session_id, "html", content="<html></html>"
        )
        fetched = grounded_service.get_artifact(saved["artifact_id"])["artifact"]
        assert fetched["content"] == "<html></html>"

    def test_artifact_requires_some_payload(self, grounded_service, session_id):
        with pytest.raises(ToolError):
            grounded_service.save_artifact("learner-test", session_id, "html")

    def test_specs_are_static_documents(self, grounded_service):
        obsidian = grounded_service.get_obsidian_structure()
        web = grounded_service.get_web_component_spec()
        assert obsidian["spec"]["vault_root"] == "LEAP/"
        assert web["spec"]["output_contract"]["global_object"] == "window.LEAP"
        assert "specification only" in web["note"].lower()

    def test_export_contains_the_session_bundle(self, grounded_service, dag):
        bundle = grounded_service.export_session_data(dag)["export"]
        assert bundle["session"]["session_id"] == dag
        assert len(bundle["knowledge_nodes"]) == 3


class TestGroundingEvidence:
    def test_report_artifact_is_linked_to_the_session(self, grounded_service, session_id):
        info = grounded_service.get_session_info(session_id)["session"]
        assert info["benchmark_report_artifact_id"] is not None
        assert info["domain_grounding_stage"] == "completed"

    def test_claim_without_source_is_flagged(self, grounded_service, session_id):
        claim = grounded_service.save_benchmark_claim(session_id, "recursion needs a base case")
        check = grounded_service.validate_claim(claim["claim_id"])
        assert check["source_linked"] is False
        assert check["verified"] is False

    def test_claim_with_source_validates(self, grounded_service, session_id):
        grounded_service.save_benchmark_report(
            session_id, "# report", source_refs=[{"source_id": "src1", "source": "textbook"}]
        )
        claim = grounded_service.save_benchmark_claim(
            session_id, "recursion needs a base case", source_id="src1"
        )
        assert grounded_service.validate_claim(claim["claim_id"])["verified"] is True

    def test_source_conflicts_are_preserved_not_overwritten(self, grounded_service, session_id):
        claim = grounded_service.save_benchmark_claim(session_id, "conflicting claim")
        result = grounded_service.record_source_conflict(
            claim["claim_id"], [{"source": "A", "value": 1}, {"source": "B", "value": 2}],
            uncertainty="sources disagree",
        )
        assert len(result["conflicting_sources"]) == 2
