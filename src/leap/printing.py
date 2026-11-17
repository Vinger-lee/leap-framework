"""Build static LEAP print editions and render self-contained HTML to A4 PDF."""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path
import re
import sys
from typing import Any, Sequence

EDITIONS = {"combined": "讲义与练习", "handout": "讲义册", "workbook": "题目册", "answers": "答案与解析"}
DEFAULT_COURSE_OUTPUT_ROOT = "~/LEAP/课程输出"
KINDS = {
    "single_choice": "choices", "multiple_choice": "choices", "true_false": "choices",
    "fill_blank": "blank", "short_answer": "lines", "calculation": "space",
    "derivation": "space", "proof": "space", "comprehensive": "space",
    "geometry": "grid", "graphing": "axes", "coding": "code", "experiment": "table",
}
AREAS = {"choices", "blank", "lines", "space", "grid", "axes", "code", "table"}
MAX_HTML_BYTES = 4 * 1024 * 1024
CSP = (
    "default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'; "
    "base-uri 'none'; form-action 'none'"
)


class PrintError(ValueError):
    """The print input or environment cannot produce the requested edition."""


@dataclass(frozen=True)
class PrintSettings:
    orientation: str = "portrait"
    margins_mm: Sequence[float] = (16, 16, 16, 16)

    def __post_init__(self) -> None:
        if self.orientation not in {"portrait", "landscape"}:
            raise PrintError("orientation must be portrait or landscape")
        if not isinstance(self.margins_mm, (list, tuple)) or len(self.margins_mm) != 4:
            raise PrintError("margins_mm must contain top, right, bottom, and left")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 80
               for v in self.margins_mm):
            raise PrintError("each margin must be between 0 and 80 mm")
        top, right, bottom, left = self.margins_mm
        width, height = self.sheet_mm
        if min(width - left - right, height - top - bottom) < 60:
            raise PrintError("leave at least 60 mm of printable width and height")
        object.__setattr__(self, "margins_mm", tuple(self.margins_mm))

    @property
    def sheet_mm(self) -> tuple[int, int]:
        return (210, 297) if self.orientation == "portrait" else (297, 210)

    def page_rule(self) -> str:
        margins = " ".join(f"{margin:g}mm" for margin in self.margins_mm)
        return f"@page {{ size: A4 {self.orientation}; margin: {margins}; }}"


class _Fragment(HTMLParser):
    """Check the contract for agent-authored static HTML fragments."""
    blocked = {
        "applet", "audio", "base", "body", "button", "embed", "form", "foreignobject",
        "frame", "frameset", "head", "html", "iframe", "input", "link", "meta", "object",
        "script", "select", "style", "template", "textarea", "video", "animate", "set",
    }
    raster = re.compile(r"^data:image/(?:png|jpeg|webp|gif);base64,", re.I)

    def __init__(self) -> None:
        super().__init__()
        self.has_content = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.blocked or tag.startswith("animate"):
            raise PrintError(f"<{tag}> is not supported in a print fragment")
        for name, value in attrs:
            value = (value or "").strip()
            if name.startswith("on") or name in {"srcdoc", "srcset", "poster", "ping"}:
                raise PrintError(f"{name} is not supported in a print fragment")
            if name == "src" and (tag != "img" or not self.raster.match(value)):
                raise PrintError("embed images as raster data URLs or inline SVG")
            if name in {"href", "xlink:href"} and not (
                value.startswith("#") or (tag == "a" and value.lower().startswith(("https://", "http://")))
            ):
                raise PrintError("use an in-document reference or a citation link")
            if name == "style" and re.search(r"url\s*\(|@import|@page", value, re.I):
                raise PrintError("inline style cannot load assets or change the page size")
        self.has_content |= tag in {"svg", "img", "math"}

    def handle_data(self, data: str) -> None:
        self.has_content |= bool(data.strip())


def _fragment(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value.encode("utf-8")) > MAX_HTML_BYTES:
        raise PrintError(f"{label} must be an HTML fragment of at most 4 MiB")
    parser = _Fragment()
    parser.feed(value)
    parser.close()
    if not parser.has_content:
        raise PrintError(f"{label} must contain printable content")
    return value


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise PrintError(f"{label} must be an integer from {minimum} to {maximum}")
    return value


def _choice_list(options: Any) -> list[str]:
    if not isinstance(options, list) or not 2 <= len(options) <= 12:
        raise PrintError("choice questions need two to twelve options_html entries")
    return [_fragment(option, "option") for option in options]


def _area(question: dict, default: str, number: int) -> str:
    config = question.get("answer_area", {})
    if not isinstance(config, dict):
        raise PrintError("answer_area must be an object")
    unknown = config.keys() - {"type", "height_mm", "lines", "line_numbers", "columns"}
    if unknown:
        raise PrintError(f"unknown answer_area fields: {', '.join(sorted(unknown))}")
    area = config.get("type", default)
    if not isinstance(area, str) or area not in AREAS:
        raise PrintError("unknown answer area type")
    if area == "choices":
        options = _choice_list(question.get("options_html", ["正确", "错误"] if question["kind"] == "true_false" else None))
        mark = "□" if question["kind"] == "multiple_choice" else "○"
        items = "".join(
            f'<li><span aria-hidden="true">{mark} {chr(65 + idx)}.</span><div>{item}</div></li>'
            for idx, item in enumerate(options)
        )
        return f'<ul class="answer-choices">{items}</ul>'
    if area == "blank":
        return '<p>答 <span class="answer-blank"></span></p>'

    rows = _integer(config.get("lines", 6 if area in {"table", "code"} else 4), "lines", 1, 40)
    default_height = {"lines": 28, "space": 45, "grid": 55, "axes": 55, "code": 42, "table": 42}
    height = _integer(config.get("height_mm", default_height[area]), "height_mm", 7, 500)
    if area == "table":
        columns = config.get("columns", ["测量量", "记录值"])
        if (not isinstance(columns, list) or not 1 <= len(columns) <= 10
                or not all(isinstance(x, str) and x.strip() for x in columns)):
            raise PrintError("columns must contain one to ten labels (include units in the labels)")
        headings = "".join(f'<th scope="col">{escape(x)}</th>' for x in columns)
        empty = "<tr>" + "<td>&nbsp;</td>" * len(columns) + "</tr>"
        return (f'<table class="answer-table"><thead><tr>{headings}</tr></thead>'
                f'<tbody style="--row-height:{height / rows:g}mm">{empty * rows}</tbody></table>')
    if area in {"lines", "code"}:
        numbered = config.get("line_numbers", False)
        if type(numbered) is not bool:
            raise PrintError("line_numbers must be a boolean")
        labels = "".join(
            f'<li>{idx + 1 if area == "code" and numbered else "&nbsp;"}</li>' for idx in range(rows)
        )
        return f'<ol class="answer-{area}" style="--row-height:{height / rows:g}mm">{labels}</ol>'
    extra = ""
    if area in {"grid", "axes"}:
        pattern = f"leap-grid-{number}"
        anchor = ' x="50%" y="50%"' if area == "axes" else ""
        axes = (
            '<line x1="0" y1="50%" x2="100%" y2="50%"/>'
            '<line x1="50%" y1="0" x2="50%" y2="100%"/>'
            '<text x="98%" y="50%" dy="-5" text-anchor="end">x</text>'
            '<text x="50%" y="4%" dx="5" dy="5">y</text>'
            '<text x="50%" y="50%" dx="-7" dy="12" text-anchor="end">0</text>'
        ) if area == "axes" else ""
        extra = (
            '<svg aria-hidden="true">'
            f'<defs><pattern id="{pattern}" width="5mm" height="5mm"{anchor} patternUnits="userSpaceOnUse">'
            '<path d="M0 18.898V0H18.898"/></pattern></defs>'
            f'<rect width="100%" height="100%" fill="url(#{pattern})"/>{axes}</svg>'
        )
    return f'<div class="answer-{area}" style="height:{height}mm">{extra}</div>'


def _question(question: dict, number: int) -> tuple[str, str]:
    if not isinstance(question, dict):
        raise PrintError(f"question {number} must be an object")
    kind = question.get("kind")
    if not isinstance(kind, str) or kind not in KINDS:
        raise PrintError(f"unknown question kind for question {number}")
    prompt = _fragment(question.get("prompt_html"), "prompt_html")
    answer = _fragment(question.get("answer_html"), "answer_html")
    if "options_html" in question and KINDS[kind] != "choices":
        raise PrintError("options_html is only supported for choice and judgment questions")
    options = ""
    default = KINDS[kind]
    area = _area(question, default, number)
    if default == "choices" and 'class="answer-choices"' not in area:
        options = _area({**question, "answer_area": {}}, default, number)
    first = question.get("new_page", False)
    if type(first) is not bool:
        raise PrintError("new_page must be a boolean")
    chunks = question.get("continuations", [])
    if not isinstance(chunks, list) or len(chunks) > 20:
        raise PrintError("continuations must be a list of up to twenty HTML fragments")
    title = question.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip() or len(title) > 80):
        raise PrintError("question title must contain 1 to 80 characters")
    label = f"第 {number} 题"
    heading = f'<h2><span class="question-label">{label}</span>{escape(title)}</h2>' if title else f"<h2>{label}</h2>"
    wrapper = f'<article class="print-question{" print-new-page" if first else ""}" data-question="{number}">'
    workbook = f'{wrapper}{heading}<div class="print-prompt">{prompt}{options}</div>{area}</article>'
    for chunk in chunks:
        workbook += (f'<article class="print-question print-new-page" data-question="{number}">'
                     f'<h2>第 {number} 题（续）</h2>{_fragment(chunk, "continuation")}</article>')
    return workbook, f'<article class="print-question" data-question="{number}">{heading}{answer}</article>'


def _print_controls(settings: PrintSettings) -> tuple[str, str]:
    paginator = files("leap").joinpath("print_assets/paginate.js").read_text(encoding="utf-8")
    script = files("leap").joinpath("print_assets/preview.js").read_text(encoding="utf-8")
    script = f'const paginatePrint = {paginator}; const printMargins = {list(settings.margins_mm)};{script}'
    digest = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    return (
        '<div class="print-controls"><button type="button" id="leapPrintNow">打印 / 另存为 PDF</button>'
        '<label for="leapPrintDirection">方向</label><select id="leapPrintDirection">'
        f'<option value="portrait"{" selected" if settings.orientation == "portrait" else ""}>纵向</option>'
        f'<option value="landscape"{" selected" if settings.orientation == "landscape" else ""}>横向</option>'
        '</select><p role="status" id="leapPrintNotice"></p></div>'
        f'<script>{script}</script>',
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}; script-src &#39;sha256-{digest}&#39;">',
    )


def build_documents(
    title: str, handout_html: str, questions: list[dict], *, version: str,
    settings: PrintSettings = PrintSettings(), language: str = "zh-CN", bibliography_html: str | None = None,
) -> dict[str, str]:
    """Compile independent editable HTML editions from the host's print draft."""
    if not isinstance(title, str) or not title.strip() or len(title) > 220:
        raise PrintError("title must contain 1 to 220 characters")
    if not isinstance(version, str) or not version.strip() or len(version) > 80:
        raise PrintError("version must contain 1 to 80 characters")
    if not isinstance(language, str) or not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", language):
        raise PrintError("language must be a language tag")
    handout = '<section class="print-handout">' + _fragment(handout_html, "handout_html") + "</section>"
    bibliography = ""
    if bibliography_html is not None:
        bibliography = ('<section class="print-bibliography print-new-page">'
                        + _fragment(bibliography_html, "bibliography_html") + "</section>")
    if not isinstance(questions, list) or not 1 <= len(questions) <= 100:
        raise PrintError("provide one to one hundred questions")
    pairs = [_question(question, idx) for idx, question in enumerate(questions, 1)]
    workbook = "".join(item[0] for item in pairs)
    answers = "".join(item[1] for item in pairs)
    css = files("leap").joinpath("print_assets/print.css").read_text(encoding="utf-8")
    safe_title, safe_version = escape(title), escape(version)
    controls, csp = _print_controls(settings)
    contents = {
        "handout": handout + bibliography, "workbook": workbook, "answers": answers,
        "combined": handout + '<section class="print-workbook print-new-page"><h2>练习卷</h2>'
                    + workbook + "</section>" + bibliography,
    }
    documents = {
        edition: (
            f'<!doctype html><html lang="{language}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'{csp}<title>{safe_title} · {EDITIONS[edition]}</title>'
            f'<style id="leapPaper">{settings.page_rule()}</style><style>{css}</style></head>'
            f'<body><main class="print-content" data-edition="{edition}"><header class="print-heading">'
            f'<p class="print-edition">{EDITIONS[edition]}</p>'
            f'<h1>{safe_title}</h1><p class="print-version">版本 {safe_version}</p></header>{content}</main>'
            f'{controls}</body></html>'
        )
        for edition, content in contents.items()
    }
    for edition, html in documents.items():
        if len(html.encode("utf-8")) > MAX_HTML_BYTES:
            raise PrintError(f"{edition} HTML exceeds 4 MiB")
    return documents


def render_pdf(html: str, settings: PrintSettings = PrintSettings(), *, chromium: str | None = None) -> bytes:
    """Render static, self-contained HTML without loading local or network resources."""
    if not isinstance(html, str) or not html.strip():
        raise PrintError("provide printable HTML")
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise PrintError("print HTML exceeds 4 MiB")
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError as exc:
        raise PrintError("install the print extra and run python -m playwright install chromium") from exc

    url = "https://leap-print.invalid/document"
    width, height = settings.sheet_mm
    top, right, bottom, left = settings.margins_mm
    width_px = round((width - left - right) * 96 / 25.4)
    height_px = (height - top - bottom) * 96 / 25.4
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=chromium or os.getenv("LEAP_PRINT_CHROMIUM"), timeout=15_000,
            )
            try:
                context = browser.new_context(service_workers="block", viewport={"width": width_px, "height": 900})
                def route_request(route):
                    if route.request.url == url and route.request.is_navigation_request():
                        route.fulfill(body=html, content_type="text/html; charset=utf-8",
                                      headers={"Content-Security-Policy": CSP})
                    else:
                        route.abort()
                context.route("**/*", route_request)
                page = context.new_page()
                page.set_default_timeout(12_000)
                page.emulate_media(media="print")
                page.goto(url, wait_until="load")
                page.evaluate("document.fonts.ready")
                page_css = settings.page_rule()
                page.evaluate(
                    """rule => {
                        for (const sheet of document.styleSheets) {
                            function normalizePageRules(group) {
                                for (let i = group.cssRules.length - 1; i >= 0; --i) {
                                    const css = group.cssRules[i];
                                    if (css.type === CSSRule.PAGE_RULE) {
                                        // Preserve named-page break policies, but normalize their geometry.
                                        for (const property of ["size", "margin", "margin-top", "margin-right",
                                                                "margin-bottom", "margin-left",
                                                                "page-orientation", "bleed", "marks"]) {
                                            css.style.removeProperty(property);
                                        }
                                    } else if (css.cssRules) normalizePageRules(css);
                                }
                            }
                            normalizePageRules(sheet);
                        }
                        const style = document.createElement('style');
                        style.textContent = rule;
                        document.head.append(style);
                    }""", page_css
                )
                js = files("leap").joinpath("print_assets/paginate.js").read_text(encoding="utf-8")
                issue = page.evaluate(js, height_px)
                if issue:
                    raise PrintError(issue)
                return page.pdf(format="A4", landscape=settings.orientation == "landscape",
                                prefer_css_page_size=True, print_background=True)
            finally:
                browser.close()
    except Error as exc:
        raise PrintError(
            "Chromium could not export this HTML. Install its browser with "
            "python -m playwright install chromium or select an installed Chromium."
        ) from exc


def write_html_editions(directory: Path, documents: dict[str, str]) -> None:
    """Create a new edition directory and undo partial writes on failure."""
    directory.mkdir(parents=True)
    written = []
    try:
        for edition, html in documents.items():
            target = directory / f"{edition}.html"
            with target.open("x", encoding="utf-8") as handle:
                written.append(target)
                handle.write(html)
    except OSError:
        for target in written:
            target.unlink(missing_ok=True)
        directory.rmdir()
        raise


def course_filename_stem(title: str) -> str:
    """Preserve the course title in a portable path component."""
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]+', "-", title).strip(" .")
    stem = stem[:90].encode("utf-8")[:160].decode("utf-8", errors="ignore").rstrip(" .")
    if re.fullmatch(r"CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|(?:COM|LPT)[1-9¹²³]", stem.partition(".")[0].rstrip(), re.I):
        stem = f"_{stem}"
    return stem or "课程"


def write_course_files(root: Path, stem: str, documents: dict[str, bytes]) -> Path:
    """Reserve a new course folder and remove this export's files if a write fails."""
    root.mkdir(parents=True, exist_ok=True)
    directory = root / stem
    number = 1
    while True:
        try:
            directory.mkdir()
            break
        except FileExistsError:
            number += 1
            directory = root / f"{stem} ({number})"

    written = []
    try:
        for filename, payload in documents.items():
            target = directory / filename
            with target.open("xb") as handle:
                written.append(target)
                handle.write(payload)
    except OSError:
        for target in written:
            target.unlink(missing_ok=True)
        directory.rmdir()
        raise
    return directory


def save_pdf(output: Path, payload: bytes, *, overwrite: bool = False) -> None:
    """Publish a complete file and preserve an existing output unless requested."""
    from tempfile import NamedTemporaryFile

    if output.suffix.lower() != ".pdf":
        raise PrintError("output must have a .pdf extension")
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = None
    try:
        with NamedTemporaryFile(dir=output.parent, suffix=".tmp", delete=False) as handle:
            staged = Path(handle.name)
            handle.write(payload)
        if overwrite:
            staged.replace(output)
        elif os.name == "nt":
            try:
                staged.rename(output)
            except FileExistsError as exc:
                raise PrintError("the output PDF already exists") from exc
        else:
            try:
                os.link(staged, output)
            except FileExistsError as exc:
                raise PrintError("the output PDF already exists") from exc
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a self-contained, static HTML file to A4 PDF.")
    parser.add_argument("html", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--orientation", choices=("portrait", "landscape"), default="portrait")
    parser.add_argument("--margins-mm", type=float, nargs=4, metavar=("TOP", "RIGHT", "BOTTOM", "LEFT"),
                        default=(16, 16, 16, 16))
    parser.add_argument("--chromium", help="path to an installed Chromium browser")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    output = args.output or args.html.with_suffix(".pdf")
    try:
        if args.html.suffix.lower() not in {".html", ".htm"}:
            raise PrintError("input must be an HTML file")
        if args.html.stat().st_size > MAX_HTML_BYTES:
            raise PrintError("print HTML exceeds 4 MiB")
        settings = PrintSettings(args.orientation, args.margins_mm)
        save_pdf(output, render_pdf(args.html.read_text(encoding="utf-8-sig"), settings,
                                    chromium=args.chromium), overwrite=args.overwrite)
    except (PrintError, OSError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
