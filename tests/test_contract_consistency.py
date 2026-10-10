"""Prevent tool docs, packaged specifications and bridge names from drifting."""
import asyncio
import json

from leap.config import REPO_ROOT
from leap.server import build_server
from scripts.generate_tool_reference import registered_tools, render


def test_reference_matches_registered_mcp_catalog():
    names = {n.name for n in registered_tools()}
    catalog = asyncio.run(build_server().list_tools())
    assert names == {t.name for t in catalog}
    assert (REPO_ROOT / "docs/mcp-tools.md").read_text(encoding="utf-8") == render()
    for name in ("README.md", "README_CN.md"):
        readme = (REPO_ROOT / name).read_text(encoding="utf-8")
        assert f"MCP-{len(names)}%20tools" in readme
        for required in ("submit_attempt", "commit_assessment", "record_reflection", "save_assessment_item"):
            assert f"`{required}`" in readme


def test_bridge_tools_exist_and_packaged_schema_matches():
    shared = REPO_ROOT / "examples/_shared/interaction-output.schema.json"
    packaged = REPO_ROOT / "src/leap/specs/interaction_output.schema.json"
    assert json.loads(shared.read_text(encoding="utf-8")) == json.loads(packaged.read_text(encoding="utf-8"))
    tools = json.loads(shared.read_text(encoding="utf-8"))["properties"]["outbox"]["items"]["properties"]["tool"]["enum"]
    assert set(tools) <= {n.name for n in registered_tools()}


def test_generated_pages_do_not_compute_runtime_evidence_stage():
    for page in (REPO_ROOT / "examples").rglob("*.html"):
        source = page.read_text(encoding="utf-8")
        assert "deriveStage(" not in source, page
        assert "mastery + (a.correctness" not in source, page
        assert 'enqueue("check_advance_unit"' in source, page


def test_no_manifest_is_not_a_passing_interaction_check(tmp_path):
    from scripts.verify_example_runtime import RuntimeReport, _exercise_scenarios
    report = RuntimeReport(tmp_path / "unknown.html")
    _exercise_scenarios(None, report.path, report)
    assert report.failures
