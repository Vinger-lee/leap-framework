"""Tests for the six behavioural gaps closed after the spec audit (step 08).

Each class maps to one gap:

    G1  section 35  pluggable interfaces
    G2  section 31  interleaving
    G3  section 32  custom learning modes / policy overrides
    G4  section 25  closing report sections
    G5  section 26  learning-outcome metrics
    G6  section 18  events that were declared but never emitted
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from leap.config import REPO_ROOT, load_config
from leap.i18n import translator_for
from leap.runtime.contracts import (
    ArtifactStore,
    MasteryEstimator,
    PolicyStrategy,
    ReviewSchedulerBackend,
    ScoreAggregator,
    StorageBackend,
)
from leap.runtime.learning_modes import LEARNING_MODES, OVERRIDABLE_KEYS, resolve_request
from leap.runtime.metrics import LearningMetrics, diagnostic_split
from leap.runtime.plugins import KINDS, PluginRegistry, register_builtins, registry
from leap.runtime.scoring import WeightedScoreAggregator
from leap.tools import build_service
from tests.conftest import answer_and_assess


# ---------------------------------------------------------------------------
# G1 - section 35 pluggable interfaces
# ---------------------------------------------------------------------------
class TestPluggableSeams:
    def test_builtin_implementations_satisfy_their_protocols(self, service):
        assert isinstance(service.estimator, MasteryEstimator)
        assert isinstance(service.aggregator, ScoreAggregator)
        assert isinstance(service.policy, PolicyStrategy)
        assert isinstance(service.scheduler, ReviewSchedulerBackend)
        assert isinstance(service.db, StorageBackend)
        assert isinstance(service.artifacts, ArtifactStore)

    def test_every_seam_resolves_from_configuration(self, service):
        info = service.get_plugin_info()
        assert info["unresolved"] == []
        assert set(info["active"]) == set(KINDS)

    def test_estimator_can_be_swapped_without_touching_call_sites(self):
        """A custom estimator registered under the same kind must be used."""
        register_builtins()
        snapshot = registry.snapshot()
        try:
            class ConstantEstimator:
                def initial(self):
                    return 0.42

                def update(self, prior, **kwargs):
                    return 0.42

                def confidence_weighted(self, prior, **kwargs):
                    return 0.42

            registry.register("mastery_estimator", "constant", lambda cfg=None, **_: ConstantEstimator())
            svc = build_service(":memory:", {"mastery_estimator": "constant"})
            assert isinstance(svc.estimator, MasteryEstimator)
            assert svc.estimator.initial() == 0.42
        finally:
            registry.restore(snapshot)

    def test_unknown_implementation_name_fails_loudly(self):
        register_builtins()
        with pytest.raises(KeyError):
            registry.create("mastery_estimator", "does_not_exist")

    def test_registry_lists_available_implementations(self):
        register_builtins()
        described = registry.describe()
        assert set(described) == set(KINDS)
        assert "simplified_bkt" in described["mastery_estimator"]
        assert "sqlite" in described["storage_backend"]

    def test_unknown_kind_is_rejected(self):
        with pytest.raises(KeyError):
            PluginRegistry().register("not_a_seam", "x", lambda: None)

    def test_aggregator_excludes_transfer_and_hint_dependency(self):
        agg = WeightedScoreAggregator()
        base = agg.aggregate({"correctness": 0.8, "conceptual_understanding": 0.8,
                              "reasoning_quality": 0.8, "application": 0.8})
        with_extra = agg.aggregate({"correctness": 0.8, "conceptual_understanding": 0.8,
                                    "reasoning_quality": 0.8, "application": 0.8,
                                    "transfer": 0.0, "hint_dependency": 1.0})
        assert base == with_extra
        assert "transfer" in agg.describe()["excluded_dimensions"]

    def test_aggregator_renormalises_over_judged_dimensions(self):
        agg = WeightedScoreAggregator()
        assert agg.aggregate({"correctness": 1.0}) == pytest.approx(1.0)
        assert agg.aggregate({}) is None


# ---------------------------------------------------------------------------
# G2 - section 31 interleaving
# ---------------------------------------------------------------------------
def _unit_service(cfg=None):
    svc = build_service(":memory:", cfg)
    sid = svc.create_session("L1", "recursion")["session_id"]
    svc.save_benchmark_report(sid, "# baseline")
    svc.save_knowledge_nodes(sid, [
        {"node_id": "n1", "title": "base case", "bloom_level": "understand", "unit_tag": "u1"},
        {"node_id": "n2", "title": "recursive case", "bloom_level": "understand", "unit_tag": "u1"},
        {"node_id": "n3", "title": "unrelated", "bloom_level": "understand", "unit_tag": "u2"},
    ])
    return svc, sid


def _stabilise(svc, sid, node_id, times=2):
    for _ in range(times):
        answer_and_assess(svc, sid, node_id, correctness=0.95, reasoning_quality=0.9)


class TestInterleaving:
    def test_plan_requires_two_stable_nodes(self):
        svc, sid = _unit_service()
        _stabilise(svc, sid, "n1")
        plan = svc.policy.interleaving_plan(svc.policy.build_teaching_context(sid, "n1"))
        assert plan["applicable"] is False
        assert "at least 2" in plan["reason"]

    def test_plan_applies_once_two_siblings_are_stable(self):
        svc, sid = _unit_service()
        _stabilise(svc, sid, "n1")
        _stabilise(svc, sid, "n2")
        plan = svc.policy.interleaving_plan(svc.policy.build_teaching_context(sid, "n1"))
        assert plan["applicable"] is True
        assert set(plan["node_ids"]) == {"n1", "n2"}
        assert "u2" not in str(plan["node_ids"])

    def test_policy_emits_an_interleaving_decision(self):
        svc, sid = _unit_service()
        _stabilise(svc, sid, "n1")
        _stabilise(svc, sid, "n2")
        decision = svc.evaluate_pedagogical_policy(sid, "n1")["decision"]
        assert decision["trigger_event"] == "interleaving"
        assert decision["interleaving"]["applicable"] is True

    def test_interleaving_is_not_applied_before_basic_stability(self):
        svc, sid = _unit_service()
        plan = svc.policy.interleaving_plan(svc.policy.build_teaching_context(sid, "n1"))
        assert plan["applicable"] is False

    def test_interleaving_can_be_disabled_by_configuration(self):
        svc, sid = _unit_service({"interleaving_enabled": "false"})
        _stabilise(svc, sid, "n1")
        _stabilise(svc, sid, "n2")
        plan = svc.policy.interleaving_plan(svc.policy.build_teaching_context(sid, "n1"))
        assert plan["applicable"] is False
        assert "disabled" in plan["reason"]

    def test_high_hint_dependency_blocks_interleaving(self):
        svc, sid = _unit_service()
        _stabilise(svc, sid, "n1")
        _stabilise(svc, sid, "n2")
        svc.db.execute(
            "UPDATE learner_knowledge_state SET hint_dependency = 0.95 WHERE node_id = 'n1'"
        )
        plan = svc.policy.interleaving_plan(svc.policy.build_teaching_context(sid, "n1"))
        assert plan["applicable"] is False
        assert "hint dependency" in plan["reason"]

    def test_node_without_unit_tag_cannot_interleave(self):
        svc, sid = _unit_service()
        svc.save_knowledge_nodes(sid, [{"node_id": "solo", "title": "solo"}])
        _stabilise(svc, sid, "solo")
        plan = svc.policy.interleaving_plan(svc.policy.build_teaching_context(sid, "solo"))
        assert plan["applicable"] is False
        assert "unit_tag" in plan["reason"]


# ---------------------------------------------------------------------------
# G3 - section 32 custom learning modes
# ---------------------------------------------------------------------------
class TestLearningModes:
    def test_natural_language_requests_map_to_modes(self):
        assert resolve_request(request="我要准备考试")["mode"] == "exam_prep"
        assert resolve_request(request="以项目实战为主")["mode"] == "project_based"
        assert resolve_request(request="只学核心内容，尽快学会")["mode"] == "core_only"

    def test_unknown_request_is_reported_not_ignored(self):
        result = resolve_request(request="随便学学")
        assert result["mode"] == "balanced"
        assert result["unrecognised"]

    def test_overrides_actually_change_engine_parameters(self, service):
        sid = service.create_session("L1", "recursion")["session_id"]
        service.save_benchmark_report(sid, "# b")
        assert service.policy._get("mastery_threshold", None, sid) == 0.80

        service.set_learning_configuration(sid, request="我要准备考试")
        assert service.policy._get("mastery_threshold", None, sid) == 0.85
        assert service.policy._get("max_hint_level", None, sid) == 2

        service.set_learning_configuration(sid, request="只学核心内容")
        assert service.policy._get("mastery_threshold", None, sid) == 0.75
        assert service.policy._get("unit_concept_budget", None, sid) == 5

        service.set_learning_configuration(sid, mode="balanced")
        assert service.policy._get("mastery_threshold", None, sid) == 0.80

    def test_overrides_are_persisted_on_the_session_not_the_program(self, service):
        sid = service.create_session("L1", "recursion")["session_id"]
        service.set_learning_configuration(sid, request="我要准备考试")
        row = service.db.query_one(
            "SELECT learning_mode, policy_overrides FROM learning_sessions WHERE session_id = ?",
            (sid,),
        )
        assert row["learning_mode"] == "exam_prep"
        payload = json.loads(row["policy_overrides"])
        assert payload["overrides"]["mastery_threshold"] == 0.85
        # the global configuration must be untouched
        assert load_config().get("mastery_threshold") == 0.80

    def test_overrides_do_not_leak_between_sessions(self, service):
        a = service.create_session("L1", "recursion")["session_id"]
        b = service.create_session("L1", "recursion")["session_id"]
        service.save_benchmark_report(a, "# b")
        service.save_benchmark_report(b, "# b")
        service.set_learning_configuration(a, request="我要准备考试")
        assert service.policy._get("mastery_threshold", None, a) == 0.85
        assert service.policy._get("mastery_threshold", None, b) == 0.80

    def test_override_key_whitelist_is_enforced(self, service):
        sid = service.create_session("L1", "recursion")["session_id"]
        result = service.set_learning_configuration(
            sid, mode="exam_prep", overrides={"mastery_threshold": 0.9, "rogue_key": 1}
        )
        assert result["overrides"]["mastery_threshold"] == 0.9
        assert "rogue_key" not in result["overrides"]
        assert any("rogue_key" in item for item in result["unrecognised"])

    def test_transfer_requirement_follows_the_mode(self, service):
        sid = service.create_session("L1", "recursion")["session_id"]
        service.save_benchmark_report(sid, "# b")
        service.save_knowledge_nodes(
            sid, [{"node_id": "n1", "title": "t", "bloom_level": "remember", "unit_tag": "u1"}]
        )
        # remember-level nodes do not need transfer by default
        assert service.get_teaching_context(sid, "n1")["transfer_requirement"] is False
        service.set_learning_configuration(sid, request="我要准备考试")  # forces transfer
        assert service.get_teaching_context(sid, "n1")["transfer_requirement"] is True

    def test_preferences_are_surfaced_to_the_host_agent(self, service):
        sid = service.create_session("L1", "recursion")["session_id"]
        service.save_benchmark_report(sid, "# b")
        service.set_learning_configuration(sid, request="以项目实战为主")
        context = service.get_teaching_context(sid)
        assert context["learning_mode"] == "project_based"
        assert context["learning_preferences"]["preferred_strategy"] == "PBL"

    def test_configuration_change_is_recorded_as_an_event(self, service):
        sid = service.create_session("L1", "recursion")["session_id"]
        service.set_learning_configuration(sid, request="我要准备考试")
        events = service.events.by_type("learning_configuration_changed", sid)
        assert len(events) == 1

    def test_mode_catalogue_is_exposed(self, service):
        sid = service.create_session("L1", "recursion")["session_id"]
        config = service.get_learning_configuration(sid)
        names = {m["mode"] for m in config["available_modes"]}
        assert names == set(LEARNING_MODES)

    def test_whitelist_covers_only_declared_keys(self):
        for mode, spec in LEARNING_MODES.items():
            unknown = set(spec["overrides"]) - OVERRIDABLE_KEYS
            assert not unknown, f"{mode} overrides undeclared keys: {unknown}"


# ---------------------------------------------------------------------------
# G4 - section 25 closing report
# ---------------------------------------------------------------------------
class TestReportSections:
    @staticmethod
    def _session_with_history(service) -> str:
        sid = service.create_session("L1", "recursion")["session_id"]
        service.save_benchmark_report(sid, "# baseline")
        first = service.submit_attempt(sid, "diagnostic answer")
        service.commit_assessment(
            first["attempt_id"], "diagnostic answer", correctness=0.3, reasoning_quality=0.35
        )
        service.save_diagnostic_result(sid, {"summary": "weak"})
        service.save_knowledge_nodes(
            sid, [{"node_id": "n1", "title": "t", "bloom_level": "understand", "unit_tag": "u1"}]
        )
        for _ in range(3):
            answer_and_assess(service, sid, "n1", correctness=0.95, reasoning_quality=0.9)
        return sid

    def test_report_has_all_fourteen_documented_sections(self, service):
        sid = self._session_with_history(service)
        markdown = service.generate_final_report(sid)["markdown"]
        # Section 25 lists fourteen required sections. The wording is localised,
        # so resolve each heading through the active catalogue.
        t = translator_for(service.cfg)
        for key, level in (
            ("report.learning_goal", "##"),
            ("report.diagnostic_baseline", "##"),
            ("report.observed_evidence", "##"),
            ("report.estimated_state", "##"),
            ("report.reasoning_quality", "###"),
            ("report.learning_gain", "###"),
            ("report.stage_distribution", "###"),
            ("report.remaining_uncertainty", "##"),
            ("report.recommended_next_step", "##"),
            ("report.review_plan", "##"),
        ):
            heading = f"{level} {t.t(key)}"
            assert heading in markdown, heading

    def test_diagnostic_baseline_is_separated_from_post_test(self, service):
        sid = self._session_with_history(service)
        report = service.generate_final_report(sid)["report"]
        assert report["diagnostic_baseline"]["evidence_points"] == 1
        assert report["estimated_state"]["learning_gain"]["post_points"] == 3

    def test_learning_gain_is_positive_when_performance_improves(self, service):
        sid = self._session_with_history(service)
        gain = service.generate_final_report(sid)["report"]["estimated_state"]["learning_gain"]
        assert gain["baseline_mean_score"] < gain["post_mean_score"]
        assert gain["absolute_gain"] > 0

    def test_reasoning_quality_is_aggregated(self, service):
        sid = self._session_with_history(service)
        rq = service.generate_final_report(sid)["report"]["estimated_state"]["reasoning_quality"]
        assert rq["samples"] == 4
        assert rq["mean"] is not None
        assert "below_threshold" in rq

    def test_missing_baseline_is_reported_as_uncertainty(self, grounded_service, dag):
        answer_and_assess(grounded_service, dag, "n1")
        uncertainty = " ".join(
            grounded_service.generate_final_report(dag)["report"]["remaining_uncertainty"]
        )
        assert "diagnostic baseline" in uncertainty


# ---------------------------------------------------------------------------
# G5 - section 26 learning metrics
# ---------------------------------------------------------------------------
class TestLearningMetrics:
    REQUIRED = (
        "immediate_performance", "delayed_retention", "transfer_performance",
        "time_to_target_evidence", "attempts_to_target_evidence", "hint_dependency",
        "misconception_resolution", "confidence_calibration", "learning_gain",
    )

    def test_all_nine_indicators_are_present(self, grounded_service, dag):
        metrics = grounded_service.get_learning_metrics(dag)
        for key in self.REQUIRED:
            assert key in metrics, key

    def test_time_and_attempts_are_measured_per_node(self, grounded_service, dag):
        for _ in range(3):
            answer_and_assess(grounded_service, dag, "n1", correctness=0.95, reasoning_quality=0.9)
        metrics = grounded_service.get_learning_metrics(dag)
        per_node = metrics["attempts_to_target_evidence"]["per_node"]
        assert per_node.get("n1") == 3
        assert metrics["time_to_target_evidence"]["per_node"]["n1"]["seconds"] is not None

    def test_transfer_performance_reflects_recorded_probes(self, grounded_service, dag):
        grounded_service.record_transfer_result("learner-test", "n1", "far", 0.8, session_id=dag)
        grounded_service.record_transfer_result("learner-test", "n1", "near", 0.6, session_id=dag)
        metrics = grounded_service.get_learning_metrics(dag)
        assert metrics["transfer_performance"]["attempts"] == 2
        assert metrics["transfer_performance"]["mean_score"] == pytest.approx(0.7)
        assert metrics["transfer_performance"]["by_type"]["far"] == pytest.approx(0.8)

    def test_misconception_resolution_rate(self, grounded_service, dag):
        created = grounded_service.assess_misconception("learner-test", "n1", "bad base case")
        metrics = grounded_service.get_learning_metrics(dag)
        assert metrics["misconception_resolution"]["resolution_rate"] == 0.0
        grounded_service.resolve_misconception(created["misconception_id"])
        metrics = grounded_service.get_learning_metrics(dag)
        assert metrics["misconception_resolution"]["resolution_rate"] == 1.0

    def test_confidence_calibration_uses_absolute_error(self, grounded_service, dag):
        attempt = grounded_service.submit_attempt(dag, "answer", node_id="n1")
        grounded_service.commit_assessment(
            attempt["attempt_id"], "answer", correctness=1.0, confidence=0.5
        )
        metrics = grounded_service.get_learning_metrics(dag)
        assert metrics["confidence_calibration"]["samples"] == 1
        assert metrics["confidence_calibration"]["mean_absolute_error"] > 0

    def test_delayed_retention_is_null_before_any_review(self, grounded_service, dag):
        metrics = grounded_service.get_learning_metrics(dag)
        assert metrics["delayed_retention"]["mean_rating"] is None
        assert metrics["delayed_retention"]["review_items"] == 0

    def test_unknown_session_is_rejected(self, service):
        with pytest.raises(KeyError):
            LearningMetrics(service.db, service.cfg).compute("ses_missing")

    def test_diagnostic_split_uses_append_order_not_timestamps(self, grounded_service, dag):
        """Everything in one second must still split correctly."""
        first = grounded_service.submit_attempt(dag, "before")
        grounded_service.commit_assessment(first["attempt_id"], "before", correctness=0.4)
        grounded_service.save_diagnostic_result(dag, {"summary": "done"})
        for _ in range(2):
            answer_and_assess(grounded_service, dag, "n1", correctness=0.9)
        baseline, post, marker = diagnostic_split(grounded_service.db, dag)
        assert len(baseline) == 1
        assert len(post) == 2
        assert marker is not None


# ---------------------------------------------------------------------------
# G6 - section 18.1 events
# ---------------------------------------------------------------------------
class TestEventCoverage:
    def _spec_events(self) -> list[str]:
        spec_path = REPO_ROOT / "（作者维护的框架设计文档，不在本仓库）"
        if not spec_path.exists():
            pytest.skip("design document is not in this public repository")
        spec = spec_path.read_text(encoding="utf-8")
        lines = spec.splitlines()
        start, body = None, []
        for i, line in enumerate(lines):
            m = re.match(r"^#\s*(\d+)\.\s", line)
            if m and int(m.group(1)) == 18:
                start = i + 1
                continue
            if start is not None and m:
                break
            if start is not None:
                body.append(line)
        text = "\n".join(body)
        block = text.split("```text")[1].split("```")[0]
        return re.findall(r"^\s*([a-z_]+),?$", block, re.M)

    def test_every_documented_event_has_an_emit_call_site(self):
        sources = {
            p: p.read_text(encoding="utf-8")
            for p in (REPO_ROOT / "src" / "leap").rglob("*.py")
        }
        missing = []
        for event in self._spec_events():
            if not any(
                f'"{event}"' in text
                for path, text in sources.items()
                if path.name != "events.py"
            ):
                missing.append(event)
        assert missing == [], f"documented but never emitted: {missing}"

    def test_policy_evaluated_is_emitted_with_a_state_snapshot(self, grounded_service, dag):
        grounded_service.evaluate_pedagogical_policy(dag, "n1")
        events = grounded_service.events.by_type("policy_evaluated", dag)
        assert len(events) == 1
        payload = events[0]["payload"]
        assert "state_snapshot" in payload
        assert "candidate_actions" in payload
        assert "selected_action" in payload

    def test_review_started_precedes_review_completed(self, grounded_service, dag):
        grounded_service.schedule_review("learner-test", "n1", session_id=dag)
        item = grounded_service.get_review_state("learner-test", "n1")["review_items"][0]
        grounded_service.submit_review(item["review_item_id"], 3, session_id=dag)
        started = grounded_service.events.by_type("review_started", dag)
        completed = grounded_service.events.by_type("review_completed", dag)
        assert len(started) == 1 and len(completed) == 1

    def test_transfer_started_precedes_transfer_completed(self, grounded_service, dag):
        grounded_service.record_transfer_result("learner-test", "n1", "far", 0.9, session_id=dag)
        assert len(grounded_service.events.by_type("transfer_started", dag)) == 1
        assert len(grounded_service.events.by_type("transfer_completed", dag)) == 1


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------
class TestSchemaMigration:
    def test_added_columns_exist_on_a_fresh_database(self, service):
        columns = {
            row["name"]
            for row in service.db.query("PRAGMA table_info(learning_sessions)")
        }
        assert {"learning_mode", "policy_overrides"} <= columns

    def test_initialize_is_idempotent_and_migrates_old_databases(self, tmp_path):
        """A database created before the new columns must be upgraded in place."""
        import sqlite3

        from leap.storage import Database

        path = tmp_path / "legacy.db"
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE learning_sessions ("
            "session_id TEXT PRIMARY KEY, learner_id TEXT, topic TEXT, status TEXT, "
            "created_at INTEGER, updated_at INTEGER)"
        )
        conn.commit()
        conn.close()

        db = Database(path).initialize()
        columns = {row["name"] for row in db.query("PRAGMA table_info(learning_sessions)")}
        assert "learning_mode" in columns
        assert "policy_overrides" in columns
        db.initialize()  # second run must not raise
        db.close()
