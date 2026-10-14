"""Tool profiles: progressive exposure of a 70-tool surface.

These tests guard the two things that can go wrong with profile filtering: a
tool silently disappearing when it should stay, and a profile that quietly
degrades to "full" because of a typo or an mcp upgrade.
"""

from __future__ import annotations

import pytest

from leap.runtime.profiles import (
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


def test_quickstart_is_a_narrow_true_subset():
    full = set(registered_tool_names(build_server("full")))
    quickstart = set(registered_tool_names(build_server("quickstart")))

    assert quickstart == set(QUICKSTART_TOOL_NAMES)
    assert quickstart < full
    assert len(quickstart) < len(full)
    # The fine-grained tools an integration does not need on day one stay hidden.
    for hidden in ("commit_assessment", "submit_attempt", "advance_unit", "get_decision_log"):
        assert hidden not in quickstart


def test_quickstart_keeps_every_facade_tool_and_the_setup_path():
    quickstart = set(registered_tool_names(build_server("quickstart")))

    assert set(FACADE_TOOL_NAMES) <= quickstart
    # A complete lesson needs grounding, the DAG, the package and the items.
    for required in (
        "save_benchmark_report",
        "save_knowledge_nodes",
        "save_knowledge_edges",
        "validate_knowledge_dag",
        "save_teaching_package",
        "save_assessment_item",
        "generate_diagnostic",
        "generate_final_report",
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
