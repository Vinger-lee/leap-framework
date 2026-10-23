"""Policy cannot be bypassed by shallow bodies, partial coverage or artifacts."""
import copy
import pytest
from leap.runtime.delivery import validate_teaching_package
from leap.tools import ToolError
from tests.teaching_fixture import teaching_pair, register_pair


@pytest.mark.parametrize("omission", [False, True])
def test_package_validation_parses_html_and_normalizes_each_passage_once(monkeypatch, omission):
    import leap.runtime.delivery as delivery

    md, html, manifest = teaching_pair()
    passage = "A separate equation check supplies another complete explanation."
    html = html.replace("</body>", f"<p>{passage}</p></body>")
    if not omission:
        md += "\n" + passage
    feeds, normalizations = [], []
    original_feed = delivery.VisibleTeaching.feed
    original_normalize = delivery.normalize_text

    def count_feed(parser, data):
        feeds.append(data)
        return original_feed(parser, data)

    def count_normalize(text):
        if text == passage:
            normalizations.append(text)
        return original_normalize(text)

    monkeypatch.setattr(delivery.VisibleTeaching, "feed", count_feed)
    monkeypatch.setattr(delivery, "normalize_text", count_normalize)
    report = delivery.validate_teaching_package(md, html, manifest)

    assert report["valid"] is not omission
    if omission:
        assert any("coverage" in error for error in report["errors"])
    assert feeds == [html]
    assert normalizations == [passage]


def test_actual_teaching_pair_and_more_complete_markdown():
    md, html, manifest = teaching_pair()
    checked = validate_teaching_package(md, html, manifest)
    assert checked["valid"], checked
    assert checked["content_coverage"] == 1
    assert checked["content_verified_by_runtime"] is False


def visual_pair():
    md, html, manifest = teaching_pair()
    caption = "The moving marker and readout share the same elapsed-time model."
    label = "Elapsed time in seconds"
    source = "One elapsed-time model drives the marker position and numeric output."
    extra = ('<figure id="rig"><svg id="still" role="img" aria-label="Three time states"></svg>'
             f'<figcaption>{caption}</figcaption><p>{label}</p><output id="time">0</output></figure>'
             '<button id="play">Play or pause</button><button id="reset">Reset</button>'
             '<input id="scrub" type="range" aria-label="Elapsed time">')
    html = html.replace("</body>", extra + "</body>")
    md += f"\n{caption}\n{label}\n{source}\nReleased\nAt the stop\n0\nPlay or pause\nReset\n"
    manifest["visual_contract"] = {"profile": "anatomy.v1", "figures": [{
        "id": "motion", "role": "mechanism", "selector": "#rig", "caption": caption,
        "labels": [label], "static_frame": "#still", "animated": True,
        "model_binding": {"source": source, "quantities": [{"name": "elapsed time", "unit": "s", "selector": "#time"}]},
        "controls": {"play_pause": "#play", "reset": "#reset", "scrub": "#scrub"},
        "states": ["Released", "At the stop"],
    }]}
    return md, html, manifest


def test_visual_contract_accepts_real_targets_without_claiming_model_truth():
    md, html, manifest = visual_pair()
    report = validate_teaching_package(md, html, manifest)
    assert report["valid"], report["errors"]
    assert report["content_verified_by_runtime"] is False


@pytest.mark.parametrize("defect", ["missing_still", "fake_still", "fake_control", "hidden_control",
    "duplicate_target", "caption", "label", "output", "model", "states", "reversible", "duplicate_figure"])
def test_visual_contract_rejects_unusable_or_unexplained_figures(defect):
    md, html, manifest = visual_pair()
    figure = manifest["visual_contract"]["figures"][0]
    if defect == "missing_still":
        figure.pop("static_frame")
    elif defect == "fake_still":
        figure["static_frame"] = "#rig"  # A container is not the promised static graphic.
    elif defect == "fake_control":
        figure["controls"]["play_pause"] = "#time"  # Output cannot be pressed.
    elif defect == "hidden_control":
        html = html.replace('id="play"', 'id="play" hidden')
    elif defect == "duplicate_target":
        html = html.replace("</body>", '<button id="reset">Reset</button></body>')
    elif defect == "caption":
        figure["caption"] = "An unsupported new claim absent from the lesson."
    elif defect == "label":
        figure["labels"] = ["An unnamed part"]
    elif defect == "output":
        figure["model_binding"]["quantities"][0]["selector"] = "#nonexistent"
    elif defect == "model":
        figure.pop("model_binding")
    elif defect == "states":
        figure["states"] = ["Released"]
    elif defect == "reversible":
        figure["controls"].pop("scrub")
    else:
        manifest["visual_contract"]["figures"].append(copy.deepcopy(figure))
    report = validate_teaching_package(md, html, manifest)
    assert not report["valid"]
    assert any(error.startswith("visual_contract.") for error in report["errors"]), report


@pytest.mark.parametrize("contract", [None, [], {}, {"profile": "unknown"},
    {"profile": "anatomy.v1", "figures": [None, {"id": [], "role": {}, "selector": 1, "static_frame": [], "animated": True, "controls": []}]}])
def test_malformed_visual_contract_is_rejected_without_crashing(contract):
    md, html, manifest = teaching_pair()
    manifest["visual_contract"] = contract
    assert not validate_teaching_package(md, html, manifest)["valid"]


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
def test_delivery_host_checks_malformed_and_exact_numeric_answers(raw, answer, expected):
    from scripts.sync_delivery import objective_matches
    assert objective_matches({"kind": "numeric", "answer": answer}, raw) is expected


def test_diagnostic_cannot_register_unreviewed_questions(service):
    sid=service.create_session("diagnostic-learner", "limits")["session_id"]
    with pytest.raises(ToolError) as err:
        service.submit_diagnostic(sid, "answer", question="An unchecked question")
    assert err.value.code == "assessment_item_required"
    assert service.db.scalar("SELECT COUNT(*) FROM assessment_items") == 0
    with pytest.raises(ToolError):
        service.submit_diagnostic(sid, "learner self-report")
