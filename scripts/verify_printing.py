"""Check actual A4 PDFs, continuation pages and course-page delivery over MCP."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname
import re
import sys
from tempfile import TemporaryDirectory

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from playwright.async_api import async_playwright

from verify_example_runtime import _find_chromium

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from leap.printing import EDITIONS, PrintSettings, build_documents, render_pdf
from leap.tools import build_service
from verify_teaching_repository import _registration_sources, _replace_placeholders

PRINT = ROOT / "print-examples/linear-equations"


def page_dimensions(pdf: bytes) -> list[tuple[float, float]]:
    return [(float(x), float(y)) for x, y in re.findall(rb"/MediaBox\s*\[0 0 ([\d.]+) ([\d.]+)\]", pdf)]


def check_paper(pdf: bytes, orientation: str, pages: int | None = None) -> None:
    assert pdf.startswith(b"%PDF-")
    sizes = page_dimensions(pdf)
    assert sizes and (pages is None or len(sizes) == pages), sizes
    w, h = (595.28, 841.89) if orientation == "portrait" else (841.89, 595.28)
    assert all(abs(width - w) < 1 and abs(height - h) < 1 for width, height in sizes), sizes


def seed(database: Path, course: Path, page: dict) -> str:
    """Register the shipped teaching pair with synthetic evidence in a temporary DB."""
    svc = build_service(database)
    try:
        sid = svc.create_session("print-reader", "linear equations")["session_id"]
        manifest = json.loads(course.with_suffix(".delivery.json").read_text(encoding="utf-8"))
        report = svc.save_benchmark_report(
            sid, "Synthetic evidence for the course-to-print integration check.",
            source_refs=_registration_sources(manifest),
            verification={
                "scope": "Register the shipped linear-equation teaching pair",
                "claims": [{"claim": "The fixture uses the registered course manifest.", "source_index": 0}],
                "worked_examples": [{
                    "problem": "Check the course and print balance example 3x + 5 = 20.",
                    "solution": "x = 5", "check_method": "Substitution", "check_result": "3 × 5 + 5 = 20",
                }],
                "limitations": ["Synthetic registration for integration verification only."],
            },
        )
        manifest = _replace_placeholders(manifest, report["sources_saved"])
        node_id = page["node_id"]
        svc.save_knowledge_nodes(sid, [{"node_id": node_id, "title": "一元一次方程", "unit_tag": "linear-equation"}])
        svc.start_unit(sid, node_id=node_id)
        svc.save_teaching_package(
            sid, node_id, "math", (course.parent / "knowledge.md").read_text(encoding="utf-8"),
            course.read_text(encoding="utf-8"), manifest,
        )
        return sid
    finally:
        svc.close()


async def check_bridge(database: Path, sid: str, chromium: str | None, spec: dict, handout: str) -> None:
    binding = spec["course"]
    course = ROOT / binding["html"]
    node_id = binding["node_id"]
    env = {**os.environ, "LEAP__DATABASE_PATH": str(database), "PYTHONPATH": str(ROOT / "src")}
    if chromium:
        env["LEAP_PRINT_CHROMIUM"] = chromium
    server = StdioServerParameters(command=sys.executable, args=["-m", "leap.server", "--tool-profile", "quickstart"], env=env)
    async with asyncio.timeout(120), stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        async def call(tool, args):
            receipt = await session.call_tool(tool, args)
            assert not receipt.is_error, receipt
            data = receipt.structured_content or json.loads(receipt.content[0].text)
            assert data["ok"], data
            return data

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=chromium)
            try:
                page = await browser.new_page(accept_downloads=True)
                await page.context.add_init_script("window.print = () => { window.printCalled = true; }")
                await page.goto(course.as_uri())
                snapshot = await page.evaluate("window.LEAP.getInteractionResult()")
                assert snapshot["example_id"] == binding["example_id"]
                assert snapshot["node"]["node_id"] == node_id

                # Every offline button must open its own edition for this course.
                for edition in EDITIONS:
                    await page.locator("[data-print-edition]").select_option(edition)
                    async with page.expect_popup() as opened:
                        await page.locator("[data-print-button]").click()
                    preview = await opened.value
                    await preview.wait_for_function("window.printCalled === true")
                    assert url2pathname(urlsplit(preview.url).path) == str(PRINT / f"{edition}.html")
                    assert await preview.locator("main").get_attribute("data-edition") == edition
                    assert await preview.locator(".print-version").inner_text() == f'版本 {spec["version"]}'
                    questions = await preview.locator("article[data-question]").count()
                    assert questions == (0 if edition == "handout" else len(spec["questions"]))
                    await preview.close()

                context = await call("get_teaching_context", {"session_id": sid, "node_id": node_id})
                await page.evaluate("ctx => window.LEAP.hydrate(ctx)", context)
                await page.locator("[data-print-edition]").select_option("combined")
                await page.locator("[data-print-orientation]").select_option("landscape")
                await page.locator("[data-print-button]").click()
                queued, = await page.evaluate("window.LEAP.drainOutbox()")
                assert queued["tool"] == "export_print_pdf"
                assert queued["args"]["edition"] == "combined" and queued["args"]["node_id"] == node_id
                missing = await call(queued["tool"], queued["args"])
                assert missing["status"] == "needs_authoring"
                await page.evaluate("data => window.LEAP.applyToolResults(data)", {queued["call_id"]: missing})
                source = await call(missing["next_call"]["tool"], missing["next_call"]["arguments"])
                assert source["source"]["markdown"]
                point_ids = {point["point_id"] for point in source["source"]["teaching_points"]}
                assert set(re.findall(r'data-teaching-point="([^"]+)"', handout)) == point_ids
                assert {point for question in spec["questions"] for point in question["point_ids"]} == point_ids
                draft = {
                    "session_id": sid, "node_id": node_id, "package_id": source["source"]["package_id"],
                    "title": spec["title"], "language": spec["language"],
                    "handout_html": handout, "questions": spec["questions"],
                }
                saved = await call("save_print_materials", draft)
                result = await call(queued["tool"], queued["args"])
                assert result["edition"] == "combined" and result["material_id"] == saved["material_id"]
                check_paper(base64.b64decode(result["pdf_base64"]), "landscape")
                async with page.expect_download() as downloaded:
                    await page.evaluate("data => window.LEAP.applyToolResults(data)", {queued["call_id"]: result})
                download = await downloaded.value
                assert download.suggested_filename.endswith("-combined.pdf")
                assert (await download.path()).read_bytes() == base64.b64decode(result["pdf_base64"])

                # Another version was authored after the user downloaded the worksheet.
                newer = await call("save_print_materials", {**draft, "title": "Revised equations"})
                assert newer["material_id"] != saved["material_id"]
                await page.locator("[data-print-edition]").select_option("answers")
                await page.locator("[data-print-button]").click()
                answer_call, = await page.evaluate("window.LEAP.drainOutbox()")
                assert answer_call["args"]["material_id"] == saved["material_id"]
                answer = await call(answer_call["tool"], answer_call["args"])
                assert answer["edition"] == "answers" and answer["material_id"] == saved["material_id"]
                check_paper(base64.b64decode(answer["pdf_base64"]), "landscape")
            finally:
                await browser.close()


def main() -> None:
    chromium = _find_chromium(None)
    spec = json.loads((PRINT / "lesson.json").read_text(encoding="utf-8"))
    handout = (PRINT / "handout.fragment").read_text(encoding="utf-8")
    course = ROOT / spec["course"]["html"]
    assert "3x+5=20" in course.read_text(encoding="utf-8") and "3x + 5 = 20" in handout
    combined = PRINT / "combined.html"
    demo = render_pdf(combined.read_text(encoding="utf-8"), chromium=chromium)
    check_paper(demo, "portrait")
    assert len(page_dimensions(demo)) >= 2
    document = build_documents(
        "Multi-page answer", "<p>Handout</p>",
        [{"kind": "experiment", "prompt_html": "<p>Record the observations in the table.</p>",
          "answer_html": "<p>Answer guide.</p>",
          "answer_area": {"columns": ["Time (s)", "Distance (m)"], "lines": 35, "height_mm": 380}}],
        version="continuation-check",
    )["workbook"]
    long_pdf = render_pdf(document, PrintSettings("landscape"), chromium=chromium)
    check_paper(long_pdf, "landscape")
    assert 3 <= len(page_dimensions(long_pdf)) <= 4
    with TemporaryDirectory(prefix="leap-print-") as folder:
        db = Path(folder) / "print.sqlite"
        sid = seed(db, course, spec["course"])
        asyncio.run(check_bridge(db, sid, chromium, spec, handout))
    print("A4 pagination, all four offline editions, actual teaching package coverage and same-version MCP PDF download passed")


if __name__ == "__main__":
    main()
