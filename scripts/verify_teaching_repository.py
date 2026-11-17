"""Gate repository Obsidian links and complete paired teaching deliveries.

Besides the static ``validate_teaching_package`` pass, every shipped example is
run through a **registration simulation**: an in-memory session, a synthetic
``save_benchmark_report``, placeholder replacement and the real
``save_teaching_package``. That catches manifests which look valid but cannot be
registered (for example a stale/placeholder ``source_ids`` list).
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from leap.runtime.delivery import validate_teaching_package
from leap.runtime.notes import strip_code

#: Shipped example manifests carry this placeholder instead of a real session
#: source id; the registration simulation and the docs explain the injection.
SOURCE_PLACEHOLDER = "<source id returned by save_benchmark_report>"

#: Public docs are rendered by GitHub/PyPI with ordinary Markdown links. They
#: keep the frontmatter/resource/callout checks but are exempt from the
#: Obsidian-only wikilink and reciprocal-link rules.
PUBLIC_DOCS = frozenset(
    {"README", "README_CN"} | {f"docs/i18n/README.{suffix}"
                               for suffix in ("ar", "es", "fr", "ja", "ko", "ru")})


def _registration_sources(manifest: dict) -> list[dict]:
    """Synthetic session sources matching a v2 research block (or one generic)."""
    contract = manifest.get("visual_contract")
    research = contract.get("research") if isinstance(contract, dict) else None
    records = research.get("sources") if isinstance(research, dict) else None
    refs: list[dict] = []
    if isinstance(records, list):
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            refs.append({
                "source_id": f"src.example.{index}",
                "source": record.get("source") or "Synthetic example source",
                "source_type": "example_fixture",
                "locator": record.get("locator") or "Synthetic example locator",
                "excerpt": record.get("excerpt")
                          or "Synthetic example excerpt for the registration simulation.",
            })
    if not refs:
        refs = [{
            "source_id": "src.example.0",
            "source": "Synthetic example source for the registration simulation",
            "source_type": "example_fixture",
            "locator": "Synthetic example locator",
            "excerpt": "Synthetic example excerpt for the registration simulation.",
        }]
    return refs


def _replace_placeholders(value, source_ids: list[str]):
    """Replace ``<...>`` manifest placeholders with real session source ids."""
    if isinstance(value, str):
        if value.startswith("<") and value.endswith(">"):
            return source_ids[0]
        return value
    if isinstance(value, list):
        return [_replace_placeholders(item, source_ids) for item in value]
    if isinstance(value, dict):
        return {key: _replace_placeholders(item, source_ids) for key, item in value.items()}
    return value


def simulate_registration(page: Path, markdown: str, html: str, manifest: dict) -> dict:
    """Register one shipped example through the real public tool path."""
    from leap.tools import ToolError, build_service

    service = build_service(":memory:", strict_grounding=False)
    try:
        session = service.create_session(
            "example-registration-verifier", f"registration simulation: {page.stem}")
        session_id = session["session_id"]
        report = service.save_benchmark_report(
            session_id,
            f"Registration simulation for {page.name}: synthetic evidence only.",
            source_refs=_registration_sources(manifest),
            verification={
                "scope": f"Repository registration simulation for {page.name}",
                "claims": [{"claim": "The example manifest is registrable after source injection.",
                            "source_index": 0}],
                "worked_examples": [{
                    "problem": "Register the shipped example",
                    "solution": "Save synthetic grounding evidence and the teaching pair",
                    "check_method": "Run the public MCP tool path in memory",
                    "check_result": "The pair is accepted or a structured error is reported",
                }],
                "limitations": ["Synthetic fixture; not real source reading or subject verification"],
            })
        saved = list(report.get("sources_saved") or [])
        if not saved:
            return {"ok": False, "error": {"code": "registration_simulation",
                                           "message": "save_benchmark_report returned no sources"}}
        package_manifest = _replace_placeholders(copy.deepcopy(manifest), saved)
        source_ids = package_manifest.get("source_ids")
        if (not isinstance(source_ids, list) or not source_ids
                or any(not isinstance(source_id, str) for source_id in source_ids)):
            package_manifest["source_ids"] = list(saved)
        node_id = "example.registration.node"
        service.save_knowledge_nodes(
            session_id, [{"node_id": node_id, "title": page.stem, "unit_tag": "example"}])
        result = service.save_teaching_package(
            session_id, node_id, "example", markdown, html, package_manifest)
        validation = result.get("validation") or {}
        visual = validation.get("visual_authoring") or {}
        return {"ok": True, "package_id": result.get("package_id"),
                "visual_contract_state": visual.get("visual_contract_state"),
                "warnings": result.get("warnings") or []}
    except ToolError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": exc.message,
                                       "details": exc.details}}
    finally:
        service.close()


def verify(root: Path = ROOT):
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root).decode("utf-8").split("\0")
    # Agent workflow files use the Agent Skills format, not the Obsidian teaching
    # note contract. Their frontmatter, references and tools have separate tests.
    notes = {str(Path(n).with_suffix("")).replace("\\", "/"): root / n for n in names
             if n.endswith(".md") and not n.startswith(".agents/skills/") and (root / n).is_file()}
    errors = []
    edges = {}
    details = []
    for key, p in notes.items():
        text = p.read_text(encoding="utf-8")
        public = key in PUBLIC_DOCS or key.startswith("docs/i18n/README.")
        front = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.S)
        if not front:
            errors.append(f"{key}: missing YAML frontmatter")
        else:
            meta = yaml.safe_load(front.group(1))
            if not isinstance(meta, dict) or any(not meta.get(k) for k in ("title", "tags", "aliases")):
                errors.append(f"{key}: title/tags/aliases required")
        if not re.search(r"Learning resources|学习资源", text[:2000], re.I):
            errors.append(f"{key}: top resources missing")
        if not re.search(r">\s*\[!\w+\][+-]", text):
            errors.append(f"{key}: foldable callout missing")
        targets = set(re.findall(r"\[\[([^\]|#]+)(?:[^\]]*)\]\]", strip_code(text)))
        # Public docs (root READMEs and translated i18n READMEs) are rendered by
        # GitHub/PyPI and use standard Markdown links, so they are exempt from the
        # Obsidian wikilink and reciprocal-link rules. Notes may still link to them.
        if not public and not targets:
            errors.append(f"{key}: no wikilinks")
        if not public:
            edges[key] = targets
            for target in targets:
                if target not in notes:
                    errors.append(f"{key}: unresolved [[{target}]]")
    for key, targets in edges.items():
        for target in targets:
            if target in edges and key not in edges[target] and key != target:
                # Generated tool-reference uses the actual reciprocal vault index.
                if target == "docs/mcp-tools" and key in edges.get("Knowledge_Index", set()):
                    continue
                errors.append(f"{key} -> {target}: reciprocal link absent")
    for page in sorted((root / "examples").rglob("*.html")):
        note = page.parent / "knowledge.md"
        manifest_path = page.with_suffix(".delivery.json")
        if not note.exists() or not manifest_path.exists():
            errors.append(f"{page.name}: canonical note/delivery manifest absent")
            continue
        markdown = note.read_text(encoding="utf-8")
        html = page.read_text(encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result = validate_teaching_package(markdown, html, manifest)
        registration = simulate_registration(page, markdown, html, manifest)
        details.append({"page": page.relative_to(root).as_posix(), **result,
                        "registration": registration})
        errors.extend(f"{page.name}: {error}" for error in result["errors"])
        if not registration.get("ok"):
            failure = registration.get("error") or {}
            errors.append(
                f"{page.name}: registration simulation failed: "
                f"{failure.get('code')}: {failure.get('message')} "
                f"{json.dumps(failure.get('details'), ensure_ascii=False)[:400]}")
    return {"ok": not errors, "markdown_notes": len(notes),
            "teaching_pairs": len(details), "errors": errors, "pairs": details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json")
    args = parser.parse_args()
    report = verify()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
