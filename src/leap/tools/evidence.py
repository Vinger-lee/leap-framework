"""Evidence / Grounding tools (section 22.9, section 17).

`get_grounding_sources` retrieves pre-reviewed evidence and `save_benchmark_report`
records the calibration receipt required before teaching.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from leap.storage import new_id, now_ts
from leap.tools.base import LeapToolMixin, ToolError

__all__ = ["EvidenceTools"]


class EvidenceTools(LeapToolMixin):
    """Domain grounding reports, claims and source conflict handling."""

    # ------------------------------------------------------------------
    # 22.9 Evidence / Grounding
    # ------------------------------------------------------------------
    def get_grounding_sources(self, session_id: str, *, point_ids: list[str] | None = None,
                              include_lesson: bool = False) -> dict:
        """Retrieve reviewed passages for this session topic, before calibration.

        Read the passages and solve the checks before saving the benchmark. With
        include_lesson, return the reviewed teaching pair after calibration.
        """
        from leap.runtime.grounding import (
            GroundingError, course_node_id, lesson_pair, print_draft, retrieve_evidence, reviewed_items,
        )

        session = self.require_session(session_id)
        try:
            evidence = retrieve_evidence(session["topic"], point_ids)
        except GroundingError as exc:
            raise ToolError(exc.code, str(exc)) from exc
        course = evidence["course"]
        response = dict(course_id=course["course_id"], title=course["title"],
                        course_revision=evidence["course_revision"], sources=evidence["sources"],
                        reviewed_on=course["reviewed_on"], review_due_on=course["review_due_on"],
                        checks=[{"id": point["check"]["id"], "prompt": point["check"]["prompt"]}
                                for point in course["points"]])
        if include_lesson:
            receipt = self.require_grounding(session_id)
            markdown, html, manifest = lesson_pair(course, receipt["source_ids"])
            response["lesson"] = {"markdown": markdown, "html": html, "manifest": manifest,
                                  "subject": "calculus", "items": reviewed_items(course, receipt["source_ids"]),
                                  "print_draft": print_draft(course),
                                  "node": {"node_id": course_node_id(session_id), "title": course["title"],
                                           "unit_tag": "calculus", "bloom_level": "understand"}}
        return self.ok(session_id=session_id, **response)

    def save_benchmark_report(
        self,
        session_id: str,
        report_text: str,
        *,
        source_refs: list[dict] | None = None,
        verification: dict | None = None,
        course_revision: str | None = None,
        chunk_ids: list[str] | None = None,
        check_answers: dict[str, str] | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Calibrate against retrieved reviewed passages and independently solve their checks.

        Submit course_revision, every retrieved chunk_id, and check_answers keyed
        by the returned check ids. The server records locators and provenance from
        the reviewed pack. Host-reported source_refs and verification are legacy
        arguments and cannot authorize production teaching.
        """
        session = self.require_session(session_id)
        report_text = self.require_text(report_text, "report_text")
        if self.guard.strict_grounding:
            if source_refs is not None or verification is not None:
                raise ToolError("grounding_host_attestation_unsupported", "Use reviewed passage IDs and their calibration checks")
            return self._save_reviewed_report(session, report_text, course_revision,
                                              chunk_ids, check_answers, request_id)
        refs = list(source_refs or [])
        if any(not isinstance(ref, Mapping) for ref in refs):
            raise ToolError("invalid_argument", "source_refs must contain source objects")
        verification = dict(verification or {})
        missing: list[str] = []
        if not refs:
            missing.append("source_refs: read sources and provide locator + excerpt")
        for i, ref in enumerate(refs):
            for key in ("source", "source_type", "locator", "excerpt"):
                if not isinstance(ref.get(key), str) or not ref[key].strip():
                    missing.append(f"source_refs[{i}].{key}")
            # Optional structured fields: reject malformed values here instead of
            # letting an int()/json() coercion fail later as an internal error.
            for key in ("retrieved_at", "last_verified"):
                if ref.get(key) is None:
                    continue
                value = ref[key]
                if isinstance(value, bool) or not isinstance(value, (int, str)) or (
                    isinstance(value, str) and not value.strip().lstrip("-").isdigit()
                ):
                    raise ToolError(
                        "invalid_argument",
                        f"source_refs[{i}].{key} must be a Unix timestamp in seconds",
                    )
            metadata = ref.get("metadata")
            if metadata is not None and not isinstance(metadata, Mapping):
                raise ToolError(
                    "invalid_argument",
                    f"source_refs[{i}].metadata must be an object",
                )
            for key in ("authority", "publication_date", "source_id"):
                if ref.get(key) is not None and not isinstance(ref[key], str):
                    raise ToolError(
                        "invalid_argument",
                        f"source_refs[{i}].{key} must be a string",
                    )
        if not isinstance(verification.get("scope"), str) or not verification["scope"].strip():
            missing.append("verification.scope")
        claims = verification.get("claims")
        if not isinstance(claims, list) or not claims:
            missing.append("verification.claims")
        else:
            for i, claim in enumerate(claims):
                index = claim.get("source_index") if isinstance(claim, dict) else None
                if not isinstance(claim, dict) or not isinstance(claim.get("claim"), str) or not claim["claim"].strip() or type(index) is not int or not 0 <= index < len(refs):
                    missing.append(f"verification.claims[{i}]: claim + valid source_index required")
        examples = verification.get("worked_examples")
        if not isinstance(examples, list) or not examples:
            missing.append("verification.worked_examples")
        else:
            for i, example in enumerate(examples):
                if not isinstance(example, dict) or any(not isinstance(example.get(k), str) or not example[k].strip() for k in ("problem", "solution", "check_method", "check_result")):
                    missing.append(f"verification.worked_examples[{i}]: problem, solution, check_method, check_result required")
        if not isinstance(verification.get("limitations"), list):
            missing.append("verification.limitations: list unresolved uncertainty explicitly")
        stage = "pending" if missing else "completed"
        previous_stage = str(session.get("domain_grounding_stage") or "pending")
        stage_downgraded = previous_stage == "completed" and stage == "pending"
        if previous_stage == "completed":
            # Grounding evidence can be added after completion, but a partial
            # follow-up report must never re-lock an already grounded session:
            # that turned an innocent second call into a re-opened gate.
            stage = "completed"
        ts = now_ts()

        artifact_id = new_id("art")
        saved_sources: list[str] = []
        artifact_metadata = {"topic": session.get("topic"), "source_count": len(refs),
                             "verification": verification, "missing_evidence": missing,
                             "evidence_format_version": 1}
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO artifacts "
                "(artifact_id, learner_id, session_id, artifact_type, path_or_uri, content, "
                " metadata, version, created_at) VALUES (?,?,?,'agent_benchmark_report',NULL,?,?, '1', ?)",
                (artifact_id, session["learner_id"], session_id, report_text,
                 self._dumps(artifact_metadata), ts),
            )
            for ref in source_refs or []:
                source_id = ref.get("source_id") or new_id("src")
                existing = self.db.query_one("SELECT session_id FROM evidence_sources WHERE source_id = ?", (source_id,))
                if existing and existing["session_id"] != session_id:
                    raise ToolError("invalid_source", "source belongs to another session")
                self.db.execute(
                    "INSERT INTO evidence_sources "
                    "(source_id, session_id, source, source_type, authority, publication_date, "
                    " retrieved_at, last_verified, metadata) VALUES (?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(source_id) DO UPDATE SET source=excluded.source, "
                    "source_type=excluded.source_type, authority=excluded.authority, "
                    "metadata=excluded.metadata, last_verified=excluded.last_verified",
                    (source_id, session_id, ref.get("source") or str(ref)[:200],
                     ref.get("source_type"), ref.get("authority"), ref.get("publication_date"),
                     int(ref.get("retrieved_at") or ts), int(ref.get("last_verified") or ts),
                     self._dumps({**(ref.get("metadata") or {}), "locator": ref.get("locator"), "excerpt": ref.get("excerpt") })),
                )
                saved_sources.append(source_id)

            artifact_metadata["source_ids"] = saved_sources
            self.db.execute("UPDATE artifacts SET metadata = ? WHERE artifact_id = ?",
                            (self._dumps(artifact_metadata), artifact_id))

            if stage_downgraded:
                # Keep the completed report as the grounding pointer: the guard
                # validates that artifact, so pointing at a partial follow-up
                # would re-lock a grounded session.
                self.db.execute(
                    "UPDATE learning_sessions SET updated_at = ? WHERE session_id = ?",
                    (ts, session_id),
                )
            else:
                self.db.execute(
                    "UPDATE learning_sessions SET benchmark_report_artifact_id = ?, "
                    "domain_grounding_stage = ?, updated_at = ? WHERE session_id = ?",
                    (artifact_id, stage, ts, session_id),
                )

        self.events.emit(
            "domain_grounding_completed" if not missing else "domain_grounding_incomplete", session_id=session_id, learner_id=session["learner_id"],
            payload={"artifact_id": artifact_id, "chars": len(report_text),
                     "source_count": len(saved_sources)},
            request_id=request_id,
        )
        self.events.emit(
            "artifact_saved", session_id=session_id, learner_id=session["learner_id"],
            payload={"artifact_id": artifact_id, "artifact_type": "agent_benchmark_report"},
        )
        return self.ok(
            artifact_id=artifact_id,
            session_id=session_id,
            domain_grounding_stage=stage,
            previous_stage=previous_stage,
            stage_downgraded=False,
            stage_downgrade_guard=stage_downgraded,
            missing_evidence=missing,
            evidence_format_version=1,
            content_verified_by_runtime=False,
            sources_saved=saved_sources,
            next_step="save_benchmark_report" if missing else "generate_diagnostic",
            note=(
                "grounding already completed; this report was appended and the stage was "
                "kept at completed"
                if stage_downgraded
                else None
            ),
        )

    def _save_reviewed_report(self, session, report_text, course_revision, chunk_ids, check_answers, request_id):
        from leap.runtime.grounding import FORMAT_VERSION, GroundingError, normalized_answer, retrieve_evidence

        self.require_active_session(session)
        session_id = session["session_id"]
        try:
            evidence = retrieve_evidence(session["topic"])
        except GroundingError as exc:
            raise ToolError(exc.code, str(exc)) from exc
        if course_revision != evidence["course_revision"]:
            raise ToolError("grounding_revision_required", "Retrieve the current reviewed course revision first",
                            {"next_call": {"tool": "get_grounding_sources", "arguments": {"session_id": session_id}}})
        sources = {record["chunk_id"]: record for record in evidence["sources"]}
        selected_ids = set(chunk_ids or [])
        if selected_ids != set(sources):
            raise ToolError("grounding_coverage_missing", "Read every reviewed passage before starting this course",
                            {"missing_chunk_ids": sorted(set(sources) - selected_ids)})
        expected = {point["check"]["id"]: point["check"]["answer"] for point in evidence["course"]["points"]}
        answers = check_answers or {}
        incorrect = [key for key, answer in expected.items() if normalized_answer(answers.get(key)) != answer]
        if incorrect:
            raise ToolError("grounding_check_failed", "Recheck the indicated derivations against the source pack",
                            {"check_ids": incorrect})
        timestamp = now_ts()
        report_id = new_id("art")
        source_ids = [new_id("src") for _ in sources]
        metadata = {"evidence_format_version": FORMAT_VERSION, "source_count": len(source_ids),
                    "course_id": evidence["course"]["course_id"], "course_revision": course_revision,
                    "source_ids": source_ids, "chunk_fingerprints": {key: row["fingerprint"] for key, row in sources.items()},
                    "passed_checks": list(expected)}
        with self.db.transaction():
            for source_id, source in zip(source_ids, sources.values()):
                self.db.execute(
                    "INSERT INTO evidence_sources (source_id, session_id, source, source_type, authority, "
                    "retrieved_at, last_verified, metadata) VALUES (?,?,?,?,?,?,?,?)",
                    (source_id, session_id, source["url"], "reviewed_reference", source["publisher"], timestamp, None,
                     self._dumps({**source, "excerpt": source["summary"], "reviewed_on": evidence["course"]["reviewed_on"]})),
                )
            self.db.execute(
                "INSERT INTO artifacts (artifact_id, learner_id, session_id, artifact_type, content, metadata, version, created_at) "
                "VALUES (?,?,?,'agent_benchmark_report',?,?,'2',?)",
                (report_id, session["learner_id"], session_id, report_text, self._dumps(metadata), timestamp),
            )
            self.db.execute("UPDATE learning_sessions SET benchmark_report_artifact_id=?, "
                            "domain_grounding_stage='completed', updated_at=? WHERE session_id=?",
                            (report_id, timestamp, session_id))
            self.events.emit("domain_grounding_completed", session_id=session_id, learner_id=session["learner_id"],
                             payload={"artifact_id": report_id, "source_count": len(source_ids)}, request_id=request_id)
        return self.ok(session_id=session_id, artifact_id=report_id, domain_grounding_stage="completed",
                       evidence_format_version=FORMAT_VERSION, course_revision=course_revision, sources_saved=source_ids,
                       next_step="generate_diagnostic", content_verified_by_runtime=False)

    def save_benchmark_claim(
        self,
        session_id: str,
        claim: str,
        *,
        source_id: str | None = None,
        confidence: float | None = None,
        knowledge_scope: str | None = None,
        conflicting_sources: Any = None,
        request_id: str | None = None,
    ) -> dict:
        """Save one structured knowledge claim with its source and confidence."""
        self.require_session(session_id)
        claim = self.require_text(claim, "claim")
        if source_id and not self.db.query_one("SELECT 1 FROM evidence_sources WHERE source_id = ? AND session_id = ?", (source_id, session_id)):
            raise ToolError("invalid_source", "source must belong to this session")
        claim_id = new_id("claim")
        ts = now_ts()
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO benchmark_claims "
                "(claim_id, session_id, source_id, claim, confidence, knowledge_scope, "
                " conflicting_sources, last_verified, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (claim_id, session_id, source_id, claim,
                 None if confidence is None else float(confidence), knowledge_scope,
                 self._dumps(conflicting_sources) if conflicting_sources is not None else None,
                 ts, ts),
            )
        return self.ok(claim_id=claim_id, session_id=session_id)

    def get_evidence(self, session_id: str, node_id: str | None = None) -> dict:
        """Return grounding report metadata, claims and sources for a session."""
        self.require_session(session_id)
        claims = self.rows(
            "SELECT bc.*, es.source, es.source_type, es.authority "
            "FROM benchmark_claims bc LEFT JOIN evidence_sources es ON es.source_id = bc.source_id "
            "WHERE bc.session_id = ? ORDER BY bc.created_at DESC",
            (session_id,),
        )
        sources = self.rows(
            "SELECT * FROM evidence_sources WHERE session_id = ? ORDER BY retrieved_at DESC",
            (session_id,),
        )
        report = self.db.query_one(
            "SELECT a.artifact_id, a.artifact_type, a.content, a.metadata, a.created_at "
            "FROM artifacts a JOIN learning_sessions s ON s.benchmark_report_artifact_id = a.artifact_id "
            "WHERE s.session_id = ?",
            (session_id,),
        )
        return self.ok(
            session_id=session_id,
            node_id=node_id,
            benchmark_report=dict(report) if report else None,
            claim_count=len(claims),
            claims=claims,
            source_count=len(sources),
            sources=sources,
        )

    def validate_claim(self, claim_id: str, *, verified: bool = True) -> dict:
        """Check whether a claim is linked to a real evidence source."""
        row = self.db.query_one("SELECT * FROM benchmark_claims WHERE claim_id = ?", (claim_id,))
        if row is None:
            raise ToolError("unknown_claim", f"claim not found: {claim_id}")
        source_id = row["source_id"]
        has_source = bool(source_id) and self.db.query_one(
            "SELECT 1 FROM evidence_sources WHERE source_id = ?", (source_id,)
        ) is not None
        ts = now_ts()
        self.db.execute(
            "UPDATE benchmark_claims SET last_verified = ? WHERE claim_id = ?", (ts, claim_id)
        )
        return self.ok(
            claim_id=claim_id,
            source_linked=has_source,
            verified=bool(verified and has_source),
            verification_scope="source_linkage_only",
            content_verified_by_runtime=False,
            last_verified=ts,
            warning=None if has_source else "claim has no linked evidence source",
        )

    def record_source_conflict(
        self,
        claim_id: str,
        conflicting_sources: Any,
        *,
        uncertainty: str | None = None,
    ) -> dict:
        """Record conflicting sources instead of silently choosing one."""
        row = self.db.query_one("SELECT * FROM benchmark_claims WHERE claim_id = ?", (claim_id,))
        if row is None:
            raise ToolError("unknown_claim", f"claim not found: {claim_id}")
        payload = self._dumps(conflicting_sources)
        self.db.execute(
            "UPDATE benchmark_claims SET conflicting_sources = ?, confidence = ?, last_verified = ? "
            "WHERE claim_id = ?",
            (payload, 0.0 if uncertainty else row["confidence"], now_ts(), claim_id),
        )
        return self.ok(
            claim_id=claim_id,
            conflicting_sources=conflicting_sources,
            uncertainty=uncertainty,
            note=(
                "Conflicting sources are preserved. For high-risk domains escalate to "
                "grounding + uncertainty + human review (section 17.4)."
            ),
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _dumps(value: Any) -> str:
        import json

        return json.dumps(value, ensure_ascii=False, default=str)
