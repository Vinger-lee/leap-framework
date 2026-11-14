"""Future hosts receive the visual workflow through real MCP, in either profile."""
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from tests.test_teaching_delivery import current_visual_pair


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["full", "quickstart"])
async def test_host_receives_visual_workflow_and_registration_checks(tmp_path, profile):
    root = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "leap.server", "--tool-profile", profile],
        env={**os.environ, "LEAP__DATABASE_PATH": str(tmp_path / "visual.sqlite"),
             "PYTHONPATH": str(root / "src")},
    )
    async with asyncio.timeout(40), stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()

            async def call(name, arguments):
                result = await session.call_tool(name, arguments)
                assert not result.is_error, result
                return result.structured_content or json.loads(next(c.text for c in result.content if c.type == "text"))

            policy = (await call("get_teaching_delivery_policy", {}))["policy"]
            guidance = policy["host_guidance"]["generation"]
            # Runtime instructions route to the policy tool; the full contract is
            # fetched explicitly instead of being duplicated per response.
            assert "get_teaching_delivery_policy" in initialized.instructions
            assert policy["visualization"]["authoring_profile"] == "anatomy.v2"
            assert policy["visualization"]["inspection_behavior"]["preview"]
            assert policy["visualization"]["contract"]["manifest_fragment"]["visual_contract"]["research"]

            started = await call("start_learning", {"learner_id": "future-host", "topic": "Synthetic instrument"})
            sid = started["session_id"]
            assert started["policy_version"] == policy["version"]
            blocked = await call("generate_diagnostic", {"session_id": sid})
            assert blocked["ok"] is False
            assert blocked["error"]["code"] == "domain_grounding_required"
            assert blocked["policy_version"] == policy["version"]

            md, html, manifest = current_visual_pair()
            source = manifest["visual_contract"]["research"]["sources"][0]
            report = await call("save_benchmark_report", {
                "session_id": sid, "report_text": "Synthetic source evidence for MCP integration only.",
                "source_refs": [{"source_id": source["evidence_source_id"], "source_type": "test_fixture",
                                 **{k: source[k] for k in ("source", "locator", "excerpt")}}],
                "verification": {
                    "scope": "Synthetic elapsed-time fixture", "claims": [{"claim": source["excerpt"], "source_index": 0}],
                    "worked_examples": [{"problem": "Time = 2", "solution": "Output = 2",
                                         "check_method": "Identity substitution", "check_result": "Equal"}],
                    "limitations": ["Not real reading or scientific verification"],
                },
            })
            assert report["domain_grounding_stage"] == "completed"
            await call("save_knowledge_nodes", {"session_id": sid, "nodes": [
                {"node_id": "sensor", "title": "Synthetic sensor", "unit_tag": "optics"}]})
            args = {"session_id": sid, "node_id": "sensor", "subject": "physics",
                    "markdown": md, "html": html, "manifest": manifest}
            source["evidence_source_id"] = "unrelated-source"
            rejected = await call("save_teaching_package", args)
            assert rejected["ok"] is False
            assert rejected["error"]["code"] == "invalid_source"
            source["evidence_source_id"] = report["sources_saved"][0]
            saved = await call("save_teaching_package", args)
            assert saved["ok"] is True, saved
            assert saved["validation"]["visual_authoring"]["visual_contract_state"] == "current"
            assert saved["visual_contract_state"] == "current"
            assert saved["validation"]["content_verified_by_runtime"] is False
            diagnostic = await call("generate_diagnostic", {"session_id": sid})
            assert diagnostic["generation_requirements"] == guidance


def test_authoring_specs_project_the_same_workflow(service):
    policy = service.get_teaching_delivery_policy()["policy"]
    for response in (service.get_web_component_spec(), service.get_obsidian_structure()):
        assert response["delivery_requirements"] == policy
        assert response["spec"]["generation_requirements"] == policy["host_guidance"]["generation"]
        assert response["spec"]["visualization"] == policy["visualization"]
