# -*- coding: utf-8 -*-
"""Regression tests for the enforced anatomy.v2 contract (review fix batch)."""
import copy
import json
import time
from pathlib import Path

import pytest

import leap.runtime.delivery as delivery
from leap.runtime.delivery import (
    html_teaching_text,
    normalize_text,
    validate_teaching_package,
    validate_visual_source_links,
)
from leap.tools import ToolError
from scripts.verify_teaching_repository import simulate_registration
from tests.conftest import complete_grounding
from tests.test_teaching_delivery import (
    current_visual_pair,
    teaching_pair,
    visual_pair,
)

SOURCE_FIELDS = ("source", "locator", "excerpt")
SOURCE_ID = "src.anatomy.review"


def _ground(service, learner="anatomy-v2-learner", topic="Synthetic instrument"):
    """Session whose latest benchmark report contains the v2 fixture source."""
    sid = service.create_session(learner, topic)["session_id"]
    report = service.save_benchmark_report(
        sid, "# Synthetic baseline\n\nElapsed time identity.",
        source_refs=[{"source_id": SOURCE_ID,
                      "source": "https://example.org/instrument-manual",
                      "source_type": "manual", "locator": "Assembly, optical sensor",
                      "excerpt": "The object interrupts a light beam."}],
        verification={"scope": "synthetic anatomy fixture",
                      "claims": [{"claim": "elapsed time identity", "source_index": 0}],
                      "worked_examples": [{"problem": "p", "solution": "s",
                                           "check_method": "m", "check_result": "r"}],
                      "limitations": []})
    assert report["domain_grounding_stage"] == "completed"
    service.save_knowledge_nodes(
        sid, [{"node_id": "sensor", "title": "Synthetic sensor", "unit_tag": "optics"}])
    return sid


def _v2_manifest_with_source(manifest, source_id):
    manifest = copy.deepcopy(manifest)
    research_source = manifest["visual_contract"]["research"]["sources"][0]
    research_source["evidence_source_id"] = source_id
    manifest["source_ids"] = [source_id]
    return manifest


def _register(service, sid, md, html, manifest):
    return service.save_teaching_package(sid, "sensor", "physics", md, html, manifest)


# ------------------------------------------------------------------ P1-1 enforcement
def test_new_package_requires_v2_or_explicit_opt_in_or_text_only(service):
    sid = _ground(service)
    md, html, legacy_manifest = visual_pair()
    legacy_manifest = copy.deepcopy(legacy_manifest)
    legacy_manifest["source_ids"] = [
        row["source_id"] for row in service.rows(
            "SELECT source_id FROM evidence_sources WHERE session_id=?", (sid,))]

    with pytest.raises(ToolError) as error:
        _register(service, sid, md, html, legacy_manifest)
    assert error.value.code == "visual_contract_required"
    assert error.value.details["is_new"] is True
    assert error.value.details["visual_contract_state"] == "legacy_v1"

    explicit = copy.deepcopy(legacy_manifest)
    explicit["allow_legacy"] = True
    saved = _register(service, sid, md, html, explicit)
    assert saved["ok"] is True
    assert saved["visual_contract_state"] == "legacy_v1"
    assert saved["warnings"] and "legacy" in saved["warnings"][0]
    row = service.db.query_one(
        "SELECT metadata FROM artifacts WHERE artifact_id=?", (saved["package_id"],))
    stored = json.loads(row["metadata"])
    assert stored["allow_legacy"] is True
    assert stored["visual_contract_state"] == "legacy_v1"


def test_revised_package_cannot_silently_downgrade_an_accepted_v2_package(service):
    sid = _ground(service)
    md, html, current = current_visual_pair()
    current = _v2_manifest_with_source(current, SOURCE_ID)
    _register(service, sid, md, html, current)

    md, html, legacy_manifest = visual_pair()
    legacy_manifest = copy.deepcopy(legacy_manifest)
    legacy_manifest["source_ids"] = [SOURCE_ID]
    with pytest.raises(ToolError) as error:
        _register(service, sid, md, html, legacy_manifest)
    assert error.value.code == "visual_contract_required"
    assert error.value.details["prior_current_contract"] is True


def test_text_only_lesson_needs_no_visual_contract_and_reports_not_applicable(service):
    sid = _ground(service)
    md, html, manifest = teaching_pair()
    manifest = copy.deepcopy(manifest)
    manifest["teaching_points"][0]["visualization"] = {
        "no_visual_reason": "This lesson is pure symbolic derivation; no diagram reveals structure."}
    manifest["source_ids"] = [
        row["source_id"] for row in service.rows(
            "SELECT source_id FROM evidence_sources WHERE session_id=?", (sid,))]
    report = validate_teaching_package(md, html, manifest)
    assert report["valid"], report["errors"]
    assert report["visual_authoring"]["visual_contract_state"] == "not_applicable"
    assert report["visual_authoring"]["text_only"] is True
    saved = _register(service, sid, md, html, manifest)
    assert saved["ok"] is True
    assert saved["visual_contract_state"] == "not_applicable"
    assert any("text-only" in warning for warning in saved["warnings"])


# ------------------------------------------------------------------ P1-2 content floor
@pytest.mark.parametrize("mutate,field", [
    (lambda contract, figure: figure.update(caption="a"), "caption"),
    (lambda contract, figure: figure["parts"][0].update(explanation="a"), "explanation"),
    (lambda contract, figure: figure.update(labels=["a"]), "labels"),
])
def test_placeholder_one_character_records_are_rejected(mutate, field):
    md, html, manifest = current_visual_pair()
    figure = manifest["visual_contract"]["figures"][0]
    mutate(manifest["visual_contract"], figure)
    report = validate_teaching_package(md, html, manifest)
    assert not report["valid"]
    assert any(field in error for error in report["errors"]), report["errors"]


def test_quantities_must_appear_in_canonical_markdown():
    md, html, manifest = current_visual_pair()
    manifest["visual_contract"]["figures"][0]["model_binding"]["quantities"][0]["name"] = "never-written-quantity"
    report = validate_teaching_package(md, html, manifest)
    assert not report["valid"]
    assert any("quantity.name must appear" in error for error in report["errors"])


# ------------------------------------------------------------------ P1-3 controllable figure
def test_static_data_package_cannot_claim_a_visual_delivery():
    md, html, manifest = current_visual_pair()
    figure = manifest["visual_contract"]["figures"][0]
    figure.update(role="data", animated=False, selector="#rig")
    figure.pop("states")
    for field in ("parts", "inspection", "model_binding", "controls"):
        figure.pop(field)
    figure["source_refs"] = ["manual"]
    report = validate_teaching_package(md, html, manifest)
    assert not report["valid"]
    assert any("controllable figure" in error for error in report["errors"]), report["errors"]


def test_controls_or_states_require_animated():
    md, html, manifest = current_visual_pair()
    figure = manifest["visual_contract"]["figures"][0]
    figure["animated"] = False
    report = validate_teaching_package(md, html, manifest)
    assert any("controls requires animated=true" in error for error in report["errors"])
    assert any("states requires animated=true" in error for error in report["errors"])


def test_figure_selector_cannot_be_plain_prose_div():
    md, html, manifest = current_visual_pair()
    manifest["visual_contract"]["figures"][0]["selector"] = "#trace"
    report = validate_teaching_package(md, html, manifest)
    assert any("enabled visible element of type" in error for error in report["errors"])
    assert any("selector" in error for error in report["errors"])


# ------------------------------------------------------------------ P2-5 selectors / tags
def test_part_selector_accepts_geometry_tags_and_unicode_ids():
    for tag, attrs in (
            ("line", 'x1="0" y1="0" x2="9" y2="9"'),
            ("ellipse", 'cx="5" cy="5" rx="3" ry="3"'),
            ("use", 'href="#sensor-def"')):
        md, html, manifest = current_visual_pair()
        original = '<g id="sensor" role="button" tabindex="0" aria-label="Optical sensor"></g>'
        assert original in html
        replacement = (f'<{tag} id="sensor" role="button" tabindex="0" '
                       f'aria-label="Optical sensor" {attrs}></{tag}>')
        html = html.replace(original, replacement)
        report = validate_teaching_package(md, html, manifest)
        assert not [error for error in report["errors"] if "parts.selector" in error], (tag, report["errors"])


def test_part_selector_accepts_digit_and_cjk_ids():
    md, html, manifest = current_visual_pair()
    original = '<g id="sensor" role="button" tabindex="0" aria-label="Optical sensor"></g>'
    html = html.replace(original, '<g id="2光敏部件" role="button" tabindex="0" aria-label="Optical sensor"></g>')
    manifest["visual_contract"]["figures"][0]["parts"][0]["selector"] = "#2光敏部件"
    report = validate_teaching_package(md, html, manifest)
    assert not [error for error in report["errors"] if "parts.selector" in error], report["errors"]


def test_hidden_ancestor_targets_are_rejected():
    md, html, manifest = current_visual_pair()
    html = html.replace('<button id="play">', '<div hidden><button id="play">')
    html = html.replace('</button><button id="reset">', '</button></div><button id="reset">')
    report = validate_teaching_package(md, html, manifest)
    assert any("#play exists but is hidden" in error for error in report["errors"]), report["errors"]


def test_selector_syntax_errors_are_distinct_from_missing_ids():
    md, html, manifest = current_visual_pair()
    manifest["visual_contract"]["figures"][0]["selector"] = "#rig .missing-class"
    report = validate_teaching_package(md, html, manifest)
    assert any("must be a single #id" in error for error in report["errors"])
    assert not any("no element with id" in error for error in report["errors"])


# ------------------------------------------------------------------ P2-6 visible text
def test_nonrendered_subtrees_are_not_visible_teaching_text(tmp_path):
    md, html, manifest = teaching_pair()
    extra = ('<template><p>templated runtime text</p></template>'
             '<p style="display:none">inline hidden text</p>'
             '<noscript>noscript text</noscript>'
             '<svg><title>svg tooltip</title><desc>svg description</desc></svg>')
    html = html.replace("</body>", extra + "</body>")
    report = validate_teaching_package(md, html, manifest)
    assert report["valid"], report["errors"]
    visible = html_teaching_text(html)
    for hidden_text in ("templated runtime text", "inline hidden text", "noscript text",
                        "svg tooltip", "svg description"):
        assert normalize_text(hidden_text) not in normalize_text(visible)


# ------------------------------------------------------------------ P3 statuses / keys / policy
def test_status_fields_are_split_and_package_valid_is_independent():
    md, html, manifest = current_visual_pair()
    report = validate_teaching_package(md, html, manifest)
    visual = report["visual_authoring"]
    assert visual["visual_contract_state"] == "current"
    assert visual["visual_contract_valid"] is True
    assert visual["package_valid"] is True
    assert report["valid"] is True
    assert visual["browser_behavior_verified_by_runtime"] is False

    manifest["markdown_extensions"] = ["An unrelated invalid extension"]
    broken = validate_teaching_package(md, html, manifest)["visual_authoring"]
    assert broken["visual_contract_state"] == "current"
    assert broken["package_valid"] is False


def test_unknown_manifest_and_contract_fields_are_rejected():
    md, html, manifest = current_visual_pair()
    manifest = copy.deepcopy(manifest)
    contract = manifest.pop("visual_contract")
    manifest["visualContract"] = contract
    report = validate_teaching_package(md, html, manifest)
    assert any("'visual_contract'" in error for error in report["errors"])

    manifest = copy.deepcopy(current_visual_pair()[2])
    manifest["unexpected_top_level"] = True
    assert any("unknown field" in error for error in
               validate_teaching_package(md, html, manifest)["errors"])

    manifest = copy.deepcopy(current_visual_pair()[2])
    manifest["visual_contract"]["unexpected_contract_field"] = True
    assert any("unknown field" in error for error in
               validate_teaching_package(md, html, manifest)["errors"])


def test_visual_contract_null_equals_absent():
    md, html, manifest = teaching_pair()
    manifest = copy.deepcopy(manifest)
    manifest["visual_contract"] = None
    report = validate_teaching_package(md, html, manifest)
    assert report["valid"], report["errors"]
    assert report["visual_authoring"]["visual_contract_state"] == "absent"


def test_v2_manifest_requires_policy_identity():
    md, html, manifest = current_visual_pair()
    manifest = copy.deepcopy(manifest)
    manifest.pop("policy_version")
    report = validate_teaching_package(md, html, manifest)
    assert not report["valid"]
    assert any("policy_version" in error for error in report["errors"])


def test_policy_reloads_when_the_file_changes(tmp_path, monkeypatch):
    source = json.loads(delivery.POLICY_FILE.read_text(encoding="utf-8"))
    policy_copy = tmp_path / "policy.json"
    source["version"] = "9.9"
    policy_copy.write_text(json.dumps(source), encoding="utf-8")
    monkeypatch.setattr(delivery, "POLICY_FILE", policy_copy)
    try:
        assert delivery._policy()["version"] == "9.9"
        time.sleep(0.02)
        source["version"] = "9.8"
        policy_copy.write_text(json.dumps(source), encoding="utf-8")
        assert delivery._policy()["version"] == "9.8"
        assert delivery.reload_policy()["version"] == "9.8"
    finally:
        monkeypatch.undo()
        delivery.reload_policy()


# ------------------------------------------------------------------ P2-8 source binding
def test_research_must_come_from_the_latest_completed_report(service):
    sid = _ground(service)
    # Second grounding report: only the new source is in the latest report.
    second = service.save_benchmark_report(
        sid, "# Second baseline\n\nElapsed time identity.",
        source_refs=[{"source_id": "src.latest", "source": "https://example.org/latest",
                      "source_type": "manual", "locator": "Latest section",
                      "excerpt": "Latest excerpt for the second grounding pass."}],
        verification={"scope": "synthetic latest pass",
                      "claims": [{"claim": "latest", "source_index": 0}],
                      "worked_examples": [{"problem": "p", "solution": "s",
                                           "check_method": "m", "check_result": "r"}],
                      "limitations": []})
    assert second["domain_grounding_stage"] == "completed"
    md, html, manifest = current_visual_pair()
    manifest = copy.deepcopy(manifest)
    manifest["source_ids"] = [SOURCE_ID]  # exists in session but not in the latest report
    with pytest.raises(ToolError) as error:
        _register(service, sid, md, html, manifest)
    assert error.value.code == "invalid_source"
    errors = error.value.details["errors"] if isinstance(error.value.details, dict) else []
    assert any("latest completed benchmark report" in item for item in errors), errors


def test_research_checked_at_cannot_be_in_the_future():
    md, html, manifest = current_visual_pair()
    manifest["visual_contract"]["research"]["sources"][0]["checked_at"] = "2999-01-01"
    md += "\n2999-01-01"
    report = validate_teaching_package(md, html, manifest)
    assert any("must not be in the future" in error for error in report["errors"])


def test_visual_source_links_defend_against_unreadable_records():
    manifest = {"visual_contract": {"profile": "anatomy.v2", "research": {"sources": [{
        "id": "primary", "evidence_source_id": "src.bad", "source": "s", "locator": "l",
        "excerpt": "e", "checked_at": "2026-10-23"}]}}}
    errors = validate_visual_source_links(manifest, {"src.bad": {"source": "s", "metadata": "not-json"}})
    assert errors and "unreadable" in errors[0]
    missing = validate_visual_source_links(manifest, {})
    assert missing and "session source_ids" in missing[0]
    no_sources = validate_visual_source_links(
        {"visual_contract": {"profile": "anatomy.v2", "research": {}}}, {})
    assert no_sources


# ------------------------------------------------------------------ repository gate
def test_all_shipped_examples_register_through_the_public_tool_path():
    root = Path(__file__).resolve().parents[1]
    examples = sorted((root / "examples").glob("*/*.html"))
    assert len(examples) == 8
    states = {}
    for page in examples:
        note = page.parent / "knowledge.md"
        manifest = json.loads(page.with_suffix(".delivery.json").read_text(encoding="utf-8"))
        assert manifest["source_ids"] == ["<source id returned by save_benchmark_report>"]
        result = simulate_registration(page, note.read_text(encoding="utf-8"),
                                       page.read_text(encoding="utf-8"), manifest)
        assert result["ok"], (page.name, result)
        states[page.parent.name] = result["visual_contract_state"]
    assert states["04-physics-free-fall"] == "current"
    assert all(state in {"absent", "legacy_v1"} for name, state in states.items()
               if name != "04-physics-free-fall")


def test_gate_keeps_frontmatter_checks_but_exempts_public_docs(tmp_path, monkeypatch):
    from scripts import verify_teaching_repository as verifier

    readme = tmp_path / "README.md"
    readme.write_text(
        "---\ntitle: readme\ntags: [leap]\naliases: [readme]\n---\n\n"
        "> [!info]- Learning resources\n> Core query one.\n\n"
        "See [docs](docs/index.md) for details.\n", encoding="utf-8")
    note = tmp_path / "docs" / "plain.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\ntitle: plain\ntags: [leap]\naliases: [plain]\n---\n\n"
        "> [!info]- Learning resources\n> Core query one.\n\nNo links here.\n",
        encoding="utf-8")

    def fake_git(*args, **kwargs):
        return b"README.md\0docs/plain.md\0"

    monkeypatch.setattr(verifier.subprocess, "check_output", fake_git)
    report = verifier.verify(tmp_path)
    assert not [error for error in report["errors"] if "README" in error]
    assert any(error.startswith("docs/plain: no wikilinks") for error in report["errors"])


def test_export_session_data_stays_inside_the_artifact_root(tmp_path):
    from leap.tools import build_service

    root = tmp_path / "artifacts"
    service = build_service(":memory:", {"artifact_root": str(root)})
    try:
        sid = service.create_session("exporter", "export fixture")["session_id"]
        relative = service.export_session_data(sid, output_path="session.json")["export"]
        target = Path(relative["written_to"])
        assert target.is_file()
        assert root.resolve() in target.parents

        absolute = (root / "nested" / "abs.json").resolve()
        service.export_session_data(sid, output_path=str(absolute))
        assert absolute.is_file()

        for bad in ("../escape.json", str(tmp_path / "escape.json"), "/etc/passwd"):
            with pytest.raises(ToolError) as error:
                service.export_session_data(sid, output_path=bad)
            assert error.value.code == "invalid_path"
    finally:
        service.close()
