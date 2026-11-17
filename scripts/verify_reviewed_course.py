"""Verify production reviewed courseware through Chromium and real stdio MCP."""

from __future__ import annotations

import asyncio
import base64
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_example import verify
from scripts.verify_example_runtime import _find_chromium
from scripts.verify_printing import check_paper
from tests.test_grounded_calculus import tutor


async def verify_course(database: Path, chromium: str) -> None:
    async with tutor(database, "full") as call:
        session = await call("start_learning", learner_id="courseware-verifier", topic="高等数学")
        sid = session["session_id"]
        evidence = await call("get_grounding_sources", session_id=sid)
        receipt = await call(
            "save_benchmark_report", session_id=sid, report_text="Verify calculus worked examples",
            course_revision=evidence["course_revision"], chunk_ids=[row["chunk_id"] for row in evidence["sources"]],
            check_answers={"jump": "does_not_exist", "square_at_two": "4", "absolute_at_zero": "-1,1"},
        )
        assert receipt["ok"], receipt
        lesson = (await call("get_grounding_sources", session_id=sid, include_lesson=True))["lesson"]
        page_file = database.with_name("reviewed-calculus.html")
        page_file.write_text(lesson["html"], encoding="utf-8")
        report = verify(page_file)
        assert not report.errors, [(check.check_id, check.detail) for check in report.errors]

        await call("save_knowledge_nodes", session_id=sid, nodes=[lesson["node"]])
        node_id = lesson["node"]["node_id"]
        pair = {key: lesson[key] for key in ("subject", "markdown", "html", "manifest")}
        package = await call("save_teaching_package", session_id=sid, node_id=node_id, **pair)
        assert package["ok"] and package["visual_contract_state"] == "current", package
        package_id = package["package_id"]
        for index, item in enumerate(lesson["items"], 1):
            registered = await call("save_assessment_item", session_id=sid, node_id=node_id,
                                    item_id=f"{sid}.{index}", teaching_package_id=package_id, **item)
            assert registered["ok"], registered
        assert (await call("start_unit", session_id=sid, node_id=node_id))["ok"]
        context = await call("get_teaching_context", session_id=sid, node_id=node_id)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=chromium)
            try:
                page = await browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
                requests = []
                errors = []
                page.on("request", lambda request: requests.append(request.url))
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.set_content(lesson["html"], wait_until="load")
                expected_points = [point["point_id"] for point in lesson["manifest"]["teaching_points"]]
                actual_points = await page.locator("section[data-teaching-point]").evaluate_all(
                    "sections => sections.map(section => section.dataset.teachingPoint)")
                assert actual_points == expected_points
                for width in (375, 1440, 1920):
                    await page.set_viewport_size({"width": width, "height": 900})
                    assert await page.evaluate("document.documentElement.scrollWidth === innerWidth")
                    if width > 375:
                        assert await page.locator("main").evaluate("element => element.offsetWidth / innerWidth >= .88")
                slider = page.locator("#secant-h")
                assert await page.locator("#secant-value").inner_text() == "5"
                await slider.press("ArrowLeft")
                assert await page.locator("#secant-value").inner_text() == "4.5"
                assert float(await page.locator("#secant-q").get_attribute("cx")) == 324
                assert float(await page.locator("#secant-q").get_attribute("cy")) == 70.25
                for _ in range(3):
                    await slider.press("ArrowLeft")
                assert "未定义" in await page.locator("#secant-value").inner_text()
                assert await page.locator("#secant-line").get_attribute("visibility") == "hidden"
                await slider.press("ArrowLeft")
                assert await page.locator("#secant-value").inner_text() == "3.99"
                await page.locator("#secant-reset").click()
                assert await page.locator("#secant-value").inner_text() == "5"
                assert not await page.evaluate("LEAP.peekOutbox()")
                await page.evaluate("ctx => LEAP.hydrate(ctx)", context)

                async def drain(tool: str) -> dict:
                    calls = await page.evaluate("LEAP.drainOutbox()")
                    assert len(calls) == 1 and calls[0]["tool"] == tool, calls
                    return calls[0]

                raw = "左极限为 4，右极限为 7，所以双侧极限不存在。"
                await page.locator("#practice-1").fill(raw)
                await page.locator('[data-practice-index="0"] [data-submit-answer]').click()
                question = await drain("submit_attempt")
                assert question["args"]["item_id"] == f"{sid}.1"
                attempt = await call("submit_attempt", **question["args"])
                assert attempt["ok"], attempt
                await page.evaluate("([id, reply]) => LEAP.applyToolResults({[id]: reply})", [question["call_id"], attempt])
                assert (await page.evaluate("LEAP.getInteractionResult()"))["assessment"]["provisional"]
                assert "作答已保存" in await page.locator('[data-practice-index="0"] .practice-status').inner_text()
                with closing(sqlite3.connect(database)) as connection:
                    assert connection.execute("SELECT answer FROM learning_attempts WHERE attempt_id=?",
                                              (attempt["attempt_id"],)).fetchone() == (raw,)

                # Another artifact is now the newest one for this node. The open page
                # must still retrieve and download the package it actually hydrated.
                newer = await call("save_teaching_package", session_id=sid, node_id=node_id, **pair)
                assert newer["ok"] and newer["package_id"] != package_id, newer
                newer_context = await call("get_teaching_context", session_id=sid, node_id=node_id)
                assert newer_context["reviewed_package_id"] == newer["package_id"]
                refused = await page.evaluate("""ctx => {
                    try { LEAP.hydrate(ctx); return false; }
                    catch (error) { return error.message.includes('已绑定教学包'); }
                }""", newer_context)
                assert refused
                other_print = await call("save_print_materials", session_id=sid, node_id=node_id,
                                         package_id=newer["package_id"], **lesson["print_draft"])
                assert other_print["ok"], other_print
                await page.locator("[data-print-edition]").select_option("handout")
                await page.locator("[data-print-button]").click()
                export = await drain("export_print_pdf")
                assert export["args"]["package_id"] == package_id
                pending = await call("export_print_pdf", **export["args"])
                assert pending["status"] == "needs_authoring" and pending["package_id"] == package_id, pending
                await page.evaluate("([id, reply]) => LEAP.applyToolResults({[id]: reply})", [export["call_id"], pending])
                next_call = pending["next_call"]
                source = await call(next_call["tool"], **next_call["arguments"])
                action = source["next_call"]
                draft = await call(action["tool"], **action["arguments"])
                assert draft["ok"] and draft["package_id"] == package_id, draft
                materials = await call("get_print_materials", session_id=sid, node_id=node_id,
                                       package_id=package_id, include_html=True)
                assert materials["material_id"] == draft["material_id"]
                for point_id in expected_points:
                    assert f'data-teaching-point="{point_id}"' in materials["documents"]["handout"]
                pdf = await call("export_print_pdf", **export["args"])
                assert pdf["ok"] and pdf["material_id"] == draft["material_id"], pdf.get("error")
                async with page.expect_download() as download:
                    await page.evaluate("([id, reply]) => LEAP.applyToolResults({[id]: reply})", [export["call_id"], pdf])
                browser_download = await download.value
                title = lesson["node"]["title"]
                assert browser_download.suggested_filename == f"{title} - 讲义册.pdf"
                downloaded = await browser_download.path()
                assert downloaded.read_bytes() == base64.b64decode(pdf["pdf_base64"])
                check_paper(downloaded.read_bytes(), "portrait")

                exported = await call("export_print_pdf", session_id=sid, node_id=node_id, package_id=package_id)
                assert exported["ok"] and exported["material_id"] == draft["material_id"], exported
                directory = database.with_name("课程输出") / title
                assert Path(exported["output_directory"]) == directory
                course_html = directory / f"{title} - 教学课件.html"
                assert Path(exported["html_path"]) == course_html
                assert course_html.read_bytes() == lesson["html"].encode("utf-8")
                expected = {edition: directory / f"{title} - {label}.pdf" for edition, label in {
                    "combined": "合订册", "handout": "讲义册", "workbook": "题目册", "answers": "答案与解析",
                }.items()}
                assert {edition: Path(path) for edition, path in exported["pdf_paths"].items()} == expected
                assert set(directory.iterdir()) == {course_html, *expected.values()}
                for path in expected.values():
                    check_paper(path.read_bytes(), "portrait")
                assert not errors, errors
                assert not requests, requests
            finally:
                await browser.close()
    print("Reviewed course: layout, model, raw attempt, package-scoped downloads and named A4 course folder passed")


if __name__ == "__main__":
    executable = _find_chromium(None)
    if executable is None:
        raise SystemExit("Install the examples extra and Playwright Chromium")
    os.environ["LEAP_PRINT_CHROMIUM"] = executable
    with TemporaryDirectory(prefix="leap-reviewed-course-") as directory:
        root = Path(directory)
        os.environ["LEAP__COURSE_OUTPUT_ROOT"] = str(root / "课程输出")
        asyncio.run(verify_course(root / "course.sqlite", executable))
