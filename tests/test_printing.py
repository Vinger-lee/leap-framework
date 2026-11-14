"""Exercise separate print editions and the host-facing persistence contract."""
import pytest

from leap.printing import PrintError, PrintSettings, build_documents, render_pdf, save_pdf
from leap.tools import ToolError
from tests.teaching_fixture import register_pair


def question(**extra):
    return {
        "point_ids": ["fixture.equation"], "kind": "calculation",
        "prompt_html": "<p>Find x for 4x + 2 = 18.</p>",
        "answer_html": "<p>Answer marker: x = 4. Substitution gives 18.</p>",
        **extra,
    }


def test_editions_are_independent_and_aligned():
    docs = build_documents("Linear equations", '<section><h2>Balance</h2><p>Keep both sides equal.</p></section>',
                           [question(answer_area={"type": "grid", "height_mm": 35})], version="V1")
    assert set(docs) == {"handout", "workbook", "combined", "answers"}
    assert "Balance" in docs["handout"] and "4x + 2" not in docs["handout"]
    assert "4x + 2" in docs["workbook"] and "answer-grid" in docs["workbook"]
    assert docs["combined"].index("Balance") < docs["combined"].index("4x + 2")
    assert "print-new-page" in docs["combined"]
    assert "Answer marker:" not in docs["workbook"] and "Answer marker:" not in docs["combined"]
    assert "Answer marker:" in docs["answers"]
    assert "<pattern" in docs["workbook"]
    assert 'data-question="1"' in docs["answers"] and 'data-question="1"' in docs["workbook"]
    assert all("V1" in doc for doc in docs.values())


def test_print_settings_validate_paper_geometry():
    assert PrintSettings().page_rule() == "@page { size: A4 portrait; margin: 16mm 16mm 16mm 16mm; }"
    assert "A4 landscape" in PrintSettings("landscape", (8, 9, 10, 11)).page_rule()
    with pytest.raises(PrintError):
        PrintSettings("portrait", (100, 150, 90, 150))
    with pytest.raises(PrintError):
        PrintSettings("wrong")


def test_runtime_reuses_print_draft_and_provides_source(grounded_service, dag):
    package = register_pair(grounded_service, dag, node_id="print.eq")
    ctx = grounded_service.get_print_materials(dag, "print.eq", include_source=True)
    assert ctx["status"] == "needs_authoring"
    assert ctx["source"]["package_id"] == package
    assert "equivalent equation" in ctx["source"]["markdown"]
    assert ctx["source"]["teaching_points"][0]["point_id"] == "fixture.equation"

    first = grounded_service.save_print_materials(dag, "print.eq", package, "Equations",
                                                 "<p>Worked example</p>", [question()])
    second = grounded_service.save_print_materials(dag, "print.eq", package, "Equations",
                                                  "<p>Edited example</p>", [question()])
    assert first["material_id"] != second["material_id"]
    assert first["version"] != second["version"]
    assert grounded_service.get_print_materials(dag, "print.eq")["material_id"] == second["material_id"]
    old = grounded_service.get_print_materials(dag, "print.eq", material_id=first["material_id"],
                                               include_html=True)
    assert "Worked example" in old["documents"]["handout"]
    assert "Edited example" not in old["documents"]["handout"]
    with pytest.raises(ToolError):
        grounded_service.save_print_materials(dag, "print.eq", package, "Equations", "<p>Early draft</p>",
                                              [question(point_ids=["unknown"])])


def test_invalid_print_content_rejected():
    with pytest.raises(PrintError):
        build_documents("Equations", "<p>Lesson</p>", [question(answer_area={"type": "invalid"})], version="V1")
    with pytest.raises(PrintError):
        build_documents("Equations", '<script>alert(1)</script>', [question()], version="V1")
    with pytest.raises(PrintError):
        build_documents("Equations", '<p>Lesson</p>', [question(answer_html="")], version="V1")


@pytest.mark.parametrize(("kind", "marker"), [
    ("single_choice", "answer-choices"), ("multiple_choice", "answer-choices"),
    ("true_false", "answer-choices"), ("fill_blank", "answer-blank"),
    ("short_answer", "answer-lines"), ("calculation", "answer-space"),
    ("proof", "answer-space"), ("geometry", "answer-grid"), ("graphing", "answer-axes"),
    ("coding", "answer-code"), ("experiment", "answer-table"),
])
def test_subject_answer_areas(kind, marker):
    kwargs = {"options_html": ["A choice", "Another choice"]} if kind in {"single_choice", "multiple_choice"} else {}
    html = build_documents("Lesson", "<p>Handout</p>", [question(kind=kind, **kwargs)], version="v")["workbook"]
    assert f'class="{marker}"' in html


def test_pdf_save_requires_explicit_overwrite(tmp_path):
    target = tmp_path / "one.pdf"
    save_pdf(target, b"%PDF-first")
    with pytest.raises(PrintError, match="already exists"):
        save_pdf(target, b"%PDF-second")
    assert target.read_bytes() == b"%PDF-first"
    save_pdf(target, b"%PDF-second", overwrite=True)
    assert target.read_bytes() == b"%PDF-second"
    assert list(tmp_path.iterdir()) == [target]


def test_html_editing_files_are_materialized_and_answer_separated(tmp_path):
    from pathlib import Path

    from leap.tools import build_service
    from tests.conftest import complete_grounding

    svc = build_service(":memory:", {"artifact_root": str(tmp_path)})
    try:
        session_id = svc.create_session("reader", "equations")["session_id"]
        complete_grounding(svc, session_id)
        package = register_pair(svc, session_id)
        draft = svc.save_print_materials(session_id, "fixture.equation", package, "Lesson", "<p>Handout</p>", [question()])
        response = svc.get_print_materials(session_id, "fixture.equation", html_directory="print-draft")
        assert response["material_id"] == draft["material_id"]
        assert "Answer marker" not in Path(response["html_paths"]["workbook"]).read_text(encoding="utf-8")
        assert "Answer marker" in Path(response["html_paths"]["answers"]).read_text(encoding="utf-8")
        with pytest.raises(ToolError) as exc:
            svc.get_print_materials(session_id, "fixture.equation", html_directory="../outside")
        assert exc.value.code == "invalid_path"
    finally:
        svc.close()


def test_saved_print_revisions_keep_their_source(grounded_service, dag):
    package = register_pair(grounded_service, dag, node_id="print.source")
    draft = grounded_service.save_print_materials(dag, "print.source", package, "Lesson", "<p>Handout</p>", [question()])
    from tests.teaching_fixture import teaching_pair
    markdown, html, manifest = teaching_pair()
    manifest["source_ids"] = [
        row["source_id"] for row in grounded_service.rows(
            "SELECT source_id FROM evidence_sources WHERE session_id=?", (dag,)
        )
    ]
    updated = grounded_service.save_teaching_package(
        dag, "print.source", "math", markdown, html, manifest
    )["package_id"]
    assert updated != package
    latest = grounded_service.get_print_materials(dag, "print.source", include_source=True)
    historical = grounded_service.get_print_materials(
        dag, "print.source", include_source=True, material_id=draft["material_id"],
    )
    assert latest["source"]["package_id"] == updated
    assert historical["source"]["package_id"] == package


def test_generated_editions_fit_the_renderer_limit(monkeypatch):
    from leap import printing

    baseline = build_documents("Title", "<p>Lesson</p>", [question()], version="V1")
    size = max(len(doc.encode("utf-8")) for doc in baseline.values())
    monkeypatch.setattr(printing, "MAX_HTML_BYTES", size + 180)
    with pytest.raises(PrintError, match="combined"):
        build_documents(
            "Title", "<p>" + "h" * 140 + "</p>",
            [question(prompt_html="<p>" + "q" * 140 + "</p>")], version="V1",
        )
