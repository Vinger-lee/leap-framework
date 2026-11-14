"""Packaging metadata must keep an installed wheel usable.

The repository checkout is the developer experience; a wheel is the deployed
one. These checks are static (no build toolchain or network required) so they
run in the normal test suite and in CI.
"""

from __future__ import annotations

import tomllib

from leap.config import (
    DEFAULT_CONFIG_PATH,
    PACKAGED_CONFIG_RESOURCE,
    REPO_ROOT,
    load_config,
)

PYPROJECT = REPO_ROOT / "pyproject.toml"


def _project() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_packaged_config_mirrors_the_repository_default():
    packaged = REPO_ROOT / "src" / "leap" / PACKAGED_CONFIG_RESOURCE
    assert packaged.is_file(), f"missing packaged config: {packaged}"
    assert packaged.read_bytes() == DEFAULT_CONFIG_PATH.read_bytes(), (
        "config/default.yaml and src/leap/config/default.yaml drifted; copy the "
        "repository file over the packaged mirror"
    )


def test_package_data_ships_config_specs_and_storage():
    data = _project()["tool"]["setuptools"]["package-data"]["leap"]
    for pattern in ("config/*.yaml", "specs/*.json", "storage/*.sql"):
        assert pattern in data, f"{pattern} missing from package-data: {data}"


def test_namespace_package_discovery_stays_off():
    find = _project()["tool"]["setuptools"]["packages"]["find"]
    assert find.get("namespaces") is False, (
        "data-only subdirectories (specs/, storage/, config/) must not be "
        "discovered as namespace packages"
    )


def test_mcp_dependency_floor_matches_the_api_in_use():
    deps = _project()["project"]["dependencies"]
    assert [dep for dep in deps if dep.startswith("mcp")] == ["mcp>=2.3,<3"], deps
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "mcp>=2.3,<3" in requirements


def test_console_entry_points_and_python_floor():
    project = _project()["project"]
    assert project["requires-python"] == ">=3.11"
    assert project["scripts"] == {
        "leap-mcp": "leap.server:main",
        "leap-doctor": "leap.doctor:main",
    }


def test_repository_checkout_loads_the_checked_in_config():
    config = load_config()
    assert config.source == DEFAULT_CONFIG_PATH
    assert config.get("tool_profile") == "full"
    assert config.get("database_path")
