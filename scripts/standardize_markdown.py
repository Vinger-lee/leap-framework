"""Normalize repository-owned notes and create resolvable reciprocal wikilinks."""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote
import posixpath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from leap.runtime.notes import obsidian_note, strip_code
import yaml

MARKER = "<!-- LEAP_BACKLINKS -->"


def without_backlinks(text):
    """Remove only the generated block; preserve later author-written text."""
    before,sep,after=text.partition(MARKER)
    if not sep:return text
    lines=after.splitlines()
    while lines and not lines[0].strip():lines.pop(0)
    if lines and lines[0].startswith("## Backlinks / 反向关联"):lines.pop(0)
    while lines and not lines[0].strip():lines.pop(0)
    if lines and lines[0].strip().startswith("[["):lines.pop(0)
    return before.rstrip()+"\n\n"+"\n".join(lines).strip()


def paths():
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    return sorted({ROOT / p for p in names if p.endswith(".md") and (ROOT / p).is_file()})


def key(path):
    return path.relative_to(ROOT).with_suffix("").as_posix()


def topic(path, title):
    domains = {"01-python": "Python recursion call stack base case", "02-math": "linear equations equivalent transformations",
        "03-cs": "OSI seven layers encapsulation protocols", "04-physics": "free fall reference axis units motion",
        "05-logic": "flowchart conditions branches execution trace", "06-statistics": "conditional probability independence Bayes",
        "07-chemistry": "chemical equation balancing atom conservation limiting reagent", "08-electronics": "Ohm law series parallel voltage current power"}
    return next((v for k,v in domains.items() if k in path.as_posix()), "LEAP " + title.replace("`", ""))


def normalize_links(body, path, known):
    def replace(m):
        label, raw = m.group(1), unquote(m.group(2).strip("<>"))
        target, _, anchor = raw.partition("#")
        if target.lower().endswith(".md") and "://" not in target:
            resolved = posixpath.normpath(posixpath.join(path.relative_to(ROOT).parent.as_posix(), target))
            target_key = resolved[:-3]
            if target_key in known:
                return "[[" + target_key + "|" + label.replace("`", "").replace("|", "／") + "]]"
        return m.group(0)
    chunks = re.split(r"(?ms)(^```.*?^```[^\n]*|^~~~.*?^~~~[^\n]*)", body)
    for i in range(0, len(chunks), 2):
        chunks[i] = re.sub(r"(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)", replace, chunks[i])
        def html_link(m):
            raw,label=m.groups()
            normalized=replace(re.match(r"\[([^\]\n]+)\]\(([^)\n]+)\)", f"[{label}]({raw})"))
            return normalized if normalized.startswith("[[") else m.group(0)
        chunks[i] = re.sub(r'<a href="([^"\n]+\.md)">([^<]+)</a>', html_link, chunks[i])
    return "".join(chunks)


def main():
    documents = paths()
    known = {key(p): p for p in documents}
    known["Knowledge_Index"] = ROOT / "Knowledge_Index.md"
    count = 70
    for p in documents:
        if key(p) == "docs/mcp-tools":
            continue
        raw = without_backlinks(p.read_text(encoding="utf-8")).rstrip()
        raw = raw.replace("MCP-59%20tools", f"MCP-{count}%20tools")
        raw = re.sub(r"\b59(?=\s*(?:tools|个工具|أداة|herramientas|outils|のツール|инструмент))", str(count), raw) if "quality-audit" not in p.name else raw
        raw = raw.replace("59개 도구", "70개 도구").replace("pytest -q        # 260 passed", "pytest -q        # inspect the current test result")
        raw = re.sub(r'<img src="https://img.shields.io/badge/tests-260%20passing-22bb33"[^>]+>', '[![Tests](https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/Vinger-lee/leap-framework/actions/workflows/ci.yml)', raw)
        raw = normalize_links(raw, p, known)
        front = re.match(r"\A---\s*\n(.*?)\n---\s*\n", raw, re.S)
        heading = re.search(r"(?m)^#\s+(.+)", raw)
        title = heading.group(1) if heading else key(p)
        if not front:
            raw = obsidian_note(raw, title=title, topic=topic(p,title))
        else:
            meta=yaml.safe_load(front.group(1)) or {}
            meta.setdefault("title", title);meta.setdefault("tags", ["leap", "knowledge"]);meta.setdefault("aliases", [title+" note"])
            raw="---\n"+yaml.safe_dump(meta,allow_unicode=True,sort_keys=False).strip()+"\n---\n\n"+raw[front.end():]
            if not re.search(r"Learning resources|学习资源", raw[:2000], re.I):
                query=topic(p,title)
                raw=raw.replace("\n---\n\n", "\n---\n\n> [!info] 学习资源\n> 核心：`"+query+" definitions beginner`\n> 拓展：`"+query+" examples conditions`\n> 进阶：`"+query+" proof transfer`\n\n",1)
            if not re.search(r">\s*\[!\w+\][+-]", raw):
                raw+="\n\n> [!note]- 复核记录\n> 逐项核对条件、原始输入、推导和回执；使用新输入完成迁移，不能把答案揭示作为掌握证据。\n"
            for target in ("Knowledge_Index", "docs/teaching-delivery"):
                if "[["+target+"]]" not in strip_code(raw):
                    raw+="\n\nRelated: [["+target+"]]\n"
        p.write_text(raw.rstrip()+"\n",encoding="utf-8")
    index = "# LEAP knowledge index\n\nThe Markdown vault is the complete source; interactive pages are its shorter projection.\n\n"
    index+="\n".join(f"- [[{k}]]" for k in sorted(known) if k!="Knowledge_Index")
    (ROOT/"Knowledge_Index.md").write_text(obsidian_note(index,title="LEAP knowledge index",topic="LEAP subject prerequisite graph learning routes",tags=["leap","index"],links=["docs/teaching-delivery","docs/subject-knowledge-map"]),encoding="utf-8")
    documents=paths(); known={key(p):p for p in documents}; inbound={k:set() for k in known}
    for k,p in known.items():
        for target in re.findall(r"\[\[([^\]|#]+)(?:[^\]]*)\]\]", strip_code(p.read_text(encoding="utf-8"))):
            if target in inbound and target!=k: inbound[target].add(k)
    for k,p in known.items():
        if k=="docs/mcp-tools": continue
        raw=without_backlinks(p.read_text(encoding="utf-8")).rstrip()
        back="\n\n"+MARKER+"\n\n## Backlinks / 反向关联\n\n"+" · ".join(f"[[{v}]]" for v in sorted(inbound[k]))+"\n"
        p.write_text(raw+back,encoding="utf-8")
    print(f"Normalized {len(documents)} repository Markdown notes; generated reciprocal index.")


if __name__=="__main__": main()
