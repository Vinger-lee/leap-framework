"""State Guard tests (section 19).

The guard is the security boundary of the runtime, so it is tested from both
directions: it must reject invalid transitions **and** it must allow valid ones.
A guard that can only reject would deadlock the learner.
"""

from __future__ import annotations

import pytest

from leap.tools import ToolError
from leap.runtime.state_guard import bloom_rank, transfer_required
from tests.conftest import answer_and_assess


def reach_demonstrated(service, session_id: str, node_id: str, attempts: int = 4) -> dict:
    """Drive a node to the ``demonstrated`` stage with clean, unhinted work."""
    for _ in range(attempts):
        answer_and_assess(service, session_id, node_id, hint_level=0, correctness=1.0)
    return service.get_mastery_status(session_id, node_id)["learner_state"]


def node_checks(decision: dict, node_id: str) -> dict:
    """Extract the per-node check block from a unit-level guard decision.

    ``advance_unit`` reports an aggregate verdict plus the individual node
    results under ``guard.details.nodes`` (section 19.2).
    """
    return decision["guard"]["details"]["nodes"][node_id]


class TestDomainGroundingGate:
    def test_diagnostic_is_blocked_before_grounding(self, service):
        session = service.create_session("L1", "recursion")
        with pytest.raises(ToolError) as exc:
            service.generate_diagnostic(session["session_id"])
        assert exc.value.code == "domain_grounding_required"

    def test_saving_a_report_marks_grounding_complete(self, service):
        session = service.create_session("L1", "recursion")
        result = service.save_benchmark_report(session["session_id"], "# report")
        assert result["domain_grounding_stage"] == "completed"
        assert service.generate_diagnostic(session["session_id"])["ok"] is True

    def test_report_with_stage_reset_is_blocked_again(self, service):
        """The gate reads the stage flag, not merely the presence of a report."""
        session = service.create_session("L1", "recursion")
        sid = session["session_id"]
        service.save_benchmark_report(sid, "# report")
        service.db.execute(
            "UPDATE learning_sessions SET domain_grounding_stage = 'pending' WHERE session_id = ?",
            (sid,),
        )
        with pytest.raises(ToolError) as exc:
            service.generate_diagnostic(sid)
        assert exc.value.code == "domain_grounding_required"

    def test_skip_flag_bypasses_the_gate(self, service):
        session = service.create_session("L1", "recursion", allow_skip_domain_grounding=True)
        result = service.generate_diagnostic(session["session_id"])
        assert result["ok"] is True
        assert result["state_guard"]["allow_skip_domain_grounding"] is True

    def test_notice_is_returned_when_warning_enabled(self, service):
        session = service.create_session("L1", "recursion", domain_grounding_warn_user=True)
        assert session["domain_grounding_notice"]
        assert "Token" in session["domain_grounding_notice"]

    def test_notice_is_suppressed_when_warning_disabled(self, service):
        session = service.create_session("L1", "recursion", domain_grounding_warn_user=False)
        assert session["domain_grounding_notice"] is None


class TestUnitAdvance:
    def test_advance_rejected_without_any_evidence(self, grounded_service, dag):
        with pytest.raises(ToolError) as exc:
            grounded_service.advance_unit(dag, unit_tag="u1")
        assert exc.value.code == "state_guard_rejected"
        assert "no assessment evidence" in exc.value.message

    def test_advance_rejected_when_only_one_node_passes(self, grounded_service, dag):
        """The batch wrapper rejects the whole unit if any single node fails."""
        reach_demonstrated(grounded_service, dag, "n1")
        with pytest.raises(ToolError) as exc:
            grounded_service.advance_unit(dag, unit_tag="u1")
        assert exc.value.code == "state_guard_rejected"
        assert "n2" in exc.value.message or "n3" in exc.value.message

    def test_advance_allowed_when_every_node_passes(self, grounded_service, dag):
        # n1 is understand-level: no transfer required.
        reach_demonstrated(grounded_service, dag, "n1")
        # n2 and n3 are apply-level: transfer evidence is mandatory.
        for node_id in ("n2", "n3"):
            reach_demonstrated(grounded_service, dag, node_id)
            grounded_service.record_transfer_result(
                "learner-test", node_id, "far", 0.9, session_id=dag
            )

        result = grounded_service.advance_unit(dag, unit_tag="u1")
        assert result["ok"] is True
        assert result["guard"]["decision"] == "ALLOW"

    def test_apply_level_node_requires_transfer(self, grounded_service, dag):
        reach_demonstrated(grounded_service, dag, "n2")
        decision = grounded_service.check_advance_unit(dag, node_id="n2")
        checks = node_checks(decision, "n2")
        assert checks["transfer_required"] is True
        assert checks["transfer_completed"] is False

    def test_check_advance_does_not_mutate_state(self, grounded_service, dag):
        before = grounded_service.get_session_info(dag)["session"]["state_version"]
        grounded_service.check_advance_unit(dag, unit_tag="u1")
        after = grounded_service.get_session_info(dag)["session"]["state_version"]
        assert before == after

    def test_manual_override_is_recorded_and_allows(self, grounded_service, dag):
        result = grounded_service.advance_unit(dag, unit_tag="u1", manual_override=True)
        assert result["ok"] is True
        assert node_checks(result, "n1")["manual_override"] is True


class TestPrerequisites:
    def test_missing_prerequisite_blocks_the_dependent_node(self, grounded_service, dag):
        decision = grounded_service.check_advance_unit(dag, node_id="n3")
        assert node_checks(decision, "n3")["prerequisites_met"] is False

    def test_prerequisite_satisfied_after_it_is_demonstrated(self, grounded_service, dag):
        reach_demonstrated(grounded_service, dag, "n1")
        decision = grounded_service.check_advance_unit(dag, node_id="n2")
        assert node_checks(decision, "n2")["prerequisites_met"] is True


class TestOptimisticConcurrency:
    def test_stale_state_version_is_rejected(self, grounded_service, dag):
        stale = grounded_service.get_session_info(dag)["session"]["state_version"]
        reach_demonstrated(grounded_service, dag, "n1")  # bumps the version
        with pytest.raises(ToolError) as exc:
            grounded_service.advance_unit(
                dag, unit_tag="u1", expected_state_version=stale
            )
        assert exc.value.code == "state_guard_rejected"
        assert "state_version" in exc.value.message

    def test_current_state_version_is_accepted(self, grounded_service, dag):
        current = grounded_service.get_session_info(dag)["session"]["state_version"]
        decision = grounded_service.check_advance_unit(
            dag, unit_tag="u1", expected_state_version=current
        )
        assert node_checks(decision, "n1")["current_state_version_valid"] is True


class TestTransferRequirementRules:
    @pytest.mark.parametrize(
        "level,expected",
        [
            ("remember", False),
            ("understand", False),
            ("apply", True),
            ("analyze", True),
            ("记忆", False),
            ("理解", False),
            ("应用", True),
            ("分析", True),
        ],
    )
    def test_conditional_default_follows_bloom_level(self, base_config, level, expected):
        assert transfer_required({"bloom_level": level}, base_config) is expected

    def test_explicit_requirement_wins(self, base_config):
        assert transfer_required(
            {"bloom_level": "remember", "transfer_requirements": "required"}, base_config
        )
        assert not transfer_required(
            {"bloom_level": "apply", "transfer_requirements": "none"}, base_config
        )

    def test_bloom_rank_handles_unknown_labels(self):
        assert bloom_rank("apply") == 2
        assert bloom_rank("应用") == 2
        assert bloom_rank("nonsense") == -1
        assert bloom_rank(None) == -1
