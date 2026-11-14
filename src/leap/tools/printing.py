"""Host authoring, persistence and export of A4 print materials."""

from __future__ import annotations

import base64
import json
from typing import Any, Literal

from leap.printing import (
    EDITIONS, PrintError, PrintSettings, build_documents, render_pdf, save_pdf, write_html_editions,
)
from leap.storage import new_id
from leap.tools.base import LeapToolMixin, ToolError

Edition = Literal["combined", "handout", "workbook", "answers"]
Orientation = Literal["portrait", "landscape"]


class PrintTools(LeapToolMixin):
    """Keep print drafts as revisioned artifacts tied to a teaching package."""

    def get_print_materials(
        self, session_id: str, node_id: str, *, material_id: str | None = None,
        include_source: bool = False, include_html: bool = False, html_directory: str | None = None,
    ) -> dict:
        """Find the latest print draft or retrieve a specific revision and its editable HTML.

        If status is needs_authoring, request include_source=True to read the canonical
        note, teaching points and learning evidence. Use html_directory to write
        all four independent HTML files to a new directory under artifact_root.
        The host authors the illustrated
        handout and fresh questions, and calls save_print_materials.
        """
        self.require_node(node_id, session_id)
        row = self._print_material(session_id, node_id, material_id)
        result = {
            "session_id": session_id, "node_id": node_id,
            "status": "ready" if row else "needs_authoring",
            "material_id": row["artifact_id"] if row else None,
            "version": row["version"] if row else None,
            "editions": list(EDITIONS),
        }
        draft = None
        if row and (include_html or html_directory or (material_id and include_source)):
            draft = json.loads(row["content"])
        if draft is not None and (include_html or html_directory):
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
            package_id = draft["package_id"] if material_id and draft else None
            package = self._print_source(session_id, node_id, package_id)
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
        return self.ok(**result)

    def save_print_materials(
        self, session_id: str, node_id: str, package_id: str, title: str,
        handout_html: str, questions: list[dict[str, Any]], *,
        orientation: Orientation = "portrait", margins_mm: list[float] | None = None,
        language: str = "zh-CN", request_id: str | None = None,
    ) -> dict:
        """Save a new editable print revision. Provide a static handout HTML fragment and freshly written questions.

        Explain terms on first use, show worked steps and reasoning, and include a self-check.
        Each question has point_ids, kind, prompt_html and answer_html. Optional title,
        options_html, answer_area, new_page and continuations control layout.
        Independently solve each question and check it against the handout before saving.
        """
        session = self.require_session(session_id)
        self.require_node(node_id, session_id)
        package = self._print_source(session_id, node_id, package_id)
        if package is None:
            raise ToolError("unknown_teaching_package", "package_id must belong to this session and node")
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
            "title": title, "handout_html": handout_html, "questions": questions, "language": language,
            "orientation": orientation, "margins_mm": margins_mm, "package_id": package_id,
        }
        documents = self._print_documents(draft, version)
        if sum(len(html.encode("utf-8")) for html in documents.values()) > 12 * 1024 * 1024:
            raise ToolError("invalid_print_material", "the four print editions exceed 12 MiB")
        self.artifacts.save(
            artifact_id=material_id, session_id=session_id, learner_id=session["learner_id"],
            artifact_type="print_materials", content=json.dumps(draft, ensure_ascii=False),
            metadata={"node_id": node_id, "package_id": package_id}, version=version,
        )
        return self.ok(
            material_id=material_id, version=version, session_id=session_id, node_id=node_id,
            covered_point_ids=sorted(covered), uncovered_point_ids=sorted(allowed - covered),
            content_verified_by_runtime=False,
        )

    def export_print_pdf(
        self, session_id: str, node_id: str, *, edition: Edition = "combined",
        material_id: str | None = None, orientation: Orientation | None = None,
        margins_mm: list[float] | None = None, output_path: str | None = None,
        include_pdf: bool = False,
    ) -> dict:
        """Export a saved print revision as A4 PDF. The combined edition starts the workbook on a fresh page.

        With include_pdf=True return base64 bytes for a host-connected page download.
        Otherwise write under artifact_root. An explicit output_path never overwrites.
        """
        self.require_node(node_id, session_id)
        if edition not in EDITIONS:
            raise ToolError("invalid_print_material", "unknown print edition")
        row = self._print_material(session_id, node_id, material_id)
        if row is None:
            return self.ok(
                status="needs_authoring", session_id=session_id, node_id=node_id, edition=edition,
                next_call={"tool": "get_print_materials", "arguments": {
                    "session_id": session_id, "node_id": node_id, "include_source": True,
                }},
            )
        draft = json.loads(row["content"])
        filename = f'{row["artifact_id"]}-{edition}.pdf'
        target = self._export_target(output_path or f'print/{new_id("export")}/{filename}') if output_path or not include_pdf else None
        try:
            settings = self._print_settings(draft, orientation, margins_mm)
            document = self._print_documents(draft, row["version"], settings)[edition]
            data = render_pdf(document, settings)
            if include_pdf and len(data) > 8 * 1024 * 1024:
                raise PrintError("PDF exceeds the inline limit. Export it to a file instead.")
            if target is not None:
                save_pdf(target, data)
        except (PrintError, OSError) as exc:
            raise ToolError("print_export_failed", str(exc)) from exc
        return self.ok(
            status="ready", session_id=session_id, node_id=node_id, edition=edition,
            material_id=row["artifact_id"], version=row["version"], filename=filename,
            orientation=settings.orientation, written_to=str(target) if target is not None else None,
            **({"pdf_base64": base64.b64encode(data).decode("ascii")} if include_pdf else {}),
        )

    def _print_source(self, session_id: str, node_id: str, package_id: str | None = None):
        return self.db.query_one(
            "SELECT artifact_id, content FROM artifacts WHERE session_id=? "
            "AND artifact_type='teaching_package' AND json_extract(metadata, '$.node_id')=? "
            "AND (? IS NULL OR artifact_id=?) ORDER BY rowid DESC LIMIT 1",
            (session_id, node_id, package_id, package_id),
        )

    def _print_material(self, session_id: str, node_id: str, material_id: str | None = None):
        row = self.db.query_one(
            "SELECT artifact_id, content, version FROM artifacts WHERE session_id=? "
            "AND artifact_type='print_materials' AND json_extract(metadata, '$.node_id')=? "
            "AND (? IS NULL OR artifact_id=?) ORDER BY rowid DESC LIMIT 1",
            (session_id, node_id, material_id, material_id),
        )
        if row is None and material_id is not None:
            raise ToolError("unknown_print_material", "material_id must belong to this session and node")
        return row

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
            )
        except PrintError as exc:
            raise ToolError("invalid_print_material", str(exc)) from exc
