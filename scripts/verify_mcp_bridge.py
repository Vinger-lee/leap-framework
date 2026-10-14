"""Exercise the shipped math page against a real, isolated MCP stdio process.

This is an integration fixture, not a claim that subject sources were researched.
It never changes a host client's MCP registration or the user's LEAP database.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from playwright.async_api import async_playwright

from verify_example_runtime import _find_chromium

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from leap.server import build_server, registered_tool_names  # noqa: E402 - needs ROOT/src on the path


async def verify(database: Path, chromium: str | None):
    env = {**os.environ, "LEAP__DATABASE_PATH": str(database), "PYTHONPATH": str(ROOT / "src")}
    params = StdioServerParameters(command=sys.executable, args=["-m", "leap.server"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            catalog = (await session.list_tools()).tools
            names = {t.name for t in catalog}
            assert {"submit_attempt", "commit_assessment", "record_reflection", "schedule_review", "check_advance_unit", "save_assessment_item", "save_teaching_package", "get_teaching_delivery_policy", "get_subject_catalog"} <= names
            # Compare against the in-process catalog of the default profile
            # instead of a hard-coded number, so adding a tool cannot leave a
            # stale constant behind.
            assert len(catalog) == len(registered_tool_names(build_server("full")))

            async def call(name, args):
                result = await session.call_tool(name, args)
                assert not result.is_error, (name, result)
                data = result.structured_content
                if not data:
                    data = json.loads(next(c.text for c in result.content if c.type == "text"))
                assert data.get("ok") is True, (name, data)
                return data

            created = await call("create_session", {"learner_id": "integration-learner", "topic": "Controlled equation fixture"})
            sid = created["session_id"]
            baseline = await call("save_benchmark_report", {
                "session_id": sid, "report_text": "Synthetic integration fixture: 3x+5=20 gives x=5.",
                "source_refs": [{"source": "controlled test fixture", "source_type": "test_fixture", "locator": "equation fixture", "excerpt": "3x+5=20; 3x=15; x=5"}],
                "verification": {"scope": "Only this controlled integration fixture", "claims": [{"claim": "x=5 satisfies the equation", "source_index": 0}],
                                 "worked_examples": [{"problem": "3x+5=20", "solution": "x=5", "check_method": "substitution", "check_result": "3*5+5=20"}],
                                 "limitations": ["Not a real source-reading or exam-content audit"]},
            })
            assert baseline["domain_grounding_stage"] == "completed"
            await call("save_knowledge_nodes", {"session_id": sid, "nodes": [{"node_id": "bridge.equation", "title": "Equation fixture", "unit_tag": "bridge-fixture", "bloom_level": "understand", "transfer_requirements": "none"}]})
            await call("start_unit", {"session_id": sid, "node_id": "bridge.equation"})
            html = ROOT / "examples/02-math-linear-equation/leap-02-math-linear-equation.html"
            manifest = json.loads(html.with_suffix(".delivery.json").read_text(encoding="utf-8"))
            manifest["source_ids"] = baseline["sources_saved"]
            package = await call("save_teaching_package", {"session_id": sid, "node_id": "bridge.equation", "subject": "math", "markdown": (html.parent/"knowledge.md").read_text(encoding="utf-8"), "html": html.read_text(encoding="utf-8"), "manifest": manifest})
            await call("save_assessment_item", {"session_id": sid, "item_id": "q2", "node_id": "bridge.equation", "question": "Solve 3x+5=20", "expected_answer": "x=5", "solution": "3x=15 then x=5", "assumptions": ["x is real"], "verification_checks": [{"method": "substitution", "result": "3*5+5=20"}], "assessor_scope": "exact_answer", "teaching_package_id": package["package_id"], "source_ids": baseline["sources_saved"]})
            ctx = await call("get_teaching_context", {"session_id": sid})
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=chromium)
                try:
                    page = await browser.new_page()
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    await page.goto(html.as_uri())
                    await page.evaluate("ctx => window.LEAP.hydrate(ctx)", ctx)
                    await page.locator("#step1").fill("3x=15")
                    await page.locator("#btnStep1").click()
                    await page.locator("#step2").fill("x=5")
                    await page.locator("#btnStep2").click()
                    pending = await page.evaluate("window.LEAP.drainOutbox()")
                    results = {}
                    executed = []
                    for queued in pending:
                        args = dict(queued["args"])
                        for key, value in args.items():
                            match = re.fullmatch(r"\{\{(call_\d+)\.(\w+)\}\}", value) if isinstance(value, str) else None
                            if match:
                                args[key] = results[match[1]][match[2]]
                        results[queued["call_id"]] = await call(queued["tool"], args)
                        executed.append(queued["tool"])
                    assert executed == ["submit_attempt", "submit_attempt", "commit_assessment", "check_advance_unit"], executed
                    history = await call("get_assessment_history", {"session_id": sid, "node_id": "bridge.equation"})
                    assert history["results"][0]["raw_answer"] == "step2: x=5"
                    confirmed = await page.evaluate("results => window.LEAP.applyToolResults(results)", results)
                    assert confirmed["assessment"]["provisional"] is False
                    assert confirmed["assessment"]["reasoning_quality"] is None
                    assert confirmed["ui_state"]["completed"] is False
                    refreshed = await call("get_teaching_context", {"session_id": sid})
                    hydrated = await page.evaluate("ctx => window.LEAP.hydrate(ctx)", refreshed)
                    assert hydrated["assessment"]["evidence_stage"] == refreshed["knowledge_state"]["evidence_stage"]
                    review = await call("schedule_review", {"learner_id": "integration-learner", "node_id": "bridge.equation", "session_id": sid})
                    assert review["ok"]
                    assert not errors, errors
                    return {"ok": True, "registered_tools": len(catalog), "executed_page_tools": executed,
                            "teaching_package_registered": True, "assessment_receipt_confirmed": True,
                            "persisted_raw_answer": history["results"][0]["raw_answer"],
                            "runtime_stage": refreshed["knowledge_state"]["evidence_stage"],
                            "scope": "real MCP stdio + Chromium + temporary SQLite; synthetic content fixture"}
                finally:
                    await browser.close()


def main():
    chromium = _find_chromium(None)
    with tempfile.TemporaryDirectory(prefix="leap-bridge-") as folder:
        result = asyncio.run(verify(Path(folder) / "integration.db", chromium))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
