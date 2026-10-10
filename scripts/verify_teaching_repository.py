"""Gate repository Obsidian links and complete paired teaching deliveries."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import yaml

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from leap.runtime.delivery import validate_teaching_package
from leap.runtime.notes import strip_code


def verify(root:Path=ROOT):
    names=subprocess.check_output(["git","ls-files","--cached","--others","--exclude-standard","-z"],cwd=root).decode("utf-8").split("\0")
    notes={str(Path(n).with_suffix("")).replace("\\","/"):root/n for n in names if n.endswith(".md") and (root/n).is_file()}
    errors=[];edges={};details=[]
    for key,p in notes.items():
        text=p.read_text(encoding="utf-8");front=re.match(r"\A---\s*\n(.*?)\n---\s*\n",text,re.S)
        if not front:errors.append(f"{key}: missing YAML frontmatter")
        else:
            meta=yaml.safe_load(front.group(1))
            if not isinstance(meta,dict) or any(not meta.get(k) for k in ("title","tags","aliases")):errors.append(f"{key}: title/tags/aliases required")
        if not re.search(r"Learning resources|学习资源",text[:2000],re.I):errors.append(f"{key}: top resources missing")
        if not re.search(r">\s*\[!\w+\][+-]",text):errors.append(f"{key}: foldable callout missing")
        targets=set(re.findall(r"\[\[([^\]|#]+)(?:[^\]]*)\]\]",strip_code(text)))
        if not targets:errors.append(f"{key}: no wikilinks")
        edges[key]=targets
        for target in targets:
            if target not in notes:errors.append(f"{key}: unresolved [[{target}]]")
    for key,targets in edges.items():
        for target in targets:
            if target in edges and key not in edges[target] and key!=target:
                # Generated tool-reference uses the actual reciprocal vault index.
                if target=="docs/mcp-tools" and key in edges.get("Knowledge_Index",set()):continue
                errors.append(f"{key} -> {target}: reciprocal link absent")
    for page in sorted((root/"examples").rglob("*.html")):
        note=page.parent/"knowledge.md";manifest=page.with_suffix(".delivery.json")
        if not note.exists() or not manifest.exists():errors.append(f"{page.name}: canonical note/delivery manifest absent");continue
        result=validate_teaching_package(note.read_text(encoding="utf-8"),page.read_text(encoding="utf-8"),json.loads(manifest.read_text(encoding="utf-8")))
        details.append({"page":page.relative_to(root).as_posix(),**result})
        errors.extend(f"{page.name}: {e}" for e in result["errors"])
    return {"ok":not errors,"markdown_notes":len(notes),"teaching_pairs":len(details),"errors":errors,"pairs":details}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--json");args=parser.parse_args()
    report=verify();print(json.dumps(report,ensure_ascii=False,indent=2))
    if args.json:Path(args.json).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__=="__main__":raise SystemExit(main())
