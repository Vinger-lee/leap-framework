"""Regression cases for grounding bypass and unchecked assessment delivery."""
import pytest

from leap.tools import ToolError
from tests.teaching_fixture import register_pair


def grounding_evidence():
    """Synthetic evidence record; these tests do not attest source retrieval."""
    return {
        "source_refs": [{"source": "fixture/functions.txt",
                         "source_type": "test_fixture", "locator": "docstrings",
                         "excerpt": "The first statement of a function can be a string literal."}],
        "verification": {
            "scope": "Python functions; this source does not establish recursion termination",
            "claims": [{"claim": "A first string literal can be a docstring", "source_index": 0}],
            "worked_examples": [{"problem": "Identify the docstring in def f(): 'doc'",
                                 "solution": "f.__doc__ is 'doc'", "check_method": "Python execution",
                                 "check_result": "Fixture expected result: f.__doc__ == 'doc'"}],
            "limitations": ["No exam syllabus was consulted"],
        },
    }


def test_empty_evidence_cannot_complete_grounding(service):
    sid = service.create_session("L", "limits")["session_id"]
    result = service.save_benchmark_report(sid, "I already know this topic")
    assert result["domain_grounding_stage"] == "pending"
    assert result["missing_evidence"]
    with pytest.raises(ToolError, match="."):
        service.generate_diagnostic(sid)


@pytest.mark.parametrize("method", ["generate_assessment", "generate_transfer_probe", "get_teaching_context", "start_unit"])
def test_teaching_cannot_bypass_grounding(service, method):
    sid = service.create_session("L", "limits")["session_id"]
    with pytest.raises(ToolError) as exc:
        getattr(service, method)(sid)
    assert exc.value.code == "domain_grounding_required"


def test_grounding_requires_readable_source_and_worked_check(service):
    sid = service.create_session("L", "functions")["session_id"]
    evidence = grounding_evidence()
    evidence["source_refs"][0].pop("excerpt")
    assert service.save_benchmark_report(sid, "Baseline", **evidence)["domain_grounding_stage"] == "pending"
    assert service.save_benchmark_report(sid, "Baseline", **grounding_evidence())["domain_grounding_stage"] == "completed"


def test_claim_cannot_borrow_source_from_another_session(service):
    first = service.create_session("L", "functions")["session_id"]
    second = service.create_session("L", "limits")["session_id"]
    report = service.save_benchmark_report(first, "Baseline", **grounding_evidence())
    with pytest.raises(ToolError) as exc:
        service.save_benchmark_claim(second, "Unsupported claim", source_id=report["sources_saved"][0])
    assert exc.value.code == "invalid_source"


def test_item_requires_solution_and_check_before_registration(grounded_service, session_id):
    with pytest.raises(ToolError):
        grounded_service.save_assessment_item(session_id, "q", "Solve 2a=a-1", "-1", "", [], [])
    register_pair(grounded_service, session_id)
    item = grounded_service.save_assessment_item(
        session_id, "q", "Solve 2a=a-1", "-1", "Subtract a from each side: a=-1", [],
        [{"method": "substitution", "result": "2*(-1) == (-1)-1 == -2"}],
        rejected_answers=[{"answer": "2", "reason": "4 != 1"}],
    )
    assert item["content_verified_by_runtime"] is False
    assert grounded_service.submit_attempt(session_id, "-1", item_id="q")["ok"]
    with pytest.raises(ToolError) as exc:
        grounded_service.save_assessment_item(session_id, "q", "Changed", "2", "Changed", [], [{"method": "check", "result": "ok"}])
    assert exc.value.code == "item_already_exists"


def test_free_text_rule_scores_do_not_enter_learner_state(grounded_service, session_id):
    register_pair(grounded_service, session_id)
    grounded_service.save_assessment_item(session_id, "prose", "Explain continuity", "limit equals value", "Use the definition", [], [{"method": "definition", "result": "Requires equal finite limit and value"}])
    attempt = grounded_service.submit_attempt(session_id, "left and right differ, therefore continuous", item_id="prose")
    with pytest.raises(ToolError) as exc:
        grounded_service.commit_assessment(attempt["attempt_id"], "left and right differ, therefore continuous", correctness=1, assessor_type="rule")
    assert exc.value.code == "semantic_review_required"
    assert grounded_service.db.scalar("SELECT COUNT(*) FROM assessment_results") == 0


def test_commit_cannot_silently_reuse_a_different_answer(grounded_service, session_id):
    attempt = grounded_service.submit_attempt(session_id, "first answer")
    with pytest.raises(ToolError) as exc:
        grounded_service.commit_assessment(attempt["attempt_id"], "post-check answer", correctness=1)
    assert exc.value.code == "raw_answer_mismatch"
