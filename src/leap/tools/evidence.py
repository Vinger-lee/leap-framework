"""Evidence / Grounding tools (section 22.9, section 17).

``save_benchmark_report`` is the core write of the Domain Grounding stage. While
``allow_skip_domain_grounding`` is false, the State Guard refuses
``generate_diagnostic`` until a valid report exists (section 22.9).
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
    def save_benchmark_report(
        self,
        session_id: str,
        report_text: str,
        *,
        source_refs: Sequence[Mapping[str, Any]] | None = None,
        verification: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Persist the agent's internal knowledge baseline for this topic.

        The full report text goes to ``artifacts``; only the structured claims
        derived from it go to ``benchmark_claims`` (section 20, Stage 2).
        """
        session = self.require_session(session_id)
        report_text = self.require_text(report_text, "report_text")
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
            missing_evidence=missing,
            evidence_format_version=1,
            content_verified_by_runtime=False,
            sources_saved=saved_sources,
            next_step="save_benchmark_report" if missing else "generate_diagnostic",
        )

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
        """Record conflicting sources instead of silently picking one (17.4)."""
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
