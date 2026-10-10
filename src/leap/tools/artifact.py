"""Artifact, specification and reporting tools (section 22.10, section 25).

The MCP runtime **outputs specifications only**. It does not write Obsidian
vaults, does not read front-end source, and does not generate the HTML pages -
the host agent does all of that (section 22.10).
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Mapping

from leap.runtime.evidence import STAGES, stage_index
from leap.runtime.metrics import LearningMetrics, diagnostic_split
from leap.storage import new_id, now_ts
from leap.tools.base import LeapToolMixin, ToolError

__all__ = ["ArtifactTools"]

SPECS_DIR = Path(__file__).resolve().parents[1] / "specs"


class ArtifactTools(LeapToolMixin):
    """Artifact persistence, static specs, export and final reporting."""

    def get_teaching_delivery_policy(self) -> dict:
        """Return permanent depth, visualization, Markdown and resource requirements."""
        from leap.runtime.delivery import delivery_policy
        return self.ok(policy=delivery_policy(complete=True))

    def get_subject_catalog(self, subject: str | None = None) -> dict:
        """Return subject modules, prerequisite edges and canonical knowledge notes."""
        catalog = self._load_spec("subject_catalog.json")
        if subject is not None:
            selected = [entry for entry in catalog["subjects"] if entry["subject_id"] == subject]
            if not selected:
                raise ToolError("unknown_subject", "Subject is not present in the starter catalog; the delivery policy still applies to any subject")
            catalog["subjects"] = selected
        return self.ok(catalog=catalog, catalog_is_exhaustive=False)

    def save_teaching_package(
        self, session_id: str, node_id: str, subject: str,
        markdown: str, html: str, manifest: dict,
        *, request_id: str | None = None,
    ) -> dict:
        """Validate and store a complete canonical Markdown + interactive HTML pair.

        The host supplies actual bodies, point-by-point teaching and resource
        records. Structural acceptance never certifies subject-matter truth.
        """
        from leap.runtime.delivery import validate_teaching_package
        session = self.require_session(session_id)
        self.require_grounding(session_id)
        node = self.require_node(node_id)
        if node["session_id"] != session_id:
            raise ToolError("invalid_node", "teaching node must belong to this session")
        self.require_text(subject, "subject")
        result = validate_teaching_package(markdown, html, manifest)
        if not result["valid"]:
            raise ToolError("teaching_package_incomplete", "Teaching pair does not meet the permanent delivery policy", result)
        source_ids = manifest.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids or any(not isinstance(s, str) for s in source_ids):
            raise ToolError("invalid_source", "Teaching package must name its actual session source records")
        for source_id in source_ids:
            if not self.db.query_one("SELECT 1 FROM evidence_sources WHERE source_id=? AND session_id=?", (source_id, session_id)):
                raise ToolError("invalid_source", "Teaching source must belong to this session")
        artifact_id = new_id("art")
        ts = now_ts()
        content = {"markdown": markdown, "html": html, "manifest": manifest}
        metadata = {"node_id": node_id, "subject": subject, "validation": result,
                    "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
                    "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest()}
        self.db.execute(
            "INSERT INTO artifacts (artifact_id, learner_id, session_id, artifact_type, content, metadata, version, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (artifact_id, session["learner_id"], session_id, "teaching_package", self._dumps(content), self._dumps(metadata), "3.0", ts),
        )
        self.events.emit("teaching_package_saved", session_id=session_id, learner_id=session["learner_id"], node_id=node_id,
                         payload={"artifact_id": artifact_id, "policy_version": "3.0", "content_verified_by_runtime": False}, request_id=request_id)
        return self.ok(package_id=artifact_id, validation=result, content_hashes=metadata)

    # ------------------------------------------------------------------
    # 22.10 Artifact
    # ------------------------------------------------------------------
    def save_artifact(
        self,
        learner_id: str,
        session_id: str | None,
        artifact_type: str,
        *,
        path_or_uri: str | None = None,
        content: str | None = None,
        metadata: Any = None,
        version: str = "1",
        request_id: str | None = None,
    ) -> dict:
        artifact_type = self.require_text(artifact_type, "artifact_type")
        if path_or_uri is None and content is None:
            raise ToolError(
                "invalid_argument", "provide at least one of 'path_or_uri' or 'content'"
            )
        if session_id:
            self.require_session(session_id)
        teaching_types = {"html", "markdown", "lesson", "teaching", "teaching_html", "teaching_markdown", "chapter_delivery"}
        is_teaching = (artifact_type.lower() in teaching_types or
                       (path_or_uri and str(path_or_uri).lower().endswith((".html", ".htm", ".md"))) or
                       (isinstance(content, str) and "<html" in content.lower()))
        if is_teaching:
            package_id = metadata.get("teaching_package_id") if isinstance(metadata, dict) else None
            row = self.db.query_one("SELECT metadata FROM artifacts WHERE artifact_id=? AND session_id=? AND artifact_type='teaching_package'", (package_id, session_id)) if package_id else None
            if not row:
                raise ToolError("teaching_package_required", "Register both teaching bodies with save_teaching_package before saving a teaching artifact")
            package_meta = json.loads(row["metadata"])
            if content is not None:
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                if digest not in {package_meta["markdown_sha256"], package_meta["html_sha256"]}:
                    raise ToolError("teaching_content_mismatch", "Artifact content differs from the registered teaching pair")
        self.ensure_learner(learner_id)

        artifact_id = new_id("art")
        ts = now_ts()
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO artifacts "
                "(artifact_id, learner_id, session_id, artifact_type, path_or_uri, content, "
                " metadata, version, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (artifact_id, learner_id, session_id, artifact_type, path_or_uri, content,
                 self._dumps(metadata) if metadata is not None else None, version, ts),
            )
        self.events.emit(
            "artifact_saved", session_id=session_id, learner_id=learner_id,
            payload={"artifact_id": artifact_id, "artifact_type": artifact_type},
            request_id=request_id,
        )
        return self.ok(artifact_id=artifact_id, artifact_type=artifact_type, created_at=ts)

    def get_artifact(self, artifact_id: str, *, include_content: bool = True) -> dict:
        row = self.db.query_one("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,))
        if row is None:
            raise ToolError("unknown_artifact", f"artifact not found: {artifact_id}")
        data = dict(row)
        if not include_content:
            data.pop("content", None)
        return self.ok(artifact=data)

    def list_artifacts(
        self, session_id: str, artifact_type: str | None = None
    ) -> dict:
        self.require_session(session_id)
        if artifact_type:
            rows = self.rows(
                "SELECT artifact_id, artifact_type, path_or_uri, version, created_at "
                "FROM artifacts WHERE session_id = ? AND artifact_type = ? ORDER BY created_at DESC",
                (session_id, artifact_type),
            )
        else:
            rows = self.rows(
                "SELECT artifact_id, artifact_type, path_or_uri, version, created_at "
                "FROM artifacts WHERE session_id = ? ORDER BY created_at DESC",
                (session_id,),
            )
        return self.ok(session_id=session_id, count=len(rows), artifacts=rows)

    def get_obsidian_structure(self) -> dict:
        """Return the static vault specification. No local file access."""
        return self.ok(
            spec=self._load_spec("obsidian_structure.json"),
            delivery_requirements=self.get_teaching_delivery_policy()["policy"],
            note=(
                "This is a specification only. The LEAP runtime does not read or write any "
                "Obsidian folder; the host agent materialises the files."
            ),
        )

    def get_web_component_spec(self) -> dict:
        """Return the static web-component specification. No source reading."""
        return self.ok(
            spec=self._load_spec("web_component_spec.json"),
            interaction_schema=self._load_spec("interaction_output.schema.json"),
            delivery_requirements=self.get_teaching_delivery_policy()["policy"],
            note=(
                "This is a specification only. The LEAP runtime does not generate HTML and "
                "does not read local front-end sources; the host agent does."
            ),
        )

    # ------------------------------------------------------------------
    # Export & reporting
    # ------------------------------------------------------------------
    def export_session_data(
        self, session_id: str, *, output_path: str | None = None
    ) -> dict:
        self.require_session(session_id)
        bundle = {
            "exported_at": now_ts(),
            "schema_version": self.db.scalar(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ),
            "session": dict(self.db.query_one(
                "SELECT * FROM learning_sessions WHERE session_id = ?", (session_id,)
            )),
            "learning_goal": self.db.row_to_dict(self.db.query_one(
                "SELECT * FROM learning_goals WHERE session_id = ? ORDER BY rowid DESC LIMIT 1",
                (session_id,),
            )),
            "knowledge_nodes": self.rows(
                "SELECT * FROM knowledge_nodes WHERE session_id = ?", (session_id,)
            ),
            "knowledge_edges": self.rows(
                "SELECT * FROM knowledge_edges WHERE session_id = ?", (session_id,)
            ),
            "attempts": self.rows(
                "SELECT * FROM learning_attempts WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ),
            "assessment_results": self.rows(
                "SELECT ar.* FROM assessment_results ar "
                "JOIN learning_attempts la ON la.attempt_id = ar.attempt_id "
                "WHERE la.session_id = ? ORDER BY ar.created_at",
                (session_id,),
            ),
            "pedagogical_decisions": self.rows(
                "SELECT * FROM pedagogical_decisions WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ),
            "events": self.rows(
                "SELECT * FROM event_log WHERE session_id = ? ORDER BY created_at", (session_id,)
            ),
            "artifacts": self.rows(
                "SELECT artifact_id, artifact_type, path_or_uri, version, created_at "
                "FROM artifacts WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ),
        }
        if output_path:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self._dumps(bundle), encoding="utf-8")
            bundle["written_to"] = str(target)
        return self.ok(export=bundle)

    def get_learning_metrics(self, session_id: str) -> dict:
        """Return the section 26.1 learning-outcome indicators.

        Section 26 asks whether the teaching strategy actually improved
        learning, not merely whether the API responded. Every value here is
        derived from recorded evidence, so it is reproducible.
        """
        self.require_session(session_id)
        metrics = LearningMetrics(self.db, self.cfg).compute(session_id)
        return self.ok(**metrics)

    def generate_final_report(
        self, session_id: str, *, save_as_artifact: bool = True
    ) -> dict:
        """Assemble the closing report (section 25).

        The report deliberately separates **observed evidence** from
        **estimated state**, and states remaining uncertainty instead of
        presenting model estimates as fact.
        """
        session = self.require_session(session_id)
        learner_id = session["learner_id"]

        goal = self.db.row_to_dict(self.db.query_one(
            "SELECT * FROM learning_goals WHERE session_id = ? ORDER BY rowid DESC LIMIT 1",
            (session_id,),
        ))
        nodes = self.rows(
            "SELECT * FROM knowledge_nodes WHERE session_id = ? ORDER BY node_id", (session_id,)
        )
        states = self.rows(
            "SELECT * FROM learner_knowledge_state WHERE learner_id = ?", (learner_id,)
        )
        results = self.rows(
            "SELECT ar.* FROM assessment_results ar "
            "JOIN learning_attempts la ON la.attempt_id = ar.attempt_id "
            "WHERE la.session_id = ? ORDER BY ar.rowid",
            (session_id,),
        )
        misconceptions = self.rows(
            "SELECT * FROM misconceptions WHERE learner_id = ? ORDER BY last_seen_at DESC",
            (learner_id,),
        )
        transfers = self.rows(
            "SELECT * FROM transfer_results WHERE learner_id = ? ORDER BY created_at",
            (learner_id,),
        )
        reviews = self.rows(
            "SELECT * FROM review_items WHERE learner_id = ? ORDER BY next_review_at",
            (learner_id,),
        )

        coverage = {
            "total_nodes": len(nodes),
            "nodes_with_evidence": sum(
                1 for s in states if stage_index(s.get("evidence_stage", "estimated")) >= 1
            ),
            "by_stage": {
                stage: sum(1 for s in states if s.get("evidence_stage") == stage) for stage in STAGES
            },
        }
        mastered = [
            s for s in states
            if stage_index(s.get("evidence_stage", "estimated")) >= stage_index("demonstrated")
        ]
        mastery = {
            "nodes_at_or_above_demonstrated": len(mastered),
            "mean_mastery_probability": (
                round(sum(float(s.get("mastery_probability") or 0.0) for s in states) / len(states), 4)
                if states else None
            ),
            "note": "mastery_probability is a model estimate produced by the server-side BKT, not a measured fact",
        }
        hint_values = [float(r["hint_dependency"]) for r in results if r.get("hint_dependency") is not None]
        calibration_pairs = [
            (float(r["confidence"]), float(r["overall_score"]))
            for r in results
            if r.get("confidence") is not None and r.get("overall_score") is not None
        ]
        calibration = (
            round(sum(abs(c - a) for c, a in calibration_pairs) / len(calibration_pairs), 4)
            if calibration_pairs else None
        )
        active_misconceptions = [m for m in misconceptions if m.get("status") == "active"]

        # --- Diagnostic baseline (section 25) -------------------------------
        # Attempts recorded before the diagnostic was marked complete form the
        # baseline that Learning Gain is measured against. The split lives in
        # leap.runtime.metrics so the report and the metrics tool agree.
        baseline_results, post_results, diagnostic_done_at = diagnostic_split(
            self.db, session_id
        )
        baseline_scores = [
            float(r["overall_score"]) for r in baseline_results if r.get("overall_score") is not None
        ]
        baseline_nodes = sorted({r["node_id"] for r in baseline_results if r.get("node_id")})
        diagnostic_artifact = self.db.query_one(
            "SELECT artifact_id, created_at FROM artifacts "
            "WHERE session_id = ? AND artifact_type = 'diagnostic_result' "
            "ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        )
        diagnostic_baseline = {
            "completed_at": int(diagnostic_done_at) if diagnostic_done_at else None,
            "artifact_id": diagnostic_artifact["artifact_id"] if diagnostic_artifact else None,
            "evidence_points": len(baseline_results),
            "nodes_probed": baseline_nodes,
            "mean_score": round(sum(baseline_scores) / len(baseline_scores), 4) if baseline_scores else None,
            "note": (
                "baseline captured from assessment evidence recorded before the diagnostic was "
                "marked complete; null when no diagnostic was run"
            ),
        }

        # --- Reasoning quality (section 25) ---------------------------------
        reasoning_values = [
            float(r["reasoning_quality"]) for r in results if r.get("reasoning_quality") is not None
        ]
        reasoning_quality = {
            "mean": round(sum(reasoning_values) / len(reasoning_values), 4) if reasoning_values else None,
            "samples": len(reasoning_values),
            "low_threshold": float(self.conf("reasoning_quality_low", 0.50)),
        }
        if reasoning_quality["mean"] is not None:
            reasoning_quality["below_threshold"] = (
                reasoning_quality["mean"] < reasoning_quality["low_threshold"]
            )

        # --- Learning Gain (section 26.2) -----------------------------------
        # Delegated to the metrics module so the report and the metrics tool
        # can never disagree about how gain is computed.
        post_scores = [
            float(r["overall_score"]) for r in post_results if r.get("overall_score") is not None
        ]
        post_mean = round(sum(post_scores) / len(post_scores), 4) if post_scores else None
        baseline_mean = diagnostic_baseline["mean_score"]
        learning_gain = LearningMetrics(self.db, self.cfg).learning_gain(
            baseline_results, post_results
        )
        if learning_gain["absolute_gain"] is None:
            learning_gain["note"] = (
                "learning gain needs both a diagnostic baseline and post-diagnostic evidence; "
                "one of them is missing"
            )

        observed = {
            "assessment_evidence_count": len(results),
            "attempt_count": len(self.rows(
                "SELECT attempt_id FROM learning_attempts WHERE session_id = ?", (session_id,)
            )),
            "transfer_attempts": len(transfers),
            "review_items": len(reviews),
            "active_misconceptions": len(active_misconceptions),
            "mean_hint_dependency": (
                round(sum(hint_values) / len(hint_values), 4) if hint_values else None
            ),
            "mean_reasoning_quality": reasoning_quality["mean"],
        }
        estimated = {
            "knowledge_coverage": coverage,
            "mastery": mastery,
            "reasoning_quality": reasoning_quality,
            "confidence_calibration_error": calibration,
            "learning_gain": learning_gain,
        }
        uncertainty: list[str] = []
        if not transfers:
            uncertainty.append("no transfer evidence collected; generalisation is unverified")
        if not reviews:
            uncertainty.append("no retention evidence collected; delayed recall is unverified")
        if len(results) < 3:
            uncertainty.append("very few assessment points; state estimates are weakly supported")
        if calibration is None:
            uncertainty.append("no confidence self-ratings; calibration could not be computed")
        if diagnostic_baseline["mean_score"] is None:
            uncertainty.append(
                "no diagnostic baseline recorded; learning gain cannot be measured"
            )
        elif learning_gain["absolute_gain"] is None:
            uncertainty.append(
                "no post-diagnostic evidence yet; learning gain is not yet measurable"
            )
        if reasoning_quality["samples"] == 0:
            uncertainty.append("no reasoning-quality ratings; reasoning quality is unknown")
        if active_misconceptions:
            uncertainty.append(
                f"{len(active_misconceptions)} misconception(s) remain active and may distort later evidence"
            )

        next_path = self._next_learning_path(states, nodes, reviews)

        report = {
            "session_id": session_id,
            "learner_id": learner_id,
            "topic": session.get("topic"),
            "generated_at": now_ts(),
            "learning_goal": goal,
            "diagnostic_baseline": diagnostic_baseline,
            "observed_evidence": observed,
            "estimated_state": estimated,
            "remaining_uncertainty": uncertainty,
            "recommended_next_step": next_path,
            "misconceptions": misconceptions,
            "transfer_performance": transfers,
            "review_plan": reviews,
        }

        artifact_id = None
        if save_as_artifact:
            artifact_id = new_id("art")
            with self.db.transaction():
                self.db.execute(
                    "INSERT INTO artifacts "
                    "(artifact_id, learner_id, session_id, artifact_type, path_or_uri, content, "
                    " metadata, version, created_at) VALUES (?,?,?,'final_report',NULL,?,NULL,'1',?)",
                    (artifact_id, learner_id, session_id, self._dumps(report), now_ts()),
                )
            self.events.emit(
                "artifact_saved", session_id=session_id, learner_id=learner_id,
                payload={"artifact_id": artifact_id, "artifact_type": "final_report"},
            )

        return self.ok(
            session_id=session_id,
            artifact_id=artifact_id,
            report=report,
            markdown=self._render_report_markdown(report),
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    @staticmethod
    def _dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str, indent=2)

    @staticmethod
    def _load_spec(filename: str) -> Mapping[str, Any]:
        path = SPECS_DIR / filename
        if not path.exists():
            raise ToolError("spec_missing", f"specification file not found: {filename}")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _next_learning_path(states: list[dict], nodes: list[dict], reviews: list[dict]) -> dict:
        by_stage: dict[str, list[str]] = {}
        for state in states:
            by_stage.setdefault(state.get("evidence_stage", "estimated"), []).append(state["node_id"])

        weakest = sorted(
            (s for s in states if stage_index(s.get("evidence_stage", "estimated")) < stage_index("demonstrated")),
            key=lambda s: float(s.get("mastery_probability") or 0.0),
        )
        return {
            "priority": "consolidate weak nodes before advancing",
            "weak_nodes": [s["node_id"] for s in weakest[:5]],
            "due_reviews": [r["node_id"] for r in reviews][:5],
            "nodes_by_stage": by_stage,
            "total_nodes": len(nodes),
        }

    def _render_report_markdown(self, report: Mapping[str, Any]) -> str:
        """Render the closing report in the active locale (section 25)."""
        t = self.t
        observed = report["observed_evidence"]
        estimated = report["estimated_state"]
        coverage = estimated["knowledge_coverage"]
        mastery = estimated["mastery"]
        goal = report.get("learning_goal") or {}

        lines = [
            f"# {t('report.title')}",
            "",
            f"- {t('report.topic')}: {report.get('topic')}",
            f"- {t('report.learner')}: {report.get('learner_id')}",
            f"- {t('report.session')}: {report.get('session_id')}",
            "",
            f"## {t('report.learning_goal')}",
            "",
            f"- Goal: {goal.get('goal') or '(not recorded)'}",
            f"- Target depth: {goal.get('target_depth') or '(not recorded)'}",
            f"- Time budget: {goal.get('time_budget') or '(not recorded)'}",
            "",
            f"## {t('report.diagnostic_baseline')}",
            "",
        ]
        baseline = report.get("diagnostic_baseline") or {}
        lines += [
            f"- Evidence points: {baseline.get('evidence_points')}",
            f"- Nodes probed: {', '.join(baseline.get('nodes_probed') or []) or '(none)'}",
            f"- Mean baseline score: {baseline.get('mean_score')}",
            f"- Completed at: {baseline.get('completed_at') or '(diagnostic not run)'}",
            "",
            f"## {t('report.observed_evidence')}",
            "",
            t("report.facts_warning"),
            "",
            f"- Assessment evidence points: {observed['assessment_evidence_count']}",
            f"- Learner attempts: {observed['attempt_count']}",
            f"- Transfer attempts: {observed['transfer_attempts']}",
            f"- Review items scheduled: {observed['review_items']}",
            f"- Active misconceptions: {observed['active_misconceptions']}",
            f"- Mean hint dependency: {observed['mean_hint_dependency']}",
            f"- Mean reasoning quality: {observed.get('mean_reasoning_quality')}",
            "",
            f"## {t('report.estimated_state')}",
            "",
            t("report.estimates_warning"),
            "",
            f"- Knowledge coverage: {coverage['nodes_with_evidence']} of {coverage['total_nodes']} nodes have evidence",
            f"- Nodes at or above `demonstrated`: {mastery['nodes_at_or_above_demonstrated']}",
            f"- Mean mastery probability: {mastery['mean_mastery_probability']}",
            f"- Confidence calibration error: {estimated['confidence_calibration_error']}",
            "",
            f"### {t('report.reasoning_quality')}",
            "",
        ]
        rq = estimated.get("reasoning_quality") or {}
        lines += [
            f"- Mean: {rq.get('mean')} (over {rq.get('samples')} rating(s))",
            f"- Low-quality threshold: {rq.get('low_threshold')}",
        ]
        if "below_threshold" in rq:
            lines.append(
                f"- Below threshold: {'yes' if rq['below_threshold'] else 'no'}"
            )

        lines += ["", f"### {t('report.learning_gain')}", ""]
        gain = estimated.get("learning_gain") or {}
        lines += [
            f"- Baseline mean score: {gain.get('baseline_mean_score')}",
            f"- Post-diagnostic mean score: {gain.get('post_mean_score')}",
            f"- Absolute gain: {gain.get('absolute_gain')}",
            f"- Post-diagnostic evidence points: {gain.get('post_points')}",
        ]

        lines += ["", f"### {t('report.stage_distribution')}", ""]
        for stage, count in coverage["by_stage"].items():
            lines.append(f"- `{stage}`: {count}")

        lines += ["", f"## {t('report.remaining_uncertainty')}", ""]
        if report["remaining_uncertainty"]:
            lines += [f"- {item}" for item in report["remaining_uncertainty"]]
        else:
            lines.append("- None identified.")

        lines += ["", f"## {t('report.recommended_next_step')}", ""]
        nxt = report["recommended_next_step"]
        lines.append(f"- {nxt['priority']}")
        if nxt["weak_nodes"]:
            lines.append(f"- Weak nodes to consolidate: {', '.join(nxt['weak_nodes'])}")
        if nxt["due_reviews"]:
            lines.append(f"- Reviews due: {', '.join(nxt['due_reviews'])}")

        lines += ["", f"## {t('report.review_plan')}", ""]
        if report["review_plan"]:
            for item in report["review_plan"]:
                lines.append(
                    f"- `{item['node_id']}` next review at {item.get('next_review_at')} "
                    f"(stability {item.get('stability')})"
                )
        else:
            lines.append("- No review items scheduled yet.")

        lines.append("")
        from leap.runtime.notes import obsidian_note
        topic = str(report.get("topic") or "learning evidence")
        return obsidian_note("\n".join(lines), title=t("report.title"), topic=topic,
                             tags=["leap", "report", "runtime_snapshot"],
                             links=["01_Knowledge/Knowledge_Map", "00_System/learning_goal"])
