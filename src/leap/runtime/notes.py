"""Canonical Obsidian wrappers for Runtime-generated human-facing notes."""
from __future__ import annotations
import json
import re


def obsidian_note(body: str, *, title: str, topic: str, tags: list[str] | None = None,
                  links: list[str] | None = None) -> str:
    """Preserve the body and add deterministic metadata/resources/reading aids."""
    front = "---\n" + "\n".join([
        "title: " + json.dumps(title, ensure_ascii=False),
        "tags: " + json.dumps(tags or ["leap", "engineering"], ensure_ascii=False),
        "aliases: " + json.dumps([title + " guide"], ensure_ascii=False),
        "canonical_role: full_knowledge_source", "delivery_policy: '3.0'",
    ]) + "\n---\n\n"
    resources = f"> [!info] Learning resources / 学习资源\n> Core: `{topic} foundations definitions workflow`\n> Extension: `{topic} failure cases examples comparison`\n> Advanced: `{topic} invariants verification transfer`\n> These are search queries; no video has been certified for this note.\n\n"
    linked = "Related: " + " · ".join(f"[[{target}]]" for target in (links or ["Knowledge_Index", "docs/teaching-delivery"])) + "\n\n"
    extension = f"\n\n> [!note]- Reading and verification sequence: {topic}\n> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.\n> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.\n> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.\n> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.\n"
    return front + resources + linked + body.strip() + extension + "\n"


def strip_code(text: str) -> str:
    text = re.sub(r"(?ms)^```.*?^```[^\n]*", "", text)
    text = re.sub(r"(?ms)^~~~.*?^~~~[^\n]*", "", text)
    return re.sub(r"`[^`\n]*`", "", text)
