"""One permanent delivery policy and structural checks for canonical teaching pairs.

These checks reject missing coverage and records, not false subject-matter claims.
Semantic review and independent problem verification remain host responsibilities.

anatomy.v2 enforcement lives in :func:`validate_teaching_package` and
:meth:`leap.tools.artifact.ArtifactTools.save_teaching_package`: the validator
reports the contract state, and registration decides whether a *new* package may
use a legacy (v1/absent) contract. Runtime still checks records and targets, not
science or browser behaviour.
"""
from __future__ import annotations

from datetime import date
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import unicodedata
from typing import Any
from urllib.parse import urlparse

POLICY_FILE = Path(__file__).resolve().parents[1] / "specs/teaching_delivery_policy.json"

#: Non-rendered subtrees excluded from the "visible teaching text" projection.
HIDDEN_TAGS = frozenset({
    "script", "style", "head", "title", "desc", "defs", "template", "noscript",
    "option", "datalist",
})
#: A figure selector must point at a real figure, not ordinary prose.
FIGURE_SELECTOR_TAGS = frozenset({"svg", "canvas", "figure", "img", "table"})
#: anatomy part tags: SVG geometry and native/ARIA buttons are accepted.
PART_TAGS = frozenset({"g", "path", "circle", "polygon", "rect", "button",
                       "line", "ellipse", "text", "use", "polyline", "image"})
PANEL_TAGS = frozenset({"p", "div", "section", "output", "aside", "dl", "article", "figure"})
CONTROL_TAGS = frozenset({"button", "input", "select"})

MANIFEST_FIELDS = frozenset({
    "resources", "teaching_points", "html_segments", "visual_contract",
    "markdown_extensions", "source_ids", "allow_legacy", "policy_id",
    "policy_version", "host_semantic_audit",
})
CONTRACT_FIELDS = frozenset({"profile", "research", "figures"})
RESEARCH_FIELDS = frozenset({"sources", "limitations"})
RESEARCH_SOURCE_FIELDS = frozenset({
    "id", "evidence_source_id", "source", "locator", "excerpt", "checked_at",
})
FIGURE_FIELDS = frozenset({
    "id", "role", "selector", "caption", "labels", "static_frame", "animated",
    "model_binding", "controls", "states", "parts", "inspection", "source_refs",
})
PART_FIELDS = frozenset({
    "selector", "name", "explanation", "relationship", "representation", "basis",
    "source_refs",
})
INSPECTION_FIELDS = frozenset({"panel", "clear", "help"})
MODEL_FIELDS = frozenset({
    "source", "assumptions", "domain", "limits", "source_refs", "quantities", "checks",
})
QUANTITY_FIELDS = frozenset({"name", "unit", "selector"})
CHECK_FIELDS = frozenset({"kind", "inputs", "expected", "method", "result"})

#: ``_policy`` cache keyed by file mtime so an updated policy is picked up
#: without a process restart (the server reads it per call, not just at import).
_POLICY_CACHE: dict[str, Any] = {"mtime_ns": None, "policy": None}


def _policy() -> dict:
    """Return the delivery policy, reloading it when the file changes on disk."""
    try:
        mtime_ns = POLICY_FILE.stat().st_mtime_ns
    except OSError:
        mtime_ns = None
    if _POLICY_CACHE["policy"] is None or _POLICY_CACHE["mtime_ns"] != mtime_ns:
        _POLICY_CACHE["policy"] = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        _POLICY_CACHE["mtime_ns"] = mtime_ns
    return _POLICY_CACHE["policy"]


def reload_policy() -> dict:
    """Force the next policy read to reload ``teaching_delivery_policy.json``."""
    _POLICY_CACHE["policy"] = None
    _POLICY_CACHE["mtime_ns"] = None
    return _policy()


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
        "visual_grounding": policy["host_guidance"]["visual_grounding"],
        "generation_requirements": policy["host_guidance"]["generation"],
        "registration_tool": "save_teaching_package",
        "next_generation": policy["host_guidance"]["next_generation"],
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
    """Collect prose/formulas that the learner could actually see.

    Hidden subtrees are excluded: executable/decorative tags, ``hidden``,
    ``aria-hidden="true"``, inline ``display:none``/``visibility:hidden`` and the
    non-rendered SVG/HTML metadata tags listed in :data:`HIDDEN_TAGS`. Text that
    only exists because of CSS ``content:`` or a stylesheet class is not visible
    to this parser; the policy assigns those to host browser verification.
    """
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self._hidden_stack: list[str] = []
        self.parts: list[str] = []
        self.passages: list[str] = []
        self.ids: set[str] = set()
        self.classes: set[str] = set()
        self.elements: dict[str, list[tuple[str, dict]]] = {}
        self.hidden_ids: set[str] = set()
        self.teaching_anchors: list[str] = []

    @staticmethod
    def _attr_hides(attributes: dict) -> bool:
        if "hidden" in attributes or attributes.get("aria-hidden") == "true":
            return True
        style = (attributes.get("style") or "").replace(" ", "").lower()
        return "display:none" in style or "visibility:hidden" in style

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        hide = tag in HIDDEN_TAGS or self._attr_hides(attributes)
        if tag == "section" and not self.hidden and not hide and attributes.get("data-teaching-point"):
            self.teaching_anchors.append(attributes["data-teaching-point"])
        if attributes.get("id"):
            identifier = attributes["id"]
            self.ids.add(identifier)
            if self.hidden or hide:
                self.hidden_ids.add(identifier)
            else:
                self.elements.setdefault(identifier, []).append((tag, attributes))
        self.classes.update((attributes.get("class") or "").split())
        if hide:
            self.hidden += 1
            self._hidden_stack.append(tag)

    def handle_endtag(self, tag):
        if self._hidden_stack and self._hidden_stack[-1] == tag:
            self._hidden_stack.pop()
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


def _needed_chars(value: Any, minimum: int) -> int:
    """CJK text conveys more meaning per character, so it needs fewer chars."""
    if not isinstance(value, str):
        return minimum
    if any("\u4e00" <= ch <= "\u9fff" for ch in value):
        return max(2, minimum - 2)
    return minimum


def _meaningful(value: Any, minimum: int) -> bool:
    """Reject empty, one-character and single-symbol placeholders like ``a``."""
    if not isinstance(value, str):
        return False
    normalized = normalize_text(value)
    needed = _needed_chars(value, minimum)
    if len(normalized) < needed:
        return False
    return len(set(normalized)) >= min(3, needed)


def _id_selector_error(selector: Any) -> tuple[str | None, str | None]:
    """Return ``(id, error)``; only a plain unique ``#id`` target is supported."""
    if not isinstance(selector, str) or not selector.strip():
        return None, "must be a nonempty string such as '#part-name'"
    value = selector.strip()
    if not value.startswith("#") or len(value) < 2:
        return None, "must be a single #id target such as '#part-name'"
    identifier = value[1:]
    if any(ch in identifier for ch in " \t\r\n#.,>+~[]()=\"':"):
        return None, ("must be a single #id target (classes, combinators, "
                      "pseudo selectors and quotes are not supported)")
    return identifier, None


def _check_known_fields(value: Any, allowed: frozenset[str], field: str,
                        errors: list[str]) -> None:
    if isinstance(value, dict):
        for key in sorted(set(value) - allowed):
            errors.append(f"{field} has unknown field {key!r}")


def _validate_visual_contract(contract: Any, parser: VisibleTeaching, md: str,
                              projected: str) -> list[str]:
    """Check explicit visual records, never execute a host model or claim it true."""
    errors: list[str] = []
    rules = _policy()["visualization"]["contract"]
    if not isinstance(contract, dict) or contract.get("profile") not in rules["accepted_profiles"]:
        return [f"visual_contract.profile must be one of {', '.join(rules['accepted_profiles'])}"]
    current = contract["profile"] == rules["profile"]
    _check_known_fields(contract, CONTRACT_FIELDS, "visual_contract", errors)
    figures = contract.get("figures")
    if not isinstance(figures, list) or not figures:
        return ["visual_contract.figures needs at least one explained figure"]

    def target(selector: Any, field: str, tags: frozenset[str] | set[str] | None = None) -> None:
        identifier, syntax_error = _id_selector_error(selector)
        if syntax_error:
            errors.append(f"{field} {syntax_error}")
            return
        matches = parser.elements.get(identifier, [])
        if not matches:
            if identifier in parser.ids:
                errors.append(
                    f"{field}: #{identifier} exists but is hidden or disabled; "
                    "an enabled visible target is required")
            else:
                errors.append(f"{field}: no element with id #{identifier} exists in the HTML")
            return
        if len(matches) != 1:
            errors.append(f"{field}: #{identifier} must be unique in the HTML")
            return
        tag, attributes = matches[0]
        if tags and (tag not in tags or "hidden" in attributes
                     or "disabled" in attributes or attributes.get("type") == "hidden"):
            errors.append(f"{field} needs an enabled visible element of type "
                          f"{', '.join(sorted(tags))}")

    def text_record(value: Any, field: str, *, both: bool = True, minimum: int = 1) -> None:
        needed = _needed_chars(value, minimum)
        if not _meaningful(value, minimum):
            errors.append(f"{field} needs meaningful text of at least {needed} characters")
            return
        normalized = normalize_text(value)
        if normalized not in md or (both and normalized not in projected):
            errors.append(f"{field} must be explained in "
                          f"{'both delivered bodies' if both else 'canonical Markdown'}")

    source_ids: set[str] = set()
    referenced_source_ids: set[str] = set()

    def source_refs(value: Any, field: str, *, required: bool = False) -> None:
        if (not isinstance(value, list) or (required and not value)
                or any(not isinstance(ref, str) or ref not in source_ids for ref in value)):
            errors.append(f"{field} must reference recorded research sources")
        else:
            referenced_source_ids.update(value)

    if current or "research" in contract:
        research = contract.get("research")
        if not isinstance(research, dict):
            errors.append("visual_contract.research must record actual source reading and limitations")
        else:
            _check_known_fields(research, RESEARCH_FIELDS, "visual_contract.research", errors)
            text_record(research.get("limitations"), "visual_contract.research.limitations",
                        both=False, minimum=8)
            sources = research.get("sources")
            if not isinstance(sources, list) or not sources:
                errors.append("visual_contract.research.sources needs source records")
            else:
                today = date.today()
                for i, source in enumerate(sources):
                    field = f"visual_contract.research.sources[{i}]"
                    if not isinstance(source, dict):
                        errors.append(f"{field} must be an object")
                        continue
                    _check_known_fields(source, RESEARCH_SOURCE_FIELDS, field, errors)
                    identifier = source.get("id")
                    if not isinstance(identifier, str) or not identifier.strip() or identifier in source_ids:
                        errors.append(f"{field}.id must be a nonempty unique name")
                    else:
                        source_ids.add(identifier)
                    if current and (not isinstance(source.get("evidence_source_id"), str)
                                    or not source["evidence_source_id"].strip()):
                        errors.append(f"{field}.evidence_source_id must name a saved session source")
                    for key in ("source", "locator", "excerpt"):
                        text_record(source.get(key), f"{field}.{key}", both=False)
                    checked_at = source.get("checked_at", "")
                    try:
                        if not isinstance(checked_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", checked_at):
                            raise ValueError("Expected YYYY-MM-DD")
                        checked_date = date.fromisoformat(checked_at)
                    except (TypeError, ValueError):
                        errors.append(f"{field}.checked_at needs an actual ISO calendar date")
                    else:
                        if checked_date > today:
                            errors.append(f"{field}.checked_at must not be in the future")
                    text_record(checked_at, f"{field}.checked_at", both=False)

    seen: set[str] = set()
    for i, figure in enumerate(figures):
        field = f"visual_contract.figures[{i}]"
        if not isinstance(figure, dict):
            errors.append(f"{field} must be an object")
            continue
        _check_known_fields(figure, FIGURE_FIELDS, field, errors)
        identifier = figure.get("id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            errors.append(f"{field}.id must be a nonempty unique name")
        else:
            seen.add(identifier)
        if figure.get("role") not in rules["roles"]:
            errors.append(f"{field}.role must describe a supported teaching purpose")
        target(figure.get("selector"), f"{field}.selector", FIGURE_SELECTOR_TAGS)
        target(figure.get("static_frame"), f"{field}.static_frame", {"svg", "img", "table"})
        text_record(figure.get("caption"), f"{field}.caption", minimum=8)
        if "source_refs" in figure:
            source_refs(figure["source_refs"], f"{field}.source_refs")
        labels = figure.get("labels")
        if not isinstance(labels, list) or not labels:
            errors.append(f"{field}.labels must explain the parts or quantities")
        else:
            for label in labels:
                text_record(label, f"{field}.labels", minimum=2)
        animated = figure.get("animated", False)
        if not isinstance(animated, bool):
            errors.append(f"{field}.animated must be boolean")
            animated = False
        if not animated and "controls" in figure:
            errors.append(f"{field}.controls requires animated=true")
        if not animated and "states" in figure:
            errors.append(f"{field}.states requires animated=true")
        binding = figure.get("model_binding")
        if animated or "model_binding" in figure:
            if not isinstance(binding, dict):
                errors.append(f"{field}.model_binding must describe the shared source and quantities")
            else:
                _check_known_fields(binding, MODEL_FIELDS, f"{field}.model_binding", errors)
                text_record(binding.get("source"), f"{field}.model_binding.source", both=False,
                            minimum=8)
                quantities = binding.get("quantities")
                if not isinstance(quantities, list) or not quantities:
                    errors.append(f"{field}.model_binding.quantities must name outputs and units")
                else:
                    for quantity in quantities:
                        if (not isinstance(quantity, dict)
                                or any(not isinstance(quantity.get(k), str)
                                       or not quantity[k].strip() for k in ("name", "unit"))):
                            errors.append(f"{field}.model_binding.quantities needs name and unit")
                            continue
                        _check_known_fields(quantity, QUANTITY_FIELDS,
                                            f"{field}.model_binding.quantities", errors)
                        target(quantity.get("selector"), f"{field}.model_binding.quantity.selector")
                        for key in ("name", "unit"):
                            normalized = normalize_text(quantity[key])
                            if normalized not in md:
                                errors.append(
                                    f"{field}.model_binding.quantity.{key} must appear in canonical Markdown")
                if current:
                    for key in ("assumptions", "domain", "limits"):
                        text_record(binding.get(key), f"{field}.model_binding.{key}",
                                    both=False, minimum=8)
                    source_refs(binding.get("source_refs"), f"{field}.model_binding.source_refs",
                                required=True)
                if current or "checks" in binding:
                    checks = binding.get("checks")
                    if not isinstance(checks, list) or not checks:
                        errors.append(f"{field}.model_binding.checks needs independent worked checks")
                    else:
                        kinds: set[str] = set()
                        for check in checks:
                            if not isinstance(check, dict):
                                errors.append(f"{field}.model_binding.checks must contain objects")
                                continue
                            _check_known_fields(check, CHECK_FIELDS,
                                                f"{field}.model_binding.checks", errors)
                            if current:
                                kind = check.get("kind")
                                if kind not in ("initial", "intermediate", "terminal", "typical", "boundary"):
                                    errors.append(f"{field}.model_binding.checks.kind needs a supported case kind")
                                else:
                                    kinds.add(kind)
                            for key in ("inputs", "expected", "method", "result"):
                                text_record(check.get(key), f"{field}.model_binding.checks.{key}",
                                            both=False, minimum=8)
                        if current and animated and ("boundary" not in kinds or len(kinds) < 2):
                            errors.append(f"{field}.model_binding.checks needs a boundary and representative case")
        inspectable = current and figure.get("role") in ("structure", "mechanism", "spatial")
        if inspectable or "parts" in figure or "inspection" in figure:
            if not source_ids:
                errors.append(f"{field}.parts needs visual_contract.research source records")
            parts = figure.get("parts")
            inspection = figure.get("inspection")
            if not isinstance(parts, list) or not parts:
                errors.append(f"{field}.parts needs explained, traceable parts")
            else:
                part_selectors: set[str] = set()
                for part in parts:
                    part_field = f"{field}.parts"
                    if not isinstance(part, dict):
                        errors.append(f"{part_field} must contain objects")
                        continue
                    _check_known_fields(part, PART_FIELDS, part_field, errors)
                    selector = part.get("selector")
                    target(selector, f"{part_field}.selector", PART_TAGS)
                    if isinstance(selector, str):
                        if selector in part_selectors:
                            errors.append(f"{part_field}.selector must be unique within the figure")
                        part_selectors.add(selector)
                    text_record(part.get("name"), f"{part_field}.name", minimum=2)
                    text_record(part.get("explanation"), f"{part_field}.explanation", minimum=8)
                    text_record(part.get("basis"), f"{part_field}.basis", both=False, minimum=8)
                    if current:
                        text_record(part.get("relationship"), f"{part_field}.relationship",
                                    both=False, minimum=8)
                    if part.get("representation") not in ("reference", "schematic", "analogy"):
                        errors.append(f"{part_field}.representation needs reference, schematic or analogy")
                    source_refs(part.get("source_refs"), f"{part_field}.source_refs",
                                required=part.get("representation") == "reference")
                    if inspection is not None and isinstance(selector, str):
                        matches = parser.elements.get(selector[1:], [])
                        if len(matches) == 1:
                            tag, attrs = matches[0]
                            if tag != "button" and (attrs.get("role") != "button"
                                                    or attrs.get("tabindex") != "0"
                                                    or not attrs.get("aria-label")):
                                errors.append(f"{part_field}.selector needs a named keyboard-focusable button for inspection")
            if inspectable or "inspection" in figure or current:
                if not isinstance(inspection, dict):
                    errors.append(f"{field}.inspection must describe the explanation panel and clear control")
                else:
                    _check_known_fields(inspection, INSPECTION_FIELDS,
                                        f"{field}.inspection", errors)
                    target(inspection.get("panel"), f"{field}.inspection.panel", PANEL_TAGS)
                    target(inspection.get("clear"), f"{field}.inspection.clear", {"button"})
                    text_record(inspection.get("help"), f"{field}.inspection.help", minimum=8)
        if animated:
            controls = figure.get("controls")
            if not isinstance(controls, dict):
                controls = {}
            for name in ("play_pause", "reset"):
                target(controls.get(name), f"{field}.controls.{name}", CONTROL_TAGS)
            if not (("step_forward" in controls and "step_back" in controls)
                    or "scrub" in controls or "parameter" in controls):
                errors.append(f"{field}.controls needs reversible steps, scrub or parameter control")
            for name, selector in controls.items():
                if name not in {"play_pause", "reset"}:
                    target(selector, f"{field}.controls.{name}", CONTROL_TAGS)
            states = figure.get("states")
            if not isinstance(states, list) or len(states) < 2:
                errors.append(f"{field}.states needs at least two explained animation states")
            else:
                for state in states:
                    text_record(state, f"{field}.states", both=False, minimum=8)
    if current:
        unmapped_sources = sorted(source_ids - referenced_source_ids)
        if unmapped_sources:
            errors.append(
                "visual_contract.research.sources must map to a figure, part or model; "
                f"unreferenced ids: {unmapped_sources}"
            )
    return errors


def validate_visual_source_links(manifest: dict, sources: dict[str, dict], *,
                                 report_source_ids: set[str] | None = None) -> list[str]:
    """Link v2 research to the session records already checked by registration.

    Exact record agreement establishes traceability, never actual reading or truth.
    ``report_source_ids`` (the latest completed benchmark report) binds each
    evidence id to the current grounding pass, not just to any session source.
    Call only after validate_teaching_package accepted the manifest shape.
    """
    contract = manifest.get("visual_contract") or {}
    if not isinstance(contract, dict) or contract.get("profile") != "anatomy.v2":
        return []
    errors: list[str] = []
    research = contract.get("research")
    research_sources = research.get("sources") if isinstance(research, dict) else None
    if not isinstance(research_sources, list):
        return ["visual_contract.research.sources must contain the research records"]
    for index, source in enumerate(research_sources):
        field = f"visual_contract.research.sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{field} must be an object")
            continue
        evidence_source_id = source.get("evidence_source_id")
        if not isinstance(evidence_source_id, str) or not evidence_source_id.strip():
            errors.append(f"{field}.evidence_source_id must name a saved session source")
            continue
        if report_source_ids is not None and evidence_source_id not in report_source_ids:
            errors.append(
                f"{field}.evidence_source_id must belong to the latest completed "
                "benchmark report's source_ids")
            continue
        saved = sources.get(evidence_source_id)
        if saved is None:
            errors.append(f"{field}.evidence_source_id must be included in this package's session source_ids")
            continue
        metadata: Any = {}
        raw_metadata = saved.get("metadata")
        if raw_metadata:
            try:
                metadata = json.loads(raw_metadata)
            except (TypeError, ValueError):
                errors.append(f"{field} has an unreadable session evidence record")
                continue
            if not isinstance(metadata, dict):
                errors.append(f"{field} has an unreadable session evidence record")
                continue
        for key in ("source", "locator", "excerpt"):
            stored_value = saved.get("source") if key == "source" else metadata.get(key)
            if (not isinstance(stored_value, str) or not isinstance(source.get(key), str)
                    or source[key].strip() != stored_value.strip()):
                errors.append(f"{field}.{key} must match its saved session evidence record")
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


def _text_only_points(points: list) -> bool:
    """True when every point declares a concrete reason not to visualise."""
    if not points:
        return False
    for point in points:
        if not isinstance(point, dict):
            return False
        visualization = point.get("visualization")
        if not isinstance(visualization, dict):
            return False
        if visualization.get("type"):
            return False
        if not _meaningful(visualization.get("no_visual_reason"), 8):
            return False
    return True


def validate_teaching_package(markdown: str, html: str, manifest: Any) -> dict:
    """Validate complete bodies against manifest; never read arbitrary file paths."""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return {"valid": False, "errors": ["manifest must be an object"]}
    if not isinstance(markdown, str) or not isinstance(html, str):
        return {"valid": False, "errors": ["both full markdown and html bodies are required"]}
    policy = _policy()
    for key in sorted(set(manifest) - MANIFEST_FIELDS):
        if key.lower().replace("_", "") == "visualcontract":
            errors.append(
                f"manifest has unknown field {key!r}; the field is 'visual_contract' "
                "(lowercase, underscore)")
        else:
            errors.append(f"manifest has unknown field {key!r}")
    allow_legacy = manifest.get("allow_legacy")
    if allow_legacy is not None and not isinstance(allow_legacy, bool):
        errors.append("manifest.allow_legacy must be a boolean")
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
    visual_errors: list[str] = []
    contract = manifest.get("visual_contract")
    has_contract = isinstance(contract, dict)
    contract_malformed = "visual_contract" in manifest and contract is not None and not has_contract
    if contract_malformed:
        errors.append("visual_contract must be an object or null")
    profile = contract.get("profile") if has_contract else None
    current_profile = policy["visualization"]["authoring_profile"]
    if has_contract:
        visual_errors = _validate_visual_contract(contract, parser, md, projected)
        errors.extend(visual_errors)
    points = manifest.get("teaching_points")
    points_list = points if isinstance(points, list) else []
    if parser.teaching_anchors and parser.teaching_anchors != [point.get("point_id") for point in points_list if isinstance(point, dict)]:
        errors.append("HTML data-teaching-point anchors must cover the manifest teaching points in order")
    text_only = _text_only_points(points_list)
    has_visual_points = any(
        isinstance(point, dict) and isinstance(point.get("visualization"), dict)
        and point["visualization"].get("type") for point in points_list)
    if profile == current_profile:
        if manifest.get("policy_id") != policy["policy_id"]:
            errors.append("manifest.policy_id must match the current delivery policy id")
        if manifest.get("policy_version") != policy["version"]:
            errors.append("manifest.policy_version must match the current delivery policy version")
        if has_visual_points:
            figures = contract.get("figures") if has_contract else None
            controllable = any(
                isinstance(figure, dict) and figure.get("animated") is True
                for figure in (figures if isinstance(figures, list) else []))
            if not controllable:
                errors.append(
                    "teaching_points declare visualizations, so the package needs at least "
                    "one controllable figure (animated=true with controls/states or parameter control)")
    elif has_contract:
        if "policy_id" in manifest and manifest.get("policy_id") != policy["policy_id"]:
            errors.append("manifest.policy_id does not match the current delivery policy id")
        if "policy_version" in manifest and manifest.get("policy_version") != policy["version"]:
            errors.append("manifest.policy_version does not match the current delivery policy version")
    resources = manifest.get("resources") or {}
    if isinstance(resources, dict):
        for tier, values in (resources.get("keywords") or {}).items():
            if isinstance(values, list):
                for query in values:
                    if isinstance(query, str):
                        normalized_query = normalize_text(query)
                        if normalized_query not in md or normalized_query not in projected:
                            errors.append(f"resources.keywords.{tier} must appear in both delivered bodies")
    if not points_list:
        errors.append("Every package must declare its teaching_points")
    for i, point in enumerate(points_list):
        if not isinstance(point, dict):
            errors.append(f"teaching_points[{i}] must be an object")
            continue
        for field in policy["teaching_point_fields"]:
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
    # Compare every actual rendered HTML text run, not host-selected excerpts or
    # a permissive 95% sampling threshold. Hidden/decorative subtrees are
    # excluded; CSS-generated text is a host browser check.
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
    if not has_contract:
        if contract_malformed:
            contract_state = "invalid"
        else:
            contract_state = "not_applicable" if text_only else "absent"
    elif visual_errors:
        contract_state = "invalid"
    elif profile == current_profile:
        contract_state = "current"
    elif profile == "anatomy.v1":
        contract_state = "legacy_v1"
    else:
        contract_state = "invalid"
    visual_status = {
        "profile": profile,
        "authoring_profile": current_profile,
        "visual_contract_state": contract_state,
        "visual_contract_valid": contract_state == "current",
        "package_valid": not errors,
        "text_only": text_only,
        "visual_contract_required": not text_only,
        "allow_legacy": allow_legacy is True,
        "browser_behavior_verified_by_runtime": False,
    }
    return {"valid": not errors, "errors": errors, "policy_version": policy["version"],
            "visual_authoring": visual_status,
            "markdown_teaching_characters": len(md), "html_teaching_characters": len(projected),
            "content_coverage": ratio, "content_verified_by_runtime": False}
