"""Host authoring, persistence and export of A4 print materials."""

from __future__ import annotations

import base64
import json
from typing import Any, Literal

from leap.config import resolve_path
from leap.printing import (
    DEFAULT_COURSE_OUTPUT_ROOT, EDITIONS, PrintError, PrintSettings, build_documents,
    course_filename_stem, render_pdf, save_pdf, write_course_files, write_html_editions,
)
from leap.storage import new_id
from leap.tools.base import LeapToolMixin, ToolError

Edition = Literal["combined", "handout", "workbook", "answers"]
Orientation = Literal["portrait", "landscape"]
PDF_LABELS = {**EDITIONS, "combined": "合订册"}


class PrintTools(LeapToolMixin):
    """Keep print drafts as revisioned artifacts tied to a teaching package."""

    def get_print_materials(
        self, session_id: str, node_id: str, *, package_id: str | None = None, material_id: str | None = None,
        include_source: bool = False, include_html: bool = False, html_directory: str | None = None,
    ) -> dict:
        """Find the latest print draft or retrieve a specific revision and its editable HTML.

        Use package_id to select the draft for the teaching package shown to the learner.
        If status is needs_authoring, request include_source=True to read the canonical
        note, teaching points and learning evidence. Use html_directory to write
        all four independent HTML files to a new directory under artifact_root.
        The host authors the illustrated
        handout and fresh questions, and calls save_print_materials.
        """
        row, selected_package_id = self._resolve_print_material(session_id, node_id, package_id, material_id)
        result = {
            "session_id": session_id, "node_id": node_id,
            "status": "ready" if row else "needs_authoring",
            "package_id": selected_package_id,
            "material_id": row["artifact_id"] if row else None,
            "version": row["version"] if row else None,
            "editions": list(EDITIONS),
        }
        if row and (include_html or html_directory):
            draft = json.loads(row["content"])
            documents = self._print_documents(draft, row["version"])
            if include_html:
                result["draft"] = draft
                result["documents"] = documents
            if html_directory:
                directory = self._export_target(html_directory)
                try:
                    write_html_editions(directory, documents)
                except OSError as exc:
                    raise ToolError("print_html_export_failed", f"cannot write print files in {directory}") from exc
                result["html_paths"] = {edition: str(directory / f"{edition}.html") for edition in documents}
        if include_source:
            source_package_id = selected_package_id if package_id or material_id or self.guard.strict_grounding else None
            package = None
            if source_package_id or not self.guard.strict_grounding:
                package = self._print_source(session_id, node_id, source_package_id)
            source = json.loads(package["content"]) if package else {}
            state = self.get_mastery_status(session_id, node_id)
            assessments = self.rows(
                "SELECT ai.question AS prompt, ar.correctness, ar.overall_score, "
                "ar.conceptual_understanding, ar.reasoning_quality, ar.application, "
                "ar.hint_dependency, ar.evidence_stage "
                "FROM assessment_results ar JOIN learning_attempts la ON la.attempt_id=ar.attempt_id "
                "LEFT JOIN assessment_items ai ON ai.item_id=la.item_id "
                "WHERE la.session_id=? AND la.node_id=? ORDER BY ar.created_at DESC, ar.rowid DESC LIMIT 12",
                (session_id, node_id),
            )
            result["source"] = {
                "package_id": package["artifact_id"] if package else None,
                "markdown": source.get("markdown"),
                "teaching_points": source.get("manifest", {}).get("teaching_points", []),
                "learner_state": state.get("learner_state"),
                "assessment_summary": assessments,
            }
        if row is None:
            if self.guard.strict_grounding and selected_package_id is not None:
                from leap.runtime.grounding import print_draft, reviewed_course

                result["next_call"] = {"tool": "save_print_materials", "arguments": {
                    **print_draft(reviewed_course()), "session_id": session_id,
                    "node_id": node_id, "package_id": selected_package_id,
                }}
            elif self.guard.strict_grounding or not include_source:
                result["next_call"] = self._print_authoring_source_call(session_id, node_id, selected_package_id)
        return self.ok(**result)

    def save_print_materials(
        self, session_id: str, node_id: str, package_id: str, title: str,
        handout_html: str, questions: list[dict[str, Any]], *,
        orientation: Orientation = "portrait", margins_mm: list[float] | None = None,
        language: str = "zh-CN", bibliography_html: str | None = None, request_id: str | None = None,
    ) -> dict:
        """Save a print revision with a static handout, questions, and optional bibliography_html.

        Explain terms on first use, show worked steps and reasoning, and include a self-check.
        Each question has point_ids, kind, prompt_html and answer_html. Optional title,
        options_html, answer_area, new_page and continuations control layout.
        The bibliography prints at the end of the handout and combined editions. Include
        enough visible publication and chapter information to find each source on paper.
        Independently solve each question and check it against the handout before saving.
        """
        session = self.require_session(session_id)
        self.require_node(node_id, session_id)
        package = self._print_source(session_id, node_id, package_id)
        if package is None:
            raise ToolError("unknown_teaching_package", "package_id must belong to this session and node")
        content = {"title": title, "handout_html": handout_html, "questions": questions, "language": language}
        if bibliography_html is not None:
            content["bibliography_html"] = bibliography_html
        if self.guard.strict_grounding:
            from leap.runtime.grounding import print_draft, reviewed_course

            grounding = self.require_grounding(session_id)
            self.require_reviewed_package(session_id, package_id, grounding)
            if content != print_draft(reviewed_course()):
                raise ToolError("grounding_unreviewed_content", "Use the reviewed print draft returned by get_grounding_sources")
        manifest = json.loads(package["content"])["manifest"]
        allowed = {point["point_id"] for point in manifest["teaching_points"]}
        covered = set()
        if not isinstance(questions, list) or not 1 <= len(questions) <= 100:
            raise ToolError("invalid_print_material", "provide one to one hundred questions")
        for number, question in enumerate(questions, 1):
            points = question.get("point_ids") if isinstance(question, dict) else None
            if not isinstance(points, list) or not points or any(
                not isinstance(point, str) or point not in allowed for point in points
            ):
                raise ToolError("invalid_print_material", f"question {number} must refer to this package's teaching points")
            covered.update(points)
        material_id = new_id("print")
        version = material_id.removeprefix("print_")
        draft = {
            **content,
            "orientation": orientation, "margins_mm": margins_mm, "package_id": package_id,
        }
        documents = self._print_documents(draft, version)
        if sum(len(html.encode("utf-8")) for html in documents.values()) > 12 * 1024 * 1024:
            raise ToolError("invalid_print_material", "the four print editions exceed 12 MiB")
        metadata = {"node_id": node_id, "package_id": package_id}
        if self.guard.strict_grounding:
            metadata["course_revision"] = grounding["course_revision"]
        self.artifacts.save(
            artifact_id=material_id, session_id=session_id, learner_id=session["learner_id"],
            artifact_type="print_materials", content=json.dumps(draft, ensure_ascii=False),
            metadata=metadata, version=version,
        )
        return self.ok(
            material_id=material_id, version=version, session_id=session_id, node_id=node_id, package_id=package_id,
            covered_point_ids=sorted(covered), uncovered_point_ids=sorted(allowed - covered),
            content_verified_by_runtime=False,
        )

    def export_print_pdf(
        self, session_id: str, node_id: str, *, edition: Edition | None = None,
        package_id: str | None = None, material_id: str | None = None, orientation: Orientation | None = None,
        margins_mm: list[float] | None = None, output_path: str | None = None,
        include_pdf: bool = False,
    ) -> dict:
        """Export the registered teaching HTML and four A4 PDFs to one course-title folder.

        The default root is ~/LEAP/课程输出 (course_output_root). Specify edition
        to export only that PDF alongside the teaching HTML. Use package_id for
        the teaching package shown to the learner. With include_pdf=True return
        a single PDF as base64 bytes for a page download. An explicit output_path
        writes a single PDF under artifact_root and never overwrites. Single PDF
        calls use the combined edition when no edition is supplied.
        """
        if edition is not None and edition not in EDITIONS:
            raise ToolError("invalid_print_material", "unknown print edition")
        selected = edition or "combined"
        row, package_id = self._resolve_print_material(session_id, node_id, package_id, material_id)
        if row is None:
            return self.ok(
                status="needs_authoring", session_id=session_id, node_id=node_id, edition=selected,
                package_id=package_id, next_call=self._print_authoring_source_call(session_id, node_id, package_id),
            )
        draft = json.loads(row["content"])
        title = self.require_node(node_id, session_id)["title"]
        stem = course_filename_stem(title)
        editions = [selected] if edition or include_pdf or output_path else list(EDITIONS)
        names = {key: f"{stem} - {PDF_LABELS[key]}.pdf" for key in editions}
        target = self._export_target(output_path) if output_path else None
        bundle = {}
        try:
            settings = self._print_settings(draft, orientation, margins_mm)
            documents = self._print_documents(draft, row["version"], settings)
            pdfs = {key: render_pdf(documents[key], settings) for key in editions}
            data = pdfs[selected]
            if include_pdf and len(data) > 8 * 1024 * 1024:
                raise PrintError("PDF exceeds the inline limit. Export it to a file instead.")
            if target is not None:
                save_pdf(target, data)
            elif not include_pdf:
                package = self._print_source(session_id, node_id, package_id)
                if package is None or package["artifact_id"] != package_id:
                    raise ToolError("unknown_teaching_package", "the print revision must have its registered teaching package")
                html_name = f"{stem} - 教学课件.html"
                files = {html_name: json.loads(package["content"])["html"].encode("utf-8")}
                files.update({names[key]: payload for key, payload in pdfs.items()})
                root = resolve_path(str(self.conf("course_output_root", DEFAULT_COURSE_OUTPUT_ROOT))).resolve()
                directory = write_course_files(root, stem, files)
                target = directory / names[selected]
                bundle = {
                    "output_directory": str(directory), "html_path": str(directory / html_name),
                    "pdf_paths": {key: str(directory / name) for key, name in names.items()},
                }
        except (PrintError, OSError) as exc:
            raise ToolError("print_export_failed", str(exc)) from exc
        return self.ok(
            status="ready", session_id=session_id, node_id=node_id, edition=selected,
            material_id=row["artifact_id"], package_id=package_id, version=row["version"],
            filename=target.name if target is not None else names[selected],
            orientation=settings.orientation, written_to=str(target) if target is not None else None, **bundle,
            **({"pdf_base64": base64.b64encode(data).decode("ascii")} if include_pdf else {}),
        )

    def _print_authoring_source_call(self, session_id: str, node_id: str, package_id: str | None) -> dict:
        if self.guard.strict_grounding and package_id is None:
            return {"tool": "get_grounding_sources", "arguments": {"session_id": session_id, "include_lesson": True}}
        arguments = {"session_id": session_id, "node_id": node_id, "include_source": True}
        if package_id is not None:
            arguments["package_id"] = package_id
        return {"tool": "get_print_materials", "arguments": arguments}

    def _print_source(
        self, session_id: str, node_id: str, package_id: str | None = None, *, course_revision: str | None = None,
    ):
        return self.db.query_one(
            "SELECT artifact_id, content FROM artifacts WHERE session_id=? "
            "AND artifact_type='teaching_package' AND json_extract(metadata, '$.node_id')=? "
            "AND (? IS NULL OR artifact_id=?) "
            "AND (? IS NULL OR json_extract(metadata, '$.course_revision')=?) ORDER BY rowid DESC LIMIT 1",
            (session_id, node_id, package_id, package_id, course_revision, course_revision),
        )

    def _require_print_package(self, session_id: str, node_id: str, package_id: str, grounding: dict | None):
        if self._print_source(session_id, node_id, package_id) is None:
            raise ToolError("unknown_teaching_package", "package_id must belong to this session and node")
        if grounding is not None:
            self.require_reviewed_package(session_id, package_id, grounding)

    def _resolve_print_material(self, session_id: str, node_id: str, package_id: str | None, material_id: str | None):
        self.require_node(node_id, session_id)
        grounding = self.require_grounding(session_id) if self.guard.strict_grounding else None
        if package_id is not None:
            self._require_print_package(session_id, node_id, package_id, grounding)
        elif material_id is None and grounding is not None:
            package = self._print_source(session_id, node_id, course_revision=grounding["course_revision"])
            if package is None:
                return None, None
            package_id = package["artifact_id"]
            self.require_reviewed_package(session_id, package_id, grounding)

        row = self.db.query_one(
            "SELECT artifact_id, content, version, "
            "coalesce(json_extract(content, '$.package_id'), json_extract(metadata, '$.package_id')) AS package_id "
            "FROM artifacts WHERE session_id=? AND artifact_type='print_materials' "
            "AND json_extract(metadata, '$.node_id')=? "
            "AND (? IS NULL OR artifact_id=?) AND (? IS NULL OR package_id=?) ORDER BY rowid DESC LIMIT 1",
            (session_id, node_id, material_id, material_id,
             package_id if material_id is None else None, package_id),
        )
        if row is None:
            if material_id is not None:
                raise ToolError("unknown_print_material", "material_id must belong to this session and node")
            return None, package_id
        material_package_id = row["package_id"]
        if package_id is not None and material_package_id != package_id:
            raise ToolError("print_package_mismatch", "material_id must belong to the requested teaching package", {
                "package_id": package_id, "material_id": material_id, "material_package_id": material_package_id,
            })
        if package_id is None and grounding is not None:
            self.require_reviewed_package(session_id, material_package_id, grounding)
            self._require_print_package(session_id, node_id, material_package_id, None)
        return row, material_package_id

    @staticmethod
    def _print_settings(draft, orientation=None, margins_mm=None) -> PrintSettings:
        return PrintSettings(
            orientation if orientation is not None else draft["orientation"],
            margins_mm if margins_mm is not None else
            (draft["margins_mm"] if draft["margins_mm"] is not None else PrintSettings().margins_mm),
        )

    def _print_documents(self, draft, version, settings=None):
        try:
            return build_documents(
                draft["title"], draft["handout_html"], draft["questions"], version=version,
                settings=settings or self._print_settings(draft), language=draft["language"],
                bibliography_html=draft.get("bibliography_html"),
            )
        except PrintError as exc:
            raise ToolError("invalid_print_material", str(exc)) from exc
