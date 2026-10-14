"""Coarse tutor API (facade): composition, recovery and preserved invariants.

The facade must be a convenience layer, never a shortcut: these tests assert
that it composes the same runtime calls, that a failure stays a failure with the
attempt recoverable, and that the State Guard still decides.
"""

from __future__ import annotations

import pytest

from leap.runtime.profiles import FACADE_TOOL_NAMES
from leap.storage import now_ts
from leap.tools.base import ToolError
from tests.teaching_fixture import register_pair


# ---------------------------------------------------------------------------
# start_learning
# ---------------------------------------------------------------------------
def test_start_learning_records_goal_in_one_call(service):
    result = service.start_learning(
        "learner-coarse", "python recursion", goal="debug simple recursion", target_depth="application"
    )

    assert result["ok"] is True
    assert result["goal_saved"] is True
    assert result["next_step"] == "domain_grounding"
    assert result["next_call"]["tool"] == "save_benchmark_report"
    # domain_grounding_warn_user defaults to true, so the notice must be returned.
    assert result["domain_grounding_notice"]

    goal = service.get_learning_goal(result["session_id"])["learning_goal"]
    assert goal["goal"] == "debug simple recursion"
    assert goal["target_depth"] == "application"


def test_start_learning_without_goal_still_creates_the_session(service):
    result = service.start_learning("learner-coarse", "python recursion")

    assert result["goal_saved"] is False
    assert service.get_learning_goal(result["session_id"])["learning_goal"] is None
    assert result["next_call"]["lifecycle_step"] == "domain_grounding"


def test_start_learning_reports_an_unrecognised_mode_instead_of_ignoring_it(service):
    result = service.start_learning(
        "learner-coarse", "python recursion", mode="只按我喜欢的节奏随便来"
    )

    assert result["ok"] is True
    assert result["mode_notice"]
    assert result["learning_mode"]


# ---------------------------------------------------------------------------
# continue_lesson
# ---------------------------------------------------------------------------
def test_continue_lesson_returns_state_and_a_next_call(dag, grounded_service):
    result = grounded_service.continue_lesson(dag, "n1")

    assert result["ok"] is True
    assert result["evidence_stage"] == "estimated"
    assert result["node_id"] == "n1"
    assert result["recommended_actions"]
    assert result["next_call"]["tool"] in {
        "log_teaching_action",
        "resolve_misconception",
        "get_review_queue",
    }
    # The nested context must not repeat the delivery policy that the envelope carries.
    assert "teaching_delivery_policy" not in result["teaching_context"]
    assert result["teaching_delivery_policy"]


def test_continue_lesson_requires_domain_grounding(service):
    session = service.create_session("learner-coarse", "python recursion")

    with pytest.raises(ToolError) as excinfo:
        service.continue_lesson(session["session_id"], "n1")

    assert excinfo.value.code == "domain_grounding_required"


# ---------------------------------------------------------------------------
# submit_answer
# ---------------------------------------------------------------------------
def test_submit_answer_stores_the_answer_and_commits_the_assessment(dag, grounded_service):
    answer = "the base case stops the recursion"
    result = grounded_service.submit_answer(
        dag,
        answer,
        node_id="n2",
        correctness=0.95,
        conceptual_understanding=0.9,
        reasoning_quality=0.85,
    )

    assert result["assessed"] is True
    assert result["attempt_id"]
    assert result["learner_state"]["mastery_probability"] > 0
    assert result["assessment"]["overall_score"] > 0
    assert result["assessment"]["attempt_id"] == result["attempt_id"]
    assert result["assessment"]["stage_after"] in {"estimated", "practiced"}

    history = grounded_service.get_assessment_history(dag, "n2")
    assert history["results"][0]["raw_answer"] == answer
    attempt = grounded_service.db.query_one(
        "SELECT answer FROM learning_attempts WHERE attempt_id = ?", (result["attempt_id"],)
    )
    assert attempt["answer"] == answer


def test_submit_answer_without_scores_only_records_the_attempt(dag, grounded_service):
    result = grounded_service.submit_answer(dag, "a free-text explanation", node_id="n2")

    assert result["assessed"] is False
    assert result["next_call"]["tool"] == "commit_assessment"
    assert result["next_call"]["arguments"]["attempt_id"] == result["attempt_id"]
    assert result["next_call"]["arguments"]["raw_answer"] == "a free-text explanation"
    assert grounded_service.get_assessment_history(dag, "n2")["count"] == 0


def test_submit_answer_failure_keeps_the_attempt_recoverable(dag, grounded_service):
    with pytest.raises(ToolError) as excinfo:
        grounded_service.submit_answer(dag, "an answer", node_id="n2", correctness=2.5)

    error = excinfo.value
    assert error.code == "invalid_score"
    assert error.details["failed_step"] == "commit_assessment"
    attempt_id = error.details["attempt_id"]
    assert attempt_id

    # The stored attempt can still be assessed directly: nothing was lost and
    # nothing was silently updated.
    committed = grounded_service.commit_assessment(attempt_id, "an answer", correctness=0.9)
    assert committed["ok"] is True
    assert grounded_service.get_assessment_history(dag, "n2")["count"] == 1


def test_submit_answer_preserves_the_grounding_gate(service):
    session = service.create_session("learner-coarse", "python recursion")

    with pytest.raises(ToolError) as excinfo:
        service.submit_answer(session["session_id"], "an answer", correctness=1.0)

    assert excinfo.value.code == "domain_grounding_required"


# ---------------------------------------------------------------------------
# advance_lesson
# ---------------------------------------------------------------------------
def test_advance_lesson_reports_a_rejection_without_writing(dag, grounded_service):
    before = grounded_service.get_session_info(dag)["session"]

    result = grounded_service.advance_lesson(dag, unit_tag="u1")

    assert result["ok"] is True
    assert result["advanced"] is False
    assert result["guard_allowed"] is False
    assert result["guard"]["decision"] == "REJECT"
    assert result["remediation"]
    # Remediation names the node and the failed check, not just "rejected".
    assert any("u1" not in r and "n" in r for r in result["remediation"])
    assert result["next_call"]["tool"] == "continue_lesson"

    after = grounded_service.get_session_info(dag)["session"]
    assert after["state_version"] == before["state_version"]
    assert after["current_node_id"] == before["current_node_id"]


def test_advance_lesson_advances_when_the_guard_allows_it(dag, grounded_service):
    result = grounded_service.advance_lesson(dag, unit_tag="u1", manual_override=True)

    assert result["advanced"] is True
    assert result["guard_allowed"] is True
    assert result["state_version"] > 1


def test_advance_lesson_never_swallows_a_hard_failure(service):
    with pytest.raises(ToolError) as excinfo:
        service.advance_lesson("ses-does-not-exist", unit_tag="u1")

    assert excinfo.value.code == "unknown_session"


# ---------------------------------------------------------------------------
# retention
# ---------------------------------------------------------------------------
def test_review_queue_and_review_answer(dag, grounded_service):
    scheduled = grounded_service.schedule_review("learner-test", "n2", session_id=dag)
    review_item_id = scheduled["review_item_id"]
    # Make the card due now instead of waiting for the scheduled interval.
    grounded_service.db.execute(
        "UPDATE review_items SET next_review_at = ? WHERE review_item_id = ?",
        (now_ts() - 60, review_item_id),
    )

    queue = grounded_service.get_review_queue("learner-test")

    assert queue["count"] == 1
    assert queue["blocks_new_learning"] is False
    assert queue["next_call"]["tool"] == "review_answer"
    assert queue["next_call"]["arguments"]["review_item_id"] == review_item_id

    answered = grounded_service.review_answer(review_item_id, 3, session_id=dag)
    assert answered["rating"] == 3
    assert answered["interval_days"] >= 1
    assert grounded_service.get_review_queue("learner-test")["count"] == 0


def test_review_answer_rejects_an_out_of_range_rating(dag, grounded_service):
    scheduled = grounded_service.schedule_review("learner-test", "n2", session_id=dag)

    with pytest.raises(ToolError) as excinfo:
        grounded_service.review_answer(scheduled["review_item_id"], 5)

    assert excinfo.value.code == "invalid_rating"


def test_get_review_queue_on_an_empty_queue_points_back_to_teaching(grounded_service):
    queue = grounded_service.get_review_queue("learner-test")

    assert queue["count"] == 0
    assert queue["next_call"]["tool"] == "continue_lesson"


# ---------------------------------------------------------------------------
# get_learner_snapshot
# ---------------------------------------------------------------------------
def test_get_learner_snapshot_lists_setup_gaps(grounded_service, session_id):
    snapshot = grounded_service.get_learner_snapshot(session_id)

    assert snapshot["setup_gaps"] == [
        "knowledge_nodes_missing",
        "teaching_package_missing",
        "assessment_items_missing",
    ]
    assert snapshot["next_call"]["tool"] == "decompose_topic"


def test_get_learner_snapshot_reports_progress_in_one_call(dag, grounded_service):
    register_pair(grounded_service, dag)
    grounded_service.submit_answer(
        dag, "a worked answer", node_id="n2", correctness=1.0, reasoning_quality=0.9
    )

    snapshot = grounded_service.get_learner_snapshot(dag)

    assert snapshot["tracked_nodes"] == 1
    assert snapshot["evidence_stage_counts"]["practiced"] == 1
    assert snapshot["node_states"][0]["node_id"] == "n2"
    assert snapshot["node_states"][0]["mastery_probability"] > 0
    assert "assessment_items_missing" in snapshot["setup_gaps"]


def test_snapshot_never_reports_the_teaching_package_as_missing_once_registered(
    dag, grounded_service
):
    register_pair(grounded_service, dag)

    snapshot = grounded_service.get_learner_snapshot(dag)

    assert "teaching_package_missing" not in snapshot["setup_gaps"]
    assert snapshot["setup_gaps"] == ["assessment_items_missing"]


# ---------------------------------------------------------------------------
# facade metadata
# ---------------------------------------------------------------------------
def test_every_facade_method_is_an_mcp_tool():
    from leap.server import registered_tool_names, build_server

    registered = registered_tool_names(build_server())
    assert set(FACADE_TOOL_NAMES) <= set(registered)


def test_facade_calls_can_be_mixed_with_fine_grained_calls(dag, grounded_service):
    """One session, both APIs: the coarse layer adds no second state machine."""
    coarse = grounded_service.submit_answer(dag, "half an answer", node_id="n2", correctness=0.5)
    assert coarse["assessed"] is True

    attempt = grounded_service.submit_attempt(dag, "another answer", node_id="n2")
    committed = grounded_service.commit_assessment(
        attempt["attempt_id"], "another answer", correctness=0.7
    )
    assert committed["ok"] is True

    history = grounded_service.get_assessment_history(dag, "n2")
    assert history["count"] == 2
