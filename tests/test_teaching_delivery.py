"""Policy cannot be bypassed by shallow bodies, partial coverage or artifacts."""
import copy
import pytest
from leap.runtime.delivery import validate_teaching_package
from leap.tools import ToolError
from tests.teaching_fixture import teaching_pair, register_pair


def test_actual_teaching_pair_and_more_complete_markdown():
    md, html, manifest = teaching_pair()
    checked = validate_teaching_package(md, html, manifest)
    assert checked["valid"], checked
    assert checked["content_coverage"] == 1
    assert checked["content_verified_by_runtime"] is False


@pytest.mark.parametrize("defect", ["omission", "extension", "visual", "resource", "shallow"])
def test_pair_rejects_coverage_and_delivery_defects(defect):
    md, html, manifest = teaching_pair()
    manifest = copy.deepcopy(manifest)
    if defect == "omission":
        html = html.replace("</body>", "<p>A separate teaching claim absent from the canonical note must fail.</p></body>")
    elif defect == "extension":
        manifest["markdown_extensions"] = ["Extra"]
    elif defect == "visual":
        manifest["teaching_points"][0]["visualization"]["selector"] = "#missing"
    elif defect == "resource":
        manifest["resources"]["keywords"]["core"] = ["An invented query absent from both bodies"]
    else:
        manifest["teaching_points"][0]["steps"] = ["Solve it"]
    assert not validate_teaching_package(md, html, manifest)["valid"]


def test_item_and_artifact_require_registered_pair(grounded_service, session_id):
    args = (session_id, "new-item", "Solve 3x+5=20", "5", "Subtract five, divide by three", [], [{"method": "substitution", "result": "3*5+5=20"}])
    with pytest.raises(ToolError) as err:
        grounded_service.save_assessment_item(*args)
    assert err.value.code == "teaching_package_required"
    with pytest.raises(ToolError) as err:
        grounded_service.save_artifact("learner-test", session_id, "html", content="<html></html>")
    assert err.value.code == "teaching_package_required"
    package = register_pair(grounded_service, session_id)
    assert grounded_service.save_assessment_item(*args, teaching_package_id=package)["ok"]
    with pytest.raises(ToolError) as err:
        grounded_service.save_artifact("learner-test", session_id, "html", content="<html>changed</html>", metadata={"teaching_package_id": package})
    assert err.value.code == "teaching_content_mismatch"


@pytest.mark.parametrize("mode", ["core_only", "full", "exam_prep"])
def test_policy_persists_across_generation_modes(grounded_service, session_id, mode):
    # Modes affect scheduling; no mode weakens teaching depth or paired delivery.
    result = grounded_service.set_learning_configuration(session_id, mode=mode)
    if result.get("ok"):
        assert result["teaching_delivery_policy"]["mandatory"]
    assert grounded_service.generate_diagnostic(session_id)["teaching_delivery_policy"]["version"] == "3.0"


def test_catalog_contains_expanded_domains(service):
    subjects = service.get_subject_catalog()["catalog"]["subjects"]
    assert {"statistics", "chemistry", "electronics"} <= {s["subject_id"] for s in subjects}
    assert service.get_subject_catalog("chemistry")["catalog_is_exhaustive"] is False


@pytest.mark.parametrize("raw,answer,expected", [
    ("NaN", "0.5", False),
    ("1/0", "0.5", False),
    ("half", "0.5", False),
    ("0.50000001", "0.5", False),
    ("1/2", "0.5", True),
    ("−1/2", "-0.5", True),
])
def test_chapter_host_checks_malformed_and_exact_numeric_answers(raw, answer, expected):
    from scripts.sync_math1_chapter import objective_matches
    assert objective_matches({"kind": "numeric", "answer": answer}, raw) is expected


def test_diagnostic_cannot_register_unreviewed_questions(service):
    sid=service.create_session("diagnostic-learner", "limits")["session_id"]
    with pytest.raises(ToolError) as err:
        service.submit_diagnostic(sid, "answer", question="An unchecked question")
    assert err.value.code == "assessment_item_required"
    assert service.db.scalar("SELECT COUNT(*) FROM assessment_items") == 0
    with pytest.raises(ToolError):
        service.submit_diagnostic(sid, "learner self-report")
