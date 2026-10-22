"""Session, goal and diagnostic tools (section 22.1 / 22.2)."""

from __future__ import annotations

import json
from typing import Any, Mapping

from leap.storage import new_id, now_ts
from leap.tools.base import LeapToolMixin, ToolError, json_dumps

__all__ = ["SessionTools"]

#: Dimensions a diagnostic must cover (section 5.2).
DIAGNOSTIC_DIMENSIONS: tuple[str, ...] = (
    "prerequisites",
    "core_concepts",
    "basic_application",
    "higher_level_application",
    "initial_transfer",
    "misconceptions",
    "confidence",
    "confidence_calibration",
)

#: Task types the host agent may choose from (section 5.2).
DIAGNOSTIC_TASK_TYPES: tuple[str, ...] = (
    "multiple_choice",
    "short_answer",
    "derivation",
    "coding",
    "feynman_explanation",
    "variation_problem",
    "open_ended",
    "mini_project",
)

DOMAIN_GROUNDING_NOTICE_KEY = "domain_grounding.notice"

#: Deprecated: kept so external callers that imported the constant keep working.
#: Prefer ``service.t("domain_grounding.notice")``, which respects the locale.
DOMAIN_GROUNDING_NOTICE = (
    "即将执行【领域自学校准】，我会先学习该专题，生成知识基准报告后再对你开展教学。"
    "此过程会消耗更多 Token 并需要等待一段时间，但可以显著提升知识准确性。"
    "是否继续？或者你希望跳过该环节（跳过会增大回答幻觉、内容出错风险）？"
)


class SessionTools(LeapToolMixin):
    """Session lifecycle, learning goals and learner diagnostics."""

    # ------------------------------------------------------------------
    # 22.1 Session / Goal
    # ------------------------------------------------------------------
    def create_session(
        self,
        learner_id: str,
        topic: str,
        *,
        learner_name: str | None = None,
        allow_skip_domain_grounding: bool | None = None,
        domain_grounding_warn_user: bool | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Create a learning session. learner_id is required (P0 is single-learner).

        Domain-grounding switches are stored per session, not globally. When
        domain_grounding_warn_user is true the returned notice must be shown to
        the user before the grounding stage starts.
        """
        learner_id = self.require_text(learner_id, "learner_id")
        topic = self.require_text(topic, "topic")

        allow_skip = (
            bool(self.conf("allow_skip_domain_grounding", False))
            if allow_skip_domain_grounding is None
            else bool(allow_skip_domain_grounding)
        )
        warn_user = (
            bool(self.conf("domain_grounding_warn_user", True))
            if domain_grounding_warn_user is None
            else bool(domain_grounding_warn_user)
        )

        self.ensure_learner(learner_id, learner_name)
        session_id = new_id("ses")
        ts = now_ts()

        with self.db.transaction():
            self.db.execute(
                "INSERT INTO learning_sessions "
                "(session_id, learner_id, topic, status, current_node_id, state_version, "
                " allow_skip_domain_grounding, domain_grounding_warn_user, domain_grounding_stage, "
                " created_at, updated_at) "
                "VALUES (?, ?, ?, 'active', NULL, 1, ?, ?, 'pending', ?, ?)",
                (session_id, learner_id, topic, int(allow_skip), int(warn_user), ts, ts),
            )

        self.events.emit(
            "session_created",
            session_id=session_id,
            learner_id=learner_id,
            payload={"topic": topic, "allow_skip_domain_grounding": allow_skip},
            request_id=request_id,
        )

        return self.ok(
            session_id=session_id,
            learner_id=learner_id,
            topic=topic,
            state_version=1,
            domain_grounding_stage="pending",
            allow_skip_domain_grounding=allow_skip,
            domain_grounding_warn_user=warn_user,
            domain_grounding_notice=(
                self.t(DOMAIN_GROUNDING_NOTICE_KEY) if warn_user else None
            ),
            next_step="domain_grounding",
            guidance=(
                "Domain Grounding is mandatory unless allow_skip_domain_grounding is true. "
                "Call save_benchmark_report before generate_diagnostic."
            ),
        )

    def find_session(self, learner_id: str, topic: str | None = None) -> dict:
        """Find existing sessions by learner and optionally topic.

        Use this to recover a session id after a chat window is reopened.
        """
        learner_id = self.require_text(learner_id, "learner_id")
        if topic:
            rows = self.rows(
                "SELECT * FROM learning_sessions WHERE learner_id = ? AND topic = ? "
                "ORDER BY updated_at DESC LIMIT 20",
                (learner_id, topic),
            )
        else:
            rows = self.rows(
                "SELECT * FROM learning_sessions WHERE learner_id = ? "
                "ORDER BY updated_at DESC LIMIT 20",
                (learner_id,),
            )
        return self.ok(learner_id=learner_id, count=len(rows), sessions=rows)

    def get_session_info(self, session_id: str) -> dict:
        """Return session state, the latest goal, node count and the next lifecycle step."""
        session = self.require_session(session_id)
        goal = self.db.query_one(
            "SELECT * FROM learning_goals WHERE session_id = ? ORDER BY rowid DESC LIMIT 1",
            (session_id,),
        )
        node_count = int(
            self.db.scalar(
                "SELECT COUNT(*) FROM knowledge_nodes WHERE session_id = ?", (session_id,), 0
            )
        )
        return self.ok(
            session=session,
            learning_goal=dict(goal) if goal else None,
            knowledge_node_count=node_count,
            event_count=self.events.count(session_id),
            next_step=self._next_step(session, node_count),
        )

    def save_learning_goal(
        self,
        session_id: str,
        goal: str | None = None,
        *,
        target_domain: str | None = None,
        target_outcome: str | None = None,
        target_depth: str | None = None,
        time_budget: int | None = None,
        prior_knowledge: str | None = None,
        constraints: str | None = None,
        materials: str | None = None,
        assessment_requirements: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Persist the learning goal and its constraints (lifecycle Stage 1)."""
        session = self.require_session(session_id)
        goal_id = new_id("goal")
        ts = now_ts()
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO learning_goals "
                "(goal_id, session_id, goal, target_domain, target_outcome, target_depth, "
                " time_budget, prior_knowledge, constraints, materials, assessment_requirements, "
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    goal_id, session_id, goal, target_domain, target_outcome, target_depth,
                    time_budget, prior_knowledge, constraints, materials,
                    assessment_requirements, ts, ts,
                ),
            )
            self.db.execute(
                "UPDATE learning_sessions SET updated_at = ? WHERE session_id = ?", (ts, session_id)
            )
        self.events.emit(
            "goal_created", session_id=session_id, learner_id=session["learner_id"],
            payload={"goal_id": goal_id, "target_depth": target_depth}, request_id=request_id,
        )
        return self.ok(goal_id=goal_id, session_id=session_id)

    def get_learning_goal(self, session_id: str) -> dict:
        """Return the most recently saved learning goal for a session."""
        self.require_session(session_id)
        row = self.db.query_one(
            "SELECT * FROM learning_goals WHERE session_id = ? ORDER BY rowid DESC LIMIT 1",
            (session_id,),
        )
        if row is None:
            return self.ok(session_id=session_id, learning_goal=None)
        return self.ok(session_id=session_id, learning_goal=dict(row))

    # ------------------------------------------------------------------
    # 32. Custom learning configuration
    # ------------------------------------------------------------------
    def set_learning_configuration(
        self,
        session_id: str,
        *,
        request: str | None = None,
        mode: str | None = None,
        overrides: dict | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Apply a learner's requested learning mode (section 32).

        Pass the learner's own words in `request` - e.g. "以项目实战为主",
        "我要准备考试", "只学核心内容，尽快学会". Recognised modes are
        project_based / exam_prep / core_only / balanced. Stored as
        session-level Learning Configuration + Policy Overrides; the program is
        never modified, and unrecognised requests are reported back.
        """
        from leap.runtime.learning_modes import describe_modes, resolve_request

        session = self.require_session(session_id)
        resolved = resolve_request(request=request, mode=mode, extra_overrides=overrides)

        payload = {
            "mode": resolved["mode"],
            "overrides": resolved["overrides"],
            "preferences": resolved["preferences"],
            "requested": {"request": request, "mode": mode, "overrides": dict(overrides or {})},
        }
        ts = now_ts()
        with self.db.transaction():
            self.db.execute(
                "UPDATE learning_sessions SET learning_mode = ?, policy_overrides = ?, "
                "updated_at = ? WHERE session_id = ?",
                (resolved["mode"], json_dumps(payload), ts, session_id),
            )

        # Drop the cached overrides so the next policy evaluation sees them.
        self.policy.invalidate_overrides(session_id)

        self.events.emit(
            "learning_configuration_changed",
            session_id=session_id,
            learner_id=session["learner_id"],
            payload={"mode": resolved["mode"], "overrides": resolved["overrides"],
                     "unrecognised": resolved["unrecognised"]},
            request_id=request_id,
        )

        return self.ok(
            session_id=session_id,
            mode=resolved["mode"],
            overrides=resolved["overrides"],
            preferences=resolved["preferences"],
            unrecognised=resolved["unrecognised"],
            available_modes=[m["mode"] for m in describe_modes(self.i18n.locale)],
            note=(
                "Stored as session-level Learning Configuration + Policy Overrides. "
                "Preferences guide presentation only; they never bypass a State Guard check."
            ),
        )

    def get_learning_configuration(self, session_id: str) -> dict:
        """Return the session's active learning mode, overrides and preferences."""
        from leap.runtime.learning_modes import describe_modes

        self.require_session(session_id)
        raw = self.db.scalar(
            "SELECT policy_overrides FROM learning_sessions WHERE session_id = ?", (session_id,)
        )
        stored: dict = {}
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    stored = parsed
            except (TypeError, ValueError):
                stored = {}
        return self.ok(
            session_id=session_id,
            mode=self.policy.learning_mode(session_id),
            overrides=stored.get("overrides", {}),
            preferences=stored.get("preferences", {}),
            requested=stored.get("requested"),
            available_modes=describe_modes(self.i18n.locale),
        )

    # ------------------------------------------------------------------
    # 22.2 Diagnostic
    # ------------------------------------------------------------------
    def generate_diagnostic(self, session_id: str, *, request_id: str | None = None) -> dict:
        """Return a diagnostic blueprint.

        Rejected by the State Guard until Domain Grounding is completed, unless
        the session was created with allow_skip_domain_grounding=true.
        """
        session = self.require_session(session_id)
        decision = self.guard.check_domain_grounding(session_id)
        if not decision.allowed:
            self.events.emit(
                "state_guard_rejected",
                session_id=session_id,
                learner_id=session["learner_id"],
                payload={"tool": "generate_diagnostic", **decision.as_dict()},
                request_id=request_id,
            )
            raise ToolError("domain_grounding_required", decision.reason, decision.as_dict())

        goal_row = self.db.query_one(
            "SELECT * FROM learning_goals WHERE session_id = ? ORDER BY rowid DESC LIMIT 1",
            (session_id,),
        )
        goal = dict(goal_row) if goal_row else {}
        depth = str(self.conf("diagnostic_depth", "adaptive"))

        self.events.emit(
            "diagnostic_started",
            session_id=session_id,
            learner_id=session["learner_id"],
            payload={"depth": depth},
            request_id=request_id,
        )

        return self.ok(
            session_id=session_id,
            diagnostic_depth=depth,
            dimensions=list(DIAGNOSTIC_DIMENSIONS),
            available_task_types=list(DIAGNOSTIC_TASK_TYPES),
            target_depth=goal.get("target_depth"),
            time_budget=goal.get("time_budget"),
            prior_knowledge=goal.get("prior_knowledge"),
            guidance=(
                "Generate items with the host agent's LLM, then submit each answer through "
                "submit_diagnostic. Keep the probe short when prior_knowledge is high; extend "
                "it when prerequisites are unknown."
            ),
            generation_requirements=(
                "Fetch get_teaching_delivery_policy; write the full Obsidian Markdown source "
                "before a shorter HTML projection and register both with save_teaching_package. "
                "All learning modes retain this requirement."
            ),
            state_guard=decision.as_dict(),
        )

    def submit_diagnostic(
        self,
        session_id: str,
        answer: str,
        *,
        item_id: str | None = None,
        node_id: str | None = None,
        question: str | None = None,
        hint_level: int = 0,
        response_time: float | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Record a diagnostic answer under the same grounding and item gates as submit_attempt.

        Supplied questions require a registered item_id matching the question;
        register its canonical teaching package first. Without an item, only a
        general learner self-report is supported; it is not a registered quiz.
        """
        if question and not item_id:
            raise ToolError("assessment_item_required", "Register diagnostic questions with save_assessment_item before submitting answers")
        if question and item_id:
            self.require_session(session_id)
            item = self.db.query_one("SELECT question FROM assessment_items WHERE item_id = ? AND session_id = ?", (item_id, session_id))
            if not item or item["question"] != question:
                raise ToolError("assessment_item_mismatch", "Diagnostic question must match the registered item")
        return self.submit_attempt(session_id, answer, item_id=item_id, node_id=node_id,
                                   hint_level=hint_level, response_time=response_time, request_id=request_id)

    def get_diagnostic_result(self, session_id: str) -> dict:
        """Return the stored diagnostic summary plus every diagnostic attempt."""
        self.require_session(session_id)
        artifact = self.db.query_one(
            "SELECT * FROM artifacts WHERE session_id = ? AND artifact_type = 'diagnostic_result' "
            "ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        )
        attempts = self.rows(
            "SELECT la.attempt_id, la.node_id, la.answer, la.hint_level, la.created_at, "
            "       ar.overall_score, ar.correctness, ar.evidence_stage, ar.assessor_type "
            "FROM learning_attempts la "
            "LEFT JOIN assessment_results ar ON ar.attempt_id = la.attempt_id "
            "WHERE la.session_id = ? ORDER BY la.created_at ASC",
            (session_id,),
        )
        return self.ok(
            session_id=session_id,
            diagnostic_completed=artifact is not None,
            diagnostic_result=dict(artifact) if artifact else None,
            attempt_count=len(attempts),
            attempts=attempts,
        )

    def save_diagnostic_result(
        self,
        session_id: str,
        result: Any,
        *,
        request_id: str | None = None,
    ) -> dict:
        """Persist the diagnostic summary and mark the diagnostic phase complete."""
        session = self.require_session(session_id)
        artifact_id = new_id("art")
        ts = now_ts()
        payload = result if isinstance(result, str) else json_dumps(result)

        with self.db.transaction():
            self.db.execute(
                "INSERT INTO artifacts "
                "(artifact_id, learner_id, session_id, artifact_type, path_or_uri, content, "
                " metadata, version, created_at) VALUES (?, ?, ?, 'diagnostic_result', ?, ?, ?, '1', ?)",
                (artifact_id, session["learner_id"], session_id, None, payload, None, ts),
            )
            self.db.execute(
                "UPDATE learning_sessions SET updated_at = ? WHERE session_id = ?", (ts, session_id)
            )
        self.events.emit(
            "diagnostic_completed", session_id=session_id, learner_id=session["learner_id"],
            payload={"artifact_id": artifact_id}, request_id=request_id,
        )
        return self.ok(artifact_id=artifact_id, session_id=session_id)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _next_step(session: dict, node_count: int) -> str:
        if session.get("domain_grounding_stage") != "completed" and not session.get(
            "allow_skip_domain_grounding"
        ):
            return "domain_grounding"
        goal = session.get("session_id")
        if node_count == 0:
            return "knowledge_representation"
        if not session.get("current_node_id"):
            return "diagnostic"
        return "teaching"
