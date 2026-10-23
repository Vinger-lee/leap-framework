"""One permanent delivery policy and structural checks for canonical teaching pairs.

These checks reject missing coverage and records, not false subject-matter claims.
Semantic review and independent problem verification remain host responsibilities.
"""
from __future__ import annotations

from functools import lru_cache
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata
from typing import Any
from urllib.parse import urlparse

POLICY_FILE = Path(__file__).resolve().parents[1] / "specs/teaching_delivery_policy.json"


@lru_cache(maxsize=1)
def _policy() -> dict:
    return json.loads(POLICY_FILE.read_text(encoding="utf-8"))


def delivery_policy(*, complete: bool = False) -> dict:
    policy = _policy()
    if complete:
        return json.loads(json.dumps(policy))
    return {
        "policy_id": policy["policy_id"], "version": policy["version"], "mandatory": True,
        "canonical_format": "Obsidian Markdown, more complete than HTML",
        "teaching_point_fields": list(policy["teaching_point_fields"]),
        "resource_rule": "verified relevant video or core/extension/advanced search keywords at document top",
        "layout": dict(policy["layout"]),
        "visual_authoring_profile": policy["visualization"]["authoring_profile"],
        "registration_tool": "save_teaching_package",
        "next_generation": "get_teaching_delivery_policy -> full Markdown -> interactive HTML -> save_teaching_package -> item registration -> browser checks",
        "truth_boundary": policy["verification"]["runtime"],
    }


def teaching_point_template() -> dict:
    """Return the required authoring shape used by every host generation."""
    policy = _policy()
    return {
        "point_id": "stable node or subpoint id",
        "title": "specific skill",
        **policy["depth"],
        "visualization": dict(policy["visualization"]),
    }


class VisibleTeaching(HTMLParser):
    """Collect prose/formulas while excluding executable and decorative code."""
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts: list[str] = []
        self.passages: list[str] = []
        self.ids: set[str] = set()
        self.classes: set[str] = set()
        self.elements: dict[str, list[tuple[str, dict]]] = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
            if not self.hidden and tag not in {"script", "style", "head"}:
                self.elements.setdefault(attributes["id"], []).append((tag, attributes))
        self.classes.update((attributes.get("class") or "").split())
        if tag in {"script", "style", "head"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"}:
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())
            self.passages.append(data.strip())


def html_teaching_text(body: str) -> str:
    parser = VisibleTeaching()
    parser.feed(body)
    return " ".join(parser.parts)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return "".join(c.casefold() for c in text if c.isalnum())


def _validate_visual_contract(contract: Any, parser: VisibleTeaching, md: str, projected: str) -> list[str]:
    """Check explicit visual records, never execute a host model or claim it true."""
    errors: list[str] = []
    rules = _policy()["visualization"]["contract"]
    if not isinstance(contract, dict) or contract.get("profile") != rules["profile"]:
        return ["visual_contract.profile must be anatomy.v1"]
    figures = contract.get("figures")
    if not isinstance(figures, list) or not figures:
        return ["visual_contract.figures needs at least one explained figure"]

    def target(selector: Any, field: str, tags: set[str] | None = None) -> None:
        matches = parser.elements.get(selector[1:], []) if isinstance(selector, str) and re.fullmatch(r"#[A-Za-z_][\w-]*", selector) else []
        if len(matches) != 1:
            errors.append(f"{field} must identify a unique actual #id")
        elif tags and (matches[0][0] not in tags or "hidden" in matches[0][1]
                       or "disabled" in matches[0][1] or matches[0][1].get("type") == "hidden"):
            errors.append(f"{field} needs an enabled visible element of type {', '.join(sorted(tags))}")

    def text_record(value: Any, field: str, *, both: bool = True) -> None:
        normalized = normalize_text(value) if isinstance(value, str) else ""
        if not normalized or normalized not in md or (both and normalized not in projected):
            errors.append(f"{field} must be explained in {'both delivered bodies' if both else 'canonical Markdown'}")

    seen: set[str] = set()
    for i, figure in enumerate(figures):
        field = f"visual_contract.figures[{i}]"
        if not isinstance(figure, dict):
            errors.append(f"{field} must be an object")
            continue
        identifier = figure.get("id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            errors.append(f"{field}.id must be a nonempty unique name")
        else:
            seen.add(identifier)
        if figure.get("role") not in rules["roles"]:
            errors.append(f"{field}.role must describe a supported teaching purpose")
        target(figure.get("selector"), f"{field}.selector", {"svg", "canvas", "figure", "div", "section", "table", "img"})
        target(figure.get("static_frame"), f"{field}.static_frame", {"svg", "img", "table"})
        text_record(figure.get("caption"), f"{field}.caption")
        labels = figure.get("labels")
        if not isinstance(labels, list) or not labels:
            errors.append(f"{field}.labels must explain the parts or quantities")
        else:
            for label in labels:
                text_record(label, f"{field}.labels")
        animated = figure.get("animated", False)
        if not isinstance(animated, bool):
            errors.append(f"{field}.animated must be boolean")
        binding = figure.get("model_binding")
        if animated or "model_binding" in figure:
            if not isinstance(binding, dict):
                errors.append(f"{field}.model_binding must describe the shared source and quantities")
            else:
                text_record(binding.get("source"), f"{field}.model_binding.source", both=False)
                quantities = binding.get("quantities")
                if not isinstance(quantities, list) or not quantities:
                    errors.append(f"{field}.model_binding.quantities must name outputs and units")
                else:
                    for quantity in quantities:
                        if not isinstance(quantity, dict) or any(not isinstance(quantity.get(k), str) or not quantity[k].strip() for k in ("name", "unit")):
                            errors.append(f"{field}.model_binding.quantities needs name and unit")
                            continue
                        target(quantity.get("selector"), f"{field}.model_binding.quantity.selector")
        if animated:
            controls = figure.get("controls")
            if not isinstance(controls, dict):
                controls = {}
            for name in ("play_pause", "reset"):
                target(controls.get(name), f"{field}.controls.{name}", {"button", "input", "select"})
            if not (("step_forward" in controls and "step_back" in controls)
                    or "scrub" in controls or "parameter" in controls):
                errors.append(f"{field}.controls needs reversible steps, scrub or parameter control")
            for name, selector in controls.items():
                if name not in {"play_pause", "reset"}:
                    target(selector, f"{field}.controls.{name}", {"button", "input", "select"})
            states = figure.get("states")
            if not isinstance(states, list) or len(states) < 2:
                errors.append(f"{field}.states needs at least two explained animation states")
            else:
                for state in states:
                    text_record(state, f"{field}.states", both=False)
    return errors


def validate_resources(resources: Any) -> list[str]:
    errors = []
    if not isinstance(resources, dict):
        return ["resources must contain verified videos or three keyword tiers"]
    keywords = resources.get("keywords", {})
    videos = resources.get("videos", [])
    if videos:
        if not isinstance(videos, list):
            return ["resources.videos must be a list"]
        for i, video in enumerate(videos):
            if not isinstance(video, dict):
                errors.append(f"video[{i}] must be a verification record")
                continue
            for field in _policy()["learning_resources"]["video_required_fields"]:
                if not video.get(field):
                    errors.append(f"video[{i}].{field} is required")
            if video.get("accessible") is not True or video.get("content_matches") is not True:
                errors.append(f"video[{i}] accessibility and topical content must have been checked")
            parsed = urlparse(str(video.get("url", "")))
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"video[{i}] needs an actual HTTPS URL")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ].*)?", str(video.get("checked_at", ""))):
                errors.append(f"video[{i}].checked_at must record a date")
    if not videos:
        if not isinstance(keywords, dict):
            return ["resources.keywords must contain core, extension and advanced lists"]
        for tier in ("core", "extension", "advanced"):
            values = keywords.get(tier)
            if not isinstance(values, list) or not values or any(not isinstance(v, str) or len(v.strip()) < 4 for v in values):
                errors.append(f"resources.keywords.{tier} requires precise nonempty search queries")
    return errors


def validate_teaching_package(markdown: str, html: str, manifest: Any) -> dict:
    """Validate complete bodies against manifest; never read arbitrary file paths."""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return {"valid": False, "errors": ["manifest must be an object"]}
    if not isinstance(markdown, str) or not isinstance(html, str):
        return {"valid": False, "errors": ["both full markdown and html bodies are required"]}
    front = re.match(r"\A---\s*\n(.*?)\n---\s*\n", markdown, re.S)
    if not front:
        errors.append("Markdown needs YAML frontmatter")
    else:
        import yaml
        try:
            meta = yaml.safe_load(front.group(1))
            if not isinstance(meta, dict) or any(not meta.get(k) for k in ("title", "tags", "aliases")):
                errors.append("Markdown frontmatter needs title, tags and aliases")
        except yaml.YAMLError:
            errors.append("Markdown frontmatter is invalid YAML")
    if not re.search(r"\[\[[^\]]+\]\]", markdown):
        errors.append("Markdown needs internal [[wikilinks]]")
    if not re.search(r">\s*\[!\w+\][+-]", markdown):
        errors.append("Markdown needs a foldable detail callout")
    if not re.search(r"学习资源|Learning resources|Reference resources", markdown[:2000], re.I):
        errors.append("Markdown needs learning resources before teaching content")
    parser = VisibleTeaching()
    parser.feed(html)
    visible_text = " ".join(parser.parts)
    if not re.search(r"学习资源|Learning resources|Reference resources", visible_text[:1800], re.I):
        errors.append("HTML needs learning resources before teaching content")
    errors.extend(validate_resources(manifest.get("resources")))
    md = normalize_text(markdown)
    projected = normalize_text(visible_text)
    if "visual_contract" in manifest:
        errors.extend(_validate_visual_contract(manifest["visual_contract"], parser, md, projected))
    resources = manifest.get("resources") or {}
    if isinstance(resources, dict):
        for tier, values in (resources.get("keywords") or {}).items():
            if isinstance(values, list):
                for query in values:
                    if isinstance(query, str):
                        normalized_query = normalize_text(query)
                        if normalized_query not in md or normalized_query not in projected:
                            errors.append(f"resources.keywords.{tier} must appear in both delivered bodies")
    points = manifest.get("teaching_points")
    if not isinstance(points, list) or not points:
        errors.append("Every package must declare its teaching_points")
        points = []
    for i, point in enumerate(points):
        if not isinstance(point, dict):
            errors.append(f"teaching_points[{i}] must be an object")
            continue
        for field in _policy()["teaching_point_fields"]:
            value = point.get(field)
            if field == "steps":
                if not isinstance(value, list) or len(value) < 2 or any(not isinstance(v, str) or len(normalize_text(v)) < 12 for v in value):
                    errors.append(f"point[{i}].steps needs at least two explained operations")
                    continue
            elif field == "visualization":
                if not isinstance(value, dict) or (not value.get("type") and not value.get("no_visual_reason")):
                    errors.append(f"point[{i}].visualization needs a strategy or specific nonvisual reason")
                    continue
                if value.get("type") and not value.get("selector"):
                    errors.append(f"point[{i}].visualization needs the HTML control/diagram selector")
                selector = value.get("selector", "")
                if selector and not (selector.startswith("#") and selector[1:] in parser.ids
                                     or selector.startswith(".") and selector[1:] in parser.classes):
                    errors.append(f"point[{i}].visualization selector must identify an actual id or class")
                continue
            elif not isinstance(value, str) or not value.strip():
                errors.append(f"point[{i}].{field} is required")
                continue
            if field not in {"point_id", "title"}:
                for part in value if isinstance(value, list) else [value]:
                    if normalize_text(part) not in md:
                        errors.append(f"point[{i}].{field} is not present in canonical Markdown")
    # A host supplies prose segments from the projection; check the actual HTML
    # independently too, so a manifest containing a title alone cannot pass.
    coverage = manifest.get("html_segments")
    if not isinstance(coverage, list) or not coverage:
        errors.append("html_segments must identify projected teaching prose")
        coverage = []
    for i, segment in enumerate(coverage):
        normalized_segment = normalize_text(segment) if isinstance(segment, str) else ""
        if not normalized_segment:
            errors.append(f"html_segments[{i}] is empty")
        elif normalized_segment not in md or normalized_segment not in projected:
            errors.append(f"html_segments[{i}] must be present in both bodies")
    if len(md) <= len(projected):
        errors.append("Canonical Markdown must contain more teaching content than the entire HTML visible text")
    # Compare every actual HTML text run, not host-selected excerpts or a
    # permissive 95% sampling threshold. This includes folded solutions and SVG
    # labels; script-only dynamic feedback needs a separate host/browser audit.
    passages = [text for p in parser.passages if (text := normalize_text(p))]
    missing = [p for p in passages if p not in md]
    ratio = (len(passages) - len(missing)) / len(passages) if passages else 0.0
    if missing or not passages:
        errors.append(f"Canonical Markdown visible-text coverage is {ratio:.1%}; requires 100%. Missing: {missing[:8]}")
    extra = manifest.get("markdown_extensions")
    if not isinstance(extra, list) or not extra:
        errors.append("markdown_extensions must identify additional explanation beyond HTML")
    else:
        for i, detail in enumerate(extra):
            normalized_detail = normalize_text(detail) if isinstance(detail, str) else ""
            if len(normalized_detail) < 40 or normalized_detail not in md or normalized_detail in projected:
                errors.append(f"markdown_extensions[{i}] needs a real additional explanation in Markdown")
    return {"valid": not errors, "errors": errors, "policy_version": _policy()["version"],
            "markdown_teaching_characters": len(md), "html_teaching_characters": len(projected),
            "content_coverage": ratio, "content_verified_by_runtime": False}
