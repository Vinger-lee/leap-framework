"""Tool profiles: progressive exposure of the registered tools.

These tests guard the two things that can go wrong with profile filtering: a
tool silently disappearing when it should stay, and a profile that quietly
degrades to "full" because of a typo or an mcp upgrade.
"""

from __future__ import annotations

import pytest

from leap.runtime.profiles import (
    ALL_TOOL_NAMES,
    DEFAULT_PROFILE,
    FACADE_TOOL_NAMES,
    PROFILES,
    QUICKSTART_TOOL_NAMES,
    allowed_tool_names,
    available_profiles,
    excluded_tool_names,
    resolve_profile,
)
from leap.server import build_server, registered_tool_names


def test_full_profile_exposes_every_registered_tool():
    names = registered_tool_names(build_server("full"))

    assert len(names) == len(set(names))
    assert allowed_tool_names("full") is None
    assert set(names) > set(FACADE_TOOL_NAMES)
    assert len(names) >= 62
    assert tuple(names) == ALL_TOOL_NAMES


def test_catalog_inspection_does_not_boot_the_runtime(monkeypatch):
    import asyncio
    import leap.server as server_module

    def unexpected_boot():
        pytest.fail("catalog inspection must not open the configured database")

    monkeypatch.setattr(server_module, "get_service", unexpected_boot)
    catalog = asyncio.run(build_server("full").list_tools())

    assert [tool.name for tool in catalog] == list(ALL_TOOL_NAMES)


def test_registered_tool_uses_the_process_service(service, monkeypatch):
    import asyncio
    import leap.server as server_module

    monkeypatch.setattr(server_module, "get_service", lambda: service)
    server = build_server("full")
    asyncio.run(server.call_tool("create_session", {"learner_id": "mcp-test", "topic": "recursion"}))
    asyncio.run(server.call_tool("save_artifact", {
        "learner_id": "mcp-test", "artifact_type": "code", "content": "print(1)",
    }))

    sessions = service.find_session("mcp-test")["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["topic"] == "recursion"
    artifact = service.db.query_one("SELECT session_id, content FROM artifacts WHERE artifact_type = 'code'")
    assert artifact["session_id"] is None
    assert artifact["content"] == "print(1)"


def test_artifact_catalog_preserves_optional_session():
    import asyncio

    catalog = asyncio.run(build_server("full").list_tools())
    tool = next(tool for tool in catalog if tool.name == "save_artifact")
    schema = tool.model_dump(by_alias=True)["inputSchema"]

    assert schema["required"] == ["learner_id", "artifact_type"]
    assert schema["properties"]["session_id"]["default"] is None
    assert "self" not in schema["properties"]


def test_quickstart_is_a_narrow_true_subset():
    full = set(registered_tool_names(build_server("full")))
    quickstart = set(registered_tool_names(build_server("quickstart")))

    assert quickstart == set(QUICKSTART_TOOL_NAMES)
    assert quickstart < full
    assert len(quickstart) < len(full)
    # The fine-grained tools an integration does not need on day one stay hidden.
    for hidden in ("submit_attempt", "advance_unit", "get_decision_log"):
        assert hidden not in quickstart


def test_quickstart_keeps_every_facade_tool_and_the_setup_path():
    quickstart = set(registered_tool_names(build_server("quickstart")))

    assert set(FACADE_TOOL_NAMES) <= quickstart
    # A complete lesson needs grounding, the DAG, the package and the items.
    for required in (
        "get_grounding_sources",
        "save_benchmark_report",
        "save_knowledge_nodes",
        "save_knowledge_edges",
        "validate_knowledge_dag",
        "save_teaching_package",
        "save_assessment_item",
        "generate_diagnostic",
        "generate_final_report",
        "commit_assessment",
        "resolve_misconception",
        "complete_session",
    ):
        assert required in quickstart


def test_every_profile_name_is_registered_in_the_full_catalog():
    """A typo in a profile tuple must fail here, not at runtime."""
    full = set(registered_tool_names(build_server("full")))

    for profile, names in PROFILES.items():
        if names is None:
            continue
        unknown = sorted(set(names) - full)
        assert not unknown, f"profile {profile!r} lists unregistered tools: {unknown}"


def test_quickstart_can_execute_the_misconception_next_call(dag, grounded_service, monkeypatch):
    import asyncio
    import json
    import leap.server as server_module

    misconception = grounded_service.assess_misconception(
        "learner-test", "n1", "Synthetic misconception", session_id=dag,
    )
    monkeypatch.setattr(server_module, "get_service", lambda: grounded_service)
    server = build_server("quickstart")

    async def exercise():
        response = await server.call_tool("continue_lesson", {"session_id": dag, "node_id": "n1"})
        lesson = response.structured_content or json.loads(response.content[0].text)
        target = lesson["next_call"]["tool"]
        assert target == "resolve_misconception"
        assert target in registered_tool_names(server)
        response = await server.call_tool(target, {
            "misconception_id": misconception["misconception_id"], "session_id": dag,
        })
        resolved = response.structured_content or json.loads(response.content[0].text)
        assert resolved["status"] == "resolved"
        assert grounded_service.get_mastery_status(dag, "n1")["misconception_ids"] == []

    asyncio.run(exercise())


def test_unknown_profile_is_refused_instead_of_silently_widening():
    with pytest.raises(ValueError) as excinfo:
        resolve_profile("quikstart")

    assert "unknown tool profile" in str(excinfo.value)
    with pytest.raises(ValueError):
        build_server("unlimited")


def test_default_profile_is_full_for_backwards_compatibility(monkeypatch):
    monkeypatch.delenv("LEAP_TOOL_PROFILE", raising=False)

    assert resolve_profile() == DEFAULT_PROFILE == "full"
    assert len(registered_tool_names(build_server())) == len(
        registered_tool_names(build_server("full"))
    )


def test_environment_variable_selects_the_profile(monkeypatch):
    monkeypatch.setenv("LEAP_TOOL_PROFILE", "quickstart")

    assert resolve_profile() == "quickstart"
    assert len(registered_tool_names(build_server())) == len(QUICKSTART_TOOL_NAMES)


def test_explicit_argument_beats_the_environment(monkeypatch):
    monkeypatch.setenv("LEAP_TOOL_PROFILE", "quickstart")

    assert resolve_profile("full") == "full"
    assert len(registered_tool_names(build_server("full"))) > len(QUICKSTART_TOOL_NAMES)


def test_config_fallback_is_used_when_nothing_else_is_set(monkeypatch):
    monkeypatch.delenv("LEAP_TOOL_PROFILE", raising=False)

    assert resolve_profile(None, fallback="quickstart") == "quickstart"
    # A stale config value that is not a profile must not be applied silently.
    with pytest.raises(ValueError):
        resolve_profile(None, fallback="lite")


def test_available_profiles_lists_the_documented_names():
    assert available_profiles() == ("quickstart", "full")


def test_excluded_tool_names_reports_what_is_hidden():
    full = registered_tool_names(build_server("full"))
    hidden = excluded_tool_names("quickstart", full)

    assert set(hidden) == set(full) - set(QUICKSTART_TOOL_NAMES)
    assert excluded_tool_names("full", full) == ()
