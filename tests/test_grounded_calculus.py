"""Production stdio guards for the reviewed higher-mathematics course."""

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from leap.runtime import grounding
from leap.tools import ToolError, build_service


@asynccontextmanager
async def tutor(database, profile):
    root = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "leap.server", "--tool-profile", profile],
        env={**os.environ, "LEAP__DATABASE_PATH": str(database), "PYTHONPATH": str(root / "src")},
    )
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()

        async def call(tool, **arguments):
            result = await session.call_tool(tool, arguments)
            assert not result.is_error, result
            return result.structured_content or json.loads(result.content[0].text)

        yield call


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["full", "quickstart"])
async def test_production_rejects_host_attestation_and_waiver(tmp_path, profile):
    async with tutor(tmp_path / "grounding.sqlite", profile) as call:
        session = await call("start_learning", learner_id="calculus-test", topic="高等数学")
        sid = session["session_id"]
        report = await call(
            "save_benchmark_report", session_id=sid, report_text="A synthetic source",
            source_refs=[{"source": "https://grounding-example.invalid", "source_type": "textbook",
                          "locator": "x", "excerpt": "x", "last_verified": 1}],
            verification={"scope": "Unrelated", "claims": [{"claim": "x", "source_index": 0}],
                          "worked_examples": [{"problem": "x", "solution": "x", "check_method": "x", "check_result": "x"}],
                          "limitations": []},
        )
        assert report.get("domain_grounding_stage") != "completed"
        waiver = await call("set_domain_grounding_skip", session_id=sid, allow_skip=True)
        assert waiver["ok"] is False
        assert (await call("continue_lesson", session_id=sid))["error"]["code"] == "domain_grounding_required"


@pytest.mark.asyncio
async def test_reviewed_calculus_can_ground_and_resume(tmp_path):
    database = tmp_path / "calculus.sqlite"
    async with tutor(database, "quickstart") as call:
        session = await call("start_learning", learner_id="student", topic="高数")
        sid = session["session_id"]
        assert session["next_call"]["tool"] == "get_grounding_sources"
        evidence = await call("get_grounding_sources", session_id=sid)
        assert evidence["course_id"] == "calculus.limits-derivative"
        assert {record["point_id"] for record in evidence["sources"]} == {
            "calculus.limit", "calculus.derivative", "calculus.differentiability",
        }
        args = dict(session_id=sid, report_text="Derivation and sided limits checked",
                    course_revision=evidence["course_revision"],
                    chunk_ids=[record["chunk_id"] for record in evidence["sources"]],
                    check_answers={"jump": "does_not_exist", "square_at_two": "4", "absolute_at_zero": "-1,1"})
        wrong = await call("save_benchmark_report", **{**args, "check_answers": {}})
        assert wrong["ok"] is False
        from asyncio import gather

        report, replay = await gather(*(call("save_benchmark_report", **args, request_id="calculus-report-1") for _ in range(2)))
        assert report["domain_grounding_stage"] == "completed"
        assert report["artifact_id"] == replay["artifact_id"]
        unrelated = await call("start_learning", learner_id="student", topic="Python 递归")
        cross_course = await call("save_benchmark_report", **{**args, "session_id": unrelated["session_id"]})
        assert cross_course["error"]["code"] == "grounding_unsupported"
        assert (await call("get_learner_snapshot", session_id=unrelated["session_id"]))["ok"] is True
    async with tutor(database, "full") as call:
        result = await call("continue_lesson", session_id=sid)
        assert result["ok"] is True
        assert result["grounding"]["course_revision"] == evidence["course_revision"]
        reviewed = await call("get_grounding_sources", session_id=sid, include_lesson=True)
        lesson = reviewed["lesson"]
        assert 'id="leap-interaction-output"' in lesson["html"]
        assert "window.LEAP" in lesson["html"] and "data-leap-print" in lesson["html"]
        assert lesson["manifest"]["visual_contract"]["profile"] == "anatomy.v2"
        ids = [point["point_id"] for point in lesson["manifest"]["teaching_points"]]
        for point_id in ids:
            anchor = f'data-teaching-point="{point_id}"'
            assert anchor in lesson["html"] and anchor in lesson["print_draft"]["handout_html"]
        node_id = lesson["node"]["node_id"]
        await call("save_knowledge_nodes", session_id=sid, nodes=[lesson["node"]])
        package_args = {key: lesson[key] for key in ("subject", "markdown", "html", "manifest")}
        package_args.update(session_id=sid, node_id=node_id)
        tampered = await call("save_teaching_package", **{**package_args, "markdown": lesson["markdown"] + "\n随意改写"})
        assert tampered["error"]["code"] == "grounding_unreviewed_content"
        package = await call("save_teaching_package", **package_args)
        assert package["ok"] is True, package
        assert package["visual_contract_state"] == "current"
        item_args = {**lesson["items"][0], "session_id": sid, "node_id": node_id, "item_id": sid + ".item",
                     "teaching_package_id": package["package_id"]}
        assert (await call("save_assessment_item", **{**item_args, "expected_answer": "7"}))["error"]["code"] == "grounding_unreviewed_content"
        assert (await call("save_assessment_item", **item_args))["ok"] is True
        forged = await call("save_artifact", session_id=sid, learner_id="student", artifact_type="teaching_package",
                            content="synthetic", metadata={"course_revision": evidence["course_revision"]})
        assert forged["error"]["code"] == "reserved_artifact_type"
        print_args = {**lesson["print_draft"], "session_id": sid, "node_id": node_id,
                      "package_id": package["package_id"]}
        rejected = await call("save_print_materials", **{**print_args, "handout_html": "<p>任意讲义</p>"})
        assert rejected["error"]["code"] == "grounding_unreviewed_content"
        printed = await call("save_print_materials", **print_args)
        assert printed["ok"] is True, printed
        materials = await call("get_print_materials", session_id=sid, node_id=node_id, include_html=True)
        assert set(materials["documents"]) == {"combined", "handout", "workbook", "answers"}
        handout = materials["documents"]["handout"]
        body, bibliography = handout.split('<section class="print-bibliography', 1)
        assert "OpenStax" not in body and "MIT OpenCourseWare" not in body
        assert "参考文献" in bibliography and "Calculus Volume 1" in bibliography
        for record in reviewed["sources"]:
            assert f'>{record["url"]}</a>' in bibliography
        assert body.count("<figcaption>") == 3
        assert body.count("<strong>先做自检</strong>") == 3
        assert materials["documents"]["combined"].index("练习卷") < materials["documents"]["combined"].index("参考文献")
        assert "OpenStax" not in materials["documents"]["answers"]
        assert "h≠0 时才可以约去 h" in materials["documents"]["answers"]
        assert "h≠0 时才可以约去 h" not in materials["documents"]["workbook"]
        assert (await call("start_unit", session_id=sid, node_id=node_id))["ok"] is True
        attempt = await call("submit_answer", session_id=sid, node_id=node_id,
                             item_id=item_args["item_id"], answer=lesson["items"][0]["expected_answer"])
        assert attempt["ok"] is True and attempt["assessed"] is False


@pytest.mark.asyncio
async def test_old_waiver_and_report_remain_readable_but_do_not_authorize_teaching(tmp_path):
    from tests.conftest import complete_grounding

    database = tmp_path / "legacy.sqlite"
    old_service = build_service(database, strict_grounding=False)
    try:
        sid = old_service.create_session("student", "高数", allow_skip_domain_grounding=True)["session_id"]
        old = complete_grounding(old_service, sid, "Historical report")
    finally:
        old_service.close()
    async with tutor(database, "full") as call:
        assert (await call("get_artifact", artifact_id=old["artifact_id"]))["artifact"]["content"] == "Historical report"
        current = await call("continue_lesson", session_id=sid)
        assert current["error"]["code"] == "domain_grounding_required"
        assert (await call("get_session_info", session_id=sid))["next_step"] == "domain_grounding"


@pytest.mark.parametrize(("replacement", "code"), [
    ({"reviewed_on": "2024-01-01", "review_due_on": "2024-06-01"}, "grounding_expired"),
    ({"status": "withdrawn"}, "grounding_withdrawn"),
    ({"title": "修订后的微积分课程"}, "domain_grounding_required"),
])
def test_revalidation_blocks_old_receipts_without_erasing_history(monkeypatch, replacement, code):
    course = grounding.reviewed_course()
    svc = build_service()
    try:
        sid = svc.start_learning("student", "高数")["session_id"]
        evidence = svc.get_grounding_sources(sid)
        report = svc.save_benchmark_report(
            sid, "Read and checked", course_revision=evidence["course_revision"],
            chunk_ids=[record["chunk_id"] for record in evidence["sources"]],
            check_answers={point["check"]["id"]: point["check"]["answer"] for point in course["points"]},
        )
        monkeypatch.setattr(grounding, "reviewed_course", lambda: {**course, **replacement})
        with pytest.raises(ToolError) as caught:
            svc.continue_lesson(sid)
        assert caught.value.code == code
        assert svc.get_artifact(report["artifact_id"])["artifact"]["content"] == "Read and checked"
        assert svc.get_session_info(sid)["next_step"] == "domain_grounding"
    finally:
        svc.close()
