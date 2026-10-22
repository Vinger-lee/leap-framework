"""Guard query budgets and catalog work without timing-sensitive assertions."""

from __future__ import annotations

import asyncio

import pytest

from leap.runtime.metrics import LearningMetrics
from leap.runtime.policy import PolicyEngine
from leap.runtime.profiles import ALL_TOOL_NAMES, PROFILES
from leap.runtime.state_guard import StateGuard


def test_metrics_read_relevant_event_history_once(service, monkeypatch):
    sid = service.create_session("metrics-learner", "recursion")["session_id"]
    service.db.executemany(
        "INSERT INTO event_log "
        "(event_id, session_id, node_id, event_type, payload, created_at) VALUES (?,?,?,?,?,?)",
        [
            ("first", sid, "n1", "attempt_submitted", None, 100),
            ("second", sid, "n1", "attempt_submitted", None, 105),
            ("reached", sid, "n1", "assessment_committed", '{"stage_after":"demonstrated"}', 105),
            ("unreached", sid, "n2", "attempt_submitted", None, 110),
            ("noise", sid, "n3", "action_executed", None, 110),
        ],
    )
    scans = []
    original_query = service.db.query

    def record_scan(sql, params=()):
        rows = original_query(sql, params)
        if "SELECT rowid, event_type, node_id, payload, created_at FROM event_log" in sql:
            scans.append(len(rows))
        return rows

    monkeypatch.setattr(service.db, "query", record_scan)
    metrics = LearningMetrics(service.db, service.cfg)
    result = metrics.compute(sid)

    assert result["time_to_target_evidence"]["per_node"] == {
        "n1": {"seconds": 5, "attempts": 2, "total_attempts": 2},
        "n2": {"seconds": None, "attempts": None, "total_attempts": 1},
    }
    assert result["attempts_to_target_evidence"]["per_node"] == {"n1": 2, "n2": None}
    assert scans == [4], "Both indicators must share one scan, excluding unrelated events"
    assert metrics.time_to_target_evidence(sid) == result["time_to_target_evidence"]
    assert metrics.attempts_to_target_evidence(sid) == result["attempts_to_target_evidence"]

    # Reuse must be per computation: later evidence cannot be hidden by a cache.
    service.events.emit("attempt_submitted", session_id=sid, node_id="n2")
    assert metrics.compute(sid)["time_to_target_evidence"]["per_node"]["n2"]["total_attempts"] == 2


@pytest.mark.parametrize("reader", ["guard", "policy"])
def test_prerequisite_lookup_has_a_constant_query_budget(service, reader):
    sid = service.create_session("prerequisite-learner", "recursion")["session_id"]
    service.create_session("other-learner", "recursion")
    stages = [None, "estimated", "practiced", "demonstrated", "retained", "transferred"]
    service.save_knowledge_nodes(sid, [
        {"node_id": f"p{i}", "title": f"prerequisite {i}"} for i in range(len(stages))
    ] + [{"node_id": "target", "title": "target"}])
    # Deliberately non-lexical insertion order is part of the existing result.
    order = [2, 5, 0, 3, 1, 4]
    service.save_knowledge_edges(sid, [
        {"pre_node_id": f"p{i}", "post_node_id": "target"} for i in order
    ])
    for i, stage in enumerate(stages):
        if stage is not None:
            service.db.execute(
                "INSERT INTO learner_knowledge_state "
                "(learner_id, node_id, evidence_stage, updated_at) VALUES (?,?,?,?)",
                ("prerequisite-learner", f"p{i}", stage, 100),
            )
    # A different learner's demonstrated state must not satisfy p0.
    service.db.execute(
        "INSERT INTO learner_knowledge_state "
        "(learner_id, node_id, evidence_stage, updated_at) VALUES (?,?,?,?)",
        ("other-learner", "p0", "demonstrated", 100),
    )
    statements = []
    service.db.connection.set_trace_callback(statements.append)
    try:
        if reader == "guard":
            component = StateGuard(service.db, service.cfg)
            missing = component._unmet_prerequisites("prerequisite-learner", "target")
        else:
            component = PolicyEngine(service.db, service.cfg)
            missing = component._prerequisite_status("prerequisite-learner", "target")["missing"]
    finally:
        service.db.connection.set_trace_callback(None)

    assert missing == ["p2", "p0", "p1"]
    reads = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
    expected = 1 if reader == "guard" else 2  # Policy also checks transfer evidence.
    assert len(reads) == expected, reads


@pytest.mark.parametrize("profile", ["full", "quickstart"])
def test_profile_only_builds_schemas_it_exposes(profile, monkeypatch):
    import leap.server as server_module

    guarded = []
    original_guard = server_module._guard

    def record_registration(fn):
        guarded.append(fn.__name__)
        return original_guard(fn)

    monkeypatch.setattr(server_module, "_guard", record_registration)
    server = server_module.build_server(profile)
    allowed = PROFILES[profile]
    expected = [name for name in ALL_TOOL_NAMES if allowed is None or name in allowed]

    assert server_module.registered_tool_names(server) == expected
    assert [tool.name for tool in asyncio.run(server.list_tools())] == expected
    assert guarded == expected


def test_profile_with_unknown_tools_fails_before_schema_generation(monkeypatch):
    import leap.server as server_module

    monkeypatch.setitem(PROFILES, "broken", ("not_registered",))

    def unexpected_registration(fn):
        pytest.fail("invalid profiles must be rejected before generating schemas")

    monkeypatch.setattr(server_module, "_guard", unexpected_registration)
    with pytest.raises(RuntimeError, match="unregistered tools.*not_registered"):
        server_module.build_server("broken")


def test_quickstart_preserves_full_catalog_contracts():
    from leap.server import build_server

    full = asyncio.run(build_server("full").list_tools())
    quickstart = asyncio.run(build_server("quickstart").list_tools())
    expected = [tool.model_dump(mode="json", by_alias=True) for tool in full
                if tool.name in PROFILES["quickstart"]]

    assert [tool.model_dump(mode="json", by_alias=True) for tool in quickstart] == expected
