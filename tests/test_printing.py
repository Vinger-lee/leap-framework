"""Exercise separate print editions and the host-facing persistence contract."""
import base64
from pathlib import Path

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


def test_bibliography_follows_the_printed_content():
    docs = build_documents("Linear equations", "<p>Worked example</p>", [question()],
                           version="V1", bibliography_html="<p>Printed reference entry</p>")
    assert docs["handout"].index("Worked example") < docs["handout"].index("Printed reference entry")
    assert docs["combined"].index("4x + 2") < docs["combined"].index("Printed reference entry")
    assert "Printed reference entry" not in docs["workbook"]
    assert "Printed reference entry" not in docs["answers"]
    with pytest.raises(PrintError, match="script"):
        build_documents("Linear equations", "<p>Worked example</p>", [question()],
                        version="V1", bibliography_html="<script>0</script>")


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

    svc = build_service(":memory:", {"artifact_root": str(tmp_path)}, strict_grounding=False)
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


def test_default_print_export_groups_named_courseware_in_its_own_folder(
    grounded_service, dag, tmp_path, monkeypatch,
):
    from leap.tools import printing
    from tests.teaching_fixture import teaching_pair

    root = tmp_path / "课程输出"
    monkeypatch.setenv("LEAP_HOME", str(tmp_path))
    conf = grounded_service.conf
    monkeypatch.setattr(grounded_service, "conf", lambda key, default=None:
                        str(root) if key == "course_output_root" else conf(key, default))
    monkeypatch.setattr(printing, "render_pdf", lambda document, settings: document.encode("utf-8"))
    node_id = "print.course"
    package = register_pair(grounded_service, dag, node_id=node_id)
    grounded_service.save_knowledge_nodes(dag, [{"node_id": node_id, "title": "高数/极限：入门"}])
    draft = grounded_service.save_print_materials(dag, node_id, package, "讲义封面", "<p>Paper</p>", [question()])

    receipt = grounded_service.export_print_pdf(dag, node_id, package_id=package)
    title = "高数-极限：入门"
    directory = root / title
    assert Path(receipt["output_directory"]) == directory
    assert receipt["package_id"] == package and receipt["material_id"] == draft["material_id"]
    html_path = directory / f"{title} - 教学课件.html"
    assert Path(receipt["html_path"]) == html_path
    assert html_path.read_text(encoding="utf-8") == teaching_pair()[1]
    expected_pdfs = {edition: directory / f"{title} - {name}.pdf" for edition, name in {
        "combined": "合订册", "handout": "讲义册", "workbook": "题目册", "answers": "答案与解析",
    }.items()}
    assert {key: Path(value) for key, value in receipt["pdf_paths"].items()} == expected_pdfs
    assert sorted(directory.iterdir()) == sorted([html_path, *expected_pdfs.values()])
    assert receipt["written_to"] == str(expected_pdfs["combined"])
    assert b"Answer marker" not in expected_pdfs["workbook"].read_bytes()
    assert b"Answer marker" in expected_pdfs["answers"].read_bytes()

    repeat = grounded_service.export_print_pdf(dag, node_id, package_id=package, edition="answers")
    repeat_directory = root / f"{title} (2)"
    assert Path(repeat["output_directory"]) == repeat_directory
    assert sorted(path.name for path in repeat_directory.iterdir()) == [
        f"{title} - 教学课件.html", f"{title} - 答案与解析.pdf",
    ]
    assert sorted(directory.iterdir()) == sorted([html_path, *expected_pdfs.values()])


def test_explicit_package_selects_its_draft_even_when_another_package_has_the_latest(
    grounded_service, dag, monkeypatch,
):
    from leap.tools import printing

    monkeypatch.setattr(printing, "render_pdf", lambda document, settings: document.encode("utf-8"))
    node_id = "print.bound"
    package = register_pair(grounded_service, dag, node_id=node_id)
    older = grounded_service.save_print_materials(dag, node_id, package, "Earlier lesson", "<p>Earlier handout</p>", [question()])
    updated = register_pair(grounded_service, dag, node_id=node_id)
    newest = grounded_service.save_print_materials(dag, node_id, updated, "Newer lesson", "<p>Newer handout</p>", [question()])
    assert package != updated
    assert grounded_service.get_print_materials(dag, node_id)["material_id"] == newest["material_id"]

    result = grounded_service.get_print_materials(dag, node_id, package_id=package, include_source=True)
    export = grounded_service.export_print_pdf(dag, node_id, package_id=package, include_pdf=True)
    assert result["source"]["package_id"] == package
    for receipt in (older, result, export):
        assert receipt["package_id"] == package
        assert receipt["material_id"] == older["material_id"]
    assert b"Earlier handout" in base64.b64decode(export["pdf_base64"])

    for method in (grounded_service.get_print_materials, grounded_service.export_print_pdf):
        with pytest.raises(ToolError) as exc:
            method(dag, node_id, package_id=package, material_id=newest["material_id"])
        assert exc.value.code == "print_package_mismatch"
        with pytest.raises(ToolError) as exc:
            method(dag, "n1", package_id=package)
        assert exc.value.code == "unknown_teaching_package"


@pytest.mark.parametrize("storage_field", ["content", "metadata"])
def test_scoped_get_reads_package_binding_from_older_drafts(grounded_service, dag, storage_field):
    node_id = "print.legacy"
    package_id = register_pair(grounded_service, dag, node_id=node_id)
    saved = grounded_service.save_print_materials(
        dag, node_id, package_id, "Lesson", "<p>Existing handout</p>", [question()],
    )
    if storage_field == "content":
        update = "UPDATE artifacts SET metadata=json_remove(metadata, '$.package_id') WHERE artifact_id=?"
    else:
        update = "UPDATE artifacts SET content=json_remove(content, '$.package_id') WHERE artifact_id=?"
    grounded_service.db.execute(update, (saved["material_id"],))
    material = grounded_service.get_print_materials(dag, node_id, package_id=package_id, include_html=True)
    assert material["material_id"] == saved["material_id"]
    assert material["package_id"] == package_id
    assert "Existing handout" in material["documents"]["handout"]


def test_strict_print_recovery_stays_with_current_reviewed_package():
    from leap.tools import build_service

    svc = build_service(":memory:")
    try:
        session_id = svc.start_learning("student", "高数")["session_id"]
        evidence = svc.get_grounding_sources(session_id)
        svc.save_benchmark_report(
            session_id, "Derivation and sided limits checked", course_revision=evidence["course_revision"],
            chunk_ids=[record["chunk_id"] for record in evidence["sources"]],
            check_answers={"jump": "does_not_exist", "square_at_two": "4", "absolute_at_zero": "-1,1"},
        )
        lesson = svc.get_grounding_sources(session_id, include_lesson=True)["lesson"]
        node_id = lesson["node"]["node_id"]
        svc.save_knowledge_nodes(session_id, [lesson["node"]])
        lesson_arguments = {key: lesson[key] for key in ("subject", "markdown", "html", "manifest")}
        previous = svc.save_teaching_package(session_id, node_id, **lesson_arguments)["package_id"]
        stale_draft = svc.save_print_materials(session_id, node_id, previous, **lesson["print_draft"])

        # Simulate a draft and package carried forward from a previous course revision.
        svc.db.execute(
            "UPDATE artifacts SET metadata=json_set(metadata, '$.course_revision', 'previous') "
            "WHERE artifact_id IN (?, ?)", (previous, stale_draft["material_id"]),
        )
        current = svc.save_teaching_package(session_id, node_id, **lesson_arguments)["package_id"]
        assert previous != current

        result = svc.export_print_pdf(session_id, node_id)
        assert result["status"] == "needs_authoring"
        assert result["package_id"] == current
        lookup = result["next_call"]
        assert lookup["tool"] == "get_print_materials"
        assert lookup["arguments"]["package_id"] == current
        draft = svc.get_print_materials(**lookup["arguments"])
        assert draft["status"] == "needs_authoring"
        assert draft["package_id"] == current == draft["source"]["package_id"]
        recovery = draft["next_call"]
        assert recovery["tool"] == "save_print_materials"
        assert recovery["arguments"]["package_id"] == current
        saved = svc.save_print_materials(**recovery["arguments"])
        assert svc.get_print_materials(session_id, node_id)["material_id"] == saved["material_id"]

        for scope in ({"package_id": previous}, {"material_id": stale_draft["material_id"]}):
            for method in (svc.get_print_materials, svc.export_print_pdf):
                with pytest.raises(ToolError) as exc:
                    method(session_id, node_id, **scope)
                assert exc.value.code == "grounding_unreviewed_content"
    finally:
        svc.close()


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
