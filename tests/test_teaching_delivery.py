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
    # This fixture exercises a legacy contract that is *not* opted into: only the
    # shared workflow fixture sets allow_legacy.
    manifest.pop("allow_legacy", None)
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


def researched_visual_pair():
    md, html, manifest = visual_pair()
    source = {
        "id": "manual", "source": "https://example.org/instrument-manual",
        "locator": "Assembly, optical sensor", "excerpt": "The object interrupts a light beam.",
        "checked_at": "2026-10-23",
    }
    explanation = "The optical sensor detects passage without applying force."
    basis = "The mounting dimensions are schematic; the beam interruption is documented."
    help_text = "Hover or focus to preview; click, Enter or Space to select; clear to restore."
    check = {"inputs": "Elapsed time = 2 seconds", "expected": "Output = 2 seconds",
             "method": "Substitute time in the identity model", "result": "The independent result agrees"}
    extra = (f'<g id="sensor" role="button" tabindex="0" aria-label="Optical sensor"></g>'
             f'<p>{explanation}</p><p>{help_text}</p><p id="part-info">Part information</p>'
             '<button id="clear-part">Clear selection</button>')
    html = html.replace("</svg>", extra[:extra.index("<p>")] + "</svg>", 1)
    html = html.replace("</body>", extra[extra.index("<p>"):] + "</body>")
    md += "\n" + "\n".join([*source.values(), explanation, basis, help_text,
                                  *check.values(), "Part information", "Clear selection",
                                  "Sources support the principle, not a certified replica."])
    contract = manifest["visual_contract"]
    contract["research"] = {"sources": [source], "limitations": "Sources support the principle, not a certified replica."}
    figure = contract["figures"][0]
    figure["parts"] = [{"selector": "#sensor", "name": "Optical sensor", "explanation": explanation,
                        "representation": "reference", "basis": basis, "source_refs": ["manual"]}]
    figure["inspection"] = {"panel": "#part-info", "clear": "#clear-part", "help": help_text}
    figure["model_binding"]["checks"] = [check]
    return md, html, manifest


def test_researched_visual_records_are_traceable_without_certifying_science():
    md, html, manifest = researched_visual_pair()
    report = validate_teaching_package(md, html, manifest)
    assert report["valid"], report["errors"]
    assert report["content_verified_by_runtime"] is False


def current_visual_pair():
    """Synthetic v2 evidence; not an actual researched instrument."""
    md, html, manifest = researched_visual_pair()
    contract = manifest["visual_contract"]
    contract["profile"] = "anatomy.v2"
    contract["research"]["sources"][0]["evidence_source_id"] = "fixture.visual-source"
    manifest["source_ids"] = ["fixture.visual-source"]
    manifest["policy_id"] = "leap.teaching.delivery"
    manifest["policy_version"] = "3.0"
    figure = contract["figures"][0]
    relationship = "The beam crosses the object's path; the sensor is mounted on the frame."
    figure["parts"][0]["relationship"] = relationship
    binding = figure["model_binding"]
    binding.update(assumptions="Time is a nonnegative independent input.",
                   domain="Elapsed time ranges from zero to two seconds.",
                   limits="This identity model only demonstrates elapsed time, not dynamics.",
                   source_refs=["manual"])
    binding["checks"][0]["kind"] = "typical"
    boundary = {"kind": "boundary", "inputs": "Elapsed time = 0 seconds",
                "expected": "Output = 0 seconds", "method": "Evaluate the initial identity state",
                "result": "The boundary value is zero"}
    binding["checks"].append(boundary)
    md += "\n" + "\n".join([relationship, binding["assumptions"], binding["domain"], binding["limits"],
                              *boundary.values()])
    return md, html, manifest


def test_current_contract_requires_research_model_and_inspection_but_preserves_legacy():
    current = validate_teaching_package(*current_visual_pair())
    assert current["valid"], current["errors"]
    assert current["visual_authoring"]["visual_contract_state"] == "current"
    assert current["visual_authoring"]["visual_contract_valid"] is True
    assert current["visual_authoring"]["browser_behavior_verified_by_runtime"] is False
    for pair, state in ((teaching_pair(), "absent"), (visual_pair(), "legacy_v1")):
        legacy = validate_teaching_package(*pair)
        assert legacy["valid"], legacy["errors"]
        assert legacy["visual_authoring"]["visual_contract_state"] == state
        assert legacy["visual_authoring"]["visual_contract_valid"] is False


@pytest.mark.parametrize("defect", ["research", "evidence_source_id", "parts", "inspection", "relationship",
    "assumptions", "domain", "limits", "model_sources", "checks", "boundary", "check_kind"])
def test_current_contract_rejects_missing_grounding_model_or_inspection(defect):
    md, html, manifest = current_visual_pair()
    contract = manifest["visual_contract"]
    figure = contract["figures"][0]
    if defect == "research":
        contract.pop("research")
    elif defect == "evidence_source_id":
        contract["research"]["sources"][0].pop(defect)
    elif defect in ("parts", "inspection"):
        figure.pop(defect)
    elif defect == "relationship":
        figure["parts"][0].pop(defect)
    elif defect == "model_sources":
        figure["model_binding"]["source_refs"] = ["not-read"]
    elif defect == "boundary":
        figure["model_binding"]["checks"].pop()
    elif defect == "check_kind":
        figure["model_binding"]["checks"][0]["kind"] = []
    else:
        figure["model_binding"].pop(defect)
    report = validate_teaching_package(md, html, manifest)
    assert not report["valid"], defect
    assert report["visual_authoring"]["visual_contract_state"] == "invalid"


def test_formal_process_can_use_states_instead_of_mechanical_parts():
    md, html, manifest = current_visual_pair()
    figure = manifest["visual_contract"]["figures"][0]
    figure["role"] = "process"
    figure.pop("parts")
    figure.pop("inspection")
    report = validate_teaching_package(md, html, manifest)
    assert report["valid"], report["errors"]


def test_current_contract_requires_mapping_each_research_source():
    md, html, manifest = current_visual_pair()
    figure = manifest["visual_contract"]["figures"][0]
    figure.update(role="process", animated=False)
    figure.pop("states")
    for field in ("parts", "inspection", "model_binding", "controls"):
        figure.pop(field)
    manifest["teaching_points"][0]["visualization"] = {
        "no_visual_reason": "The fixture intentionally uses a formal state trace instead of a figure."}

    unmapped = validate_teaching_package(md, html, manifest)
    assert not unmapped["valid"]
    assert any("unreferenced ids" in error for error in unmapped["errors"])

    figure["source_refs"] = ["manual"]
    mapped = validate_teaching_package(md, html, manifest)
    assert mapped["valid"], mapped["errors"]


def test_visual_status_only_reflects_visual_contract_errors():
    md, html, manifest = current_visual_pair()
    manifest["markdown_extensions"] = ["An unrelated invalid extension"]

    report = validate_teaching_package(md, html, manifest)

    assert not report["valid"]
    assert report["visual_authoring"]["visual_contract_state"] == "current"
    assert report["visual_authoring"]["package_valid"] is False


def store_visual_source(service, session_id, manifest):
    source = manifest["visual_contract"]["research"]["sources"][0]
    saved = service.save_benchmark_report(session_id, "Synthetic visual source fixture", source_refs=[{
        "source_id": source["evidence_source_id"], "source_type": "test_fixture",
        **{key: source[key] for key in ("source", "locator", "excerpt")},
    }], verification={
        "scope": "Synthetic optical sensor registration test",
        "claims": [{"claim": source["excerpt"], "source_index": 0}],
        "worked_examples": [{"problem": "Elapsed time = 2", "solution": "Output = 2",
                             "check_method": "Identity", "check_result": "Equal"}],
        "limitations": ["Fixture is not real research"],
    })
    assert saved["domain_grounding_stage"] == "completed"


@pytest.mark.parametrize("defect", [None, "wrong_session", "not_in_package", "source", "locator", "excerpt"])
def test_visual_registration_uses_matching_session_reading_records(service, defect):
    sid = service.create_session("visual-learner", "Synthetic instrument")["session_id"]
    service.save_knowledge_nodes(sid, [{"node_id": "sensor", "title": "Optical sensor", "unit_tag": "optics"}])
    md, html, manifest = current_visual_pair()
    store_visual_source(service, sid, manifest)
    source = manifest["visual_contract"]["research"]["sources"][0]
    if defect == "wrong_session":
        other = service.create_session("other-learner", "Other topic")["session_id"]
        copy_manifest = copy.deepcopy(manifest)
        copy_manifest["visual_contract"]["research"]["sources"][0]["evidence_source_id"] = "other-source"
        store_visual_source(service, other, copy_manifest)
        manifest["source_ids"] = ["other-source"]
        source["evidence_source_id"] = "other-source"
    elif defect == "not_in_package":
        source["evidence_source_id"] = "not-in-package"
    elif defect:
        source[defect] = "Different source content, not the saved reading record."
        md += "\n" + source[defect]
    before = service.db.scalar("SELECT COUNT(*) FROM artifacts WHERE artifact_type='teaching_package'")
    if defect:
        with pytest.raises(ToolError) as error:
            service.save_teaching_package(sid, "sensor", "physics", md, html, manifest)
        assert error.value.code == "invalid_source"
        assert service.db.scalar("SELECT COUNT(*) FROM artifacts WHERE artifact_type='teaching_package'") == before
    else:
        saved = service.save_teaching_package(sid, "sensor", "physics", md, html, manifest)
        assert saved["validation"]["visual_authoring"]["visual_contract_state"] == "current"
        assert saved["visual_contract_state"] == "current"
        assert isinstance(saved["warnings"], list)
        assert saved["validation"]["content_verified_by_runtime"] is False
        assert service.db.scalar("SELECT COUNT(*) FROM artifacts WHERE artifact_type='teaching_package'") == before + 1


@pytest.mark.parametrize("defect", ["research", "missing_excerpt", "invalid_date", "duplicate_source",
    "unknown_source", "unreferenced_real_part", "missing_part", "unexplained_part", "basis",
    "duplicate_part", "representation", "keyboard", "inspection_panel", "inspection_clear", "check"])
def test_researched_visual_rejects_broken_evidence_and_inspection_records(defect):
    md, html, manifest = researched_visual_pair()
    contract = manifest["visual_contract"]
    figure = contract["figures"][0]
    if defect == "research":
        contract.pop("research")
    elif defect == "missing_excerpt":
        contract["research"]["sources"][0].pop("excerpt")
    elif defect == "invalid_date":
        contract["research"]["sources"][0]["checked_at"] = "2026-02-30"
    elif defect == "duplicate_source":
        contract["research"]["sources"] *= 2
    elif defect == "unknown_source":
        figure["parts"][0]["source_refs"] = ["unread-manual"]
    elif defect == "unreferenced_real_part":
        figure["parts"][0]["source_refs"] = []
    elif defect == "missing_part":
        figure["parts"][0]["selector"] = "#imaginary"
    elif defect == "unexplained_part":
        figure["parts"][0]["explanation"] = "This claim was never included in the lesson."
    elif defect == "basis":
        figure["parts"][0].pop("basis")
    elif defect == "duplicate_part":
        figure["parts"] *= 2
    elif defect == "representation":
        figure["parts"][0]["representation"] = "realistic"
    elif defect == "keyboard":
        html = html.replace('tabindex="0"', 'tabindex="-1"')
    elif defect == "inspection_panel":
        figure["inspection"]["panel"] = "#nonexistent"
    elif defect == "inspection_clear":
        figure["inspection"]["clear"] = "#time"
    else:
        figure["model_binding"]["checks"][0].pop("expected")
    report = validate_teaching_package(md, html, manifest)
    assert not report["valid"], defect
    assert any(error.startswith("visual_contract.") for error in report["errors"]), report


@pytest.mark.parametrize("field,value", [("research", []), ("parts", [None]), ("parts", []),
    ("inspection", []), ("source_refs", [None]), ("checks", [None])])
def test_malformed_research_and_part_records_do_not_crash(field, value):
    md, html, manifest = researched_visual_pair()
    contract = manifest["visual_contract"]
    figure = contract["figures"][0]
    if field == "research":
        contract[field] = value
    elif field == "checks":
        figure["model_binding"][field] = value
    elif field == "source_refs":
        figure["parts"][0][field] = value
    else:
        figure[field] = value
    assert not validate_teaching_package(md, html, manifest)["valid"]


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
    report = validate_teaching_package(md, html, manifest)
    if contract is None:
        # visual_contract: null is documented as equivalent to an absent contract.
        assert report["valid"]
        assert report["visual_authoring"]["visual_contract_state"] == "absent"
    else:
        assert not report["valid"]


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
