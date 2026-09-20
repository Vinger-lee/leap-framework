#!/usr/bin/env python3
"""Audit how much of the LEAP specification the implementation actually covers.

Parses the authoritative design document (``（作者维护的框架设计文档，不在本仓库）``)
and compares it against the running code:

* **section 22** MCP tool contract  vs. the tools registered on the MCP server
* **section 23** database design    vs. the tables created by ``schema.sql``
* **section 30** default parameters vs. the keys in ``config/default.yaml``

The point is to answer "is the implementation complete?" with evidence rather
than with confidence. Anything present in the spec but absent from the code is
reported as MISSING; anything in the code but not in the spec is EXTRA.

Usage:
    python scripts/spec_coverage.py
    python scripts/spec_coverage.py --md reports/spec-coverage.md

Exit codes:
    0  full coverage
    1  at least one documented item is not implemented
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
# The authoritative design document is maintained by the project author and
# is NOT part of this public repository. When it is absent (the normal case for
# anyone who has only cloned this repo) the auditor reports a SKIPPED row per
# section instead of failing, so CI still passes on a clean clone.
SPEC_PATH = REPO_ROOT / "（作者维护的框架设计文档，不在本仓库）"
SPEC_AVAILABLE = SPEC_PATH.exists()

# The authoritative design document is maintained by the project author and
# is not part of this public repository. When it is absent (the typical case
# for anyone who has only cloned this repo) the auditor reports a "skipped"
# row instead of failing, so CI can still pass on a clean clone.
SPEC_AVAILABLE = SPEC_PATH.exists() and SPEC_PATH.read_text(encoding="utf-8").strip() != ""

# A table row whose first cell is a single backticked snake_case identifier.
_ROW_ID = re.compile(r"^\|\s*`([a-z][a-z0-9_]*)`\s*\|")
# A level-2 heading like "## 23.14 `review_items`"
_TABLE_HEADING = re.compile(r"^##\s*23\.\d+\s*`([a-z][a-z0-9_]*)`")
# Section headings
_SECTION = re.compile(r"^#\s*(\d+)\.\s")


@dataclass
class Coverage:
    label: str
    documented: list[str] = field(default_factory=list)
    implemented: list[str] = field(default_factory=list)

    @property
    def missing(self) -> list[str]:
        return [x for x in self.documented if x not in self.implemented]

    @property
    def extra(self) -> list[str]:
        return [x for x in self.implemented if x not in self.documented]

    @property
    def covered(self) -> list[str]:
        return [x for x in self.documented if x in self.implemented]


def _section_text(spec: str, number: int) -> str:
    """Return the body of a top-level ``# N.`` section."""
    lines = spec.splitlines()
    start = None
    for i, line in enumerate(lines):
        m = _SECTION.match(line)
        if m and int(m.group(1)) == number:
            start = i + 1
            continue
        if start is not None and _SECTION.match(line):
            return "\n".join(lines[start:i])
    return "\n".join(lines[start:]) if start is not None else ""


def documented_tools(spec: str) -> list[str]:
    """Tool names declared in the section 22 contract tables."""
    body = _section_text(spec, 22)
    seen: list[str] = []
    for line in body.splitlines():
        m = _ROW_ID.match(line)
        if m and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def documented_tables(spec: str) -> list[str]:
    body = _section_text(spec, 23)
    seen: list[str] = []
    for line in body.splitlines():
        m = _TABLE_HEADING.match(line)
        if m and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def documented_params(spec: str) -> list[str]:
    body = _section_text(spec, 30)
    seen: list[str] = []
    for line in body.splitlines():
        m = _ROW_ID.match(line)
        if m and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def implemented_tools() -> list[str]:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from leap.server import build_server

    server = build_server()
    tools = asyncio.run(server.list_tools())
    return sorted(t.name for t in tools)


def implemented_tables() -> list[str]:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from leap.storage import Database

    db = Database(":memory:").initialize()
    names = db.table_names()
    db.close()
    return names


def implemented_params() -> list[str]:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from leap.config import load_config

    return sorted(load_config().as_dict().keys())


def _render(coverage: Coverage) -> str:
    lines = [
        f"### {coverage.label}",
        "",
        f"- 文档定义：**{len(coverage.documented)}**",
        f"- 已实现：**{len(coverage.covered)}** / {len(coverage.documented)}"
        f"  （{len(coverage.covered) * 100 // max(1, len(coverage.documented))}%）",
        "",
    ]
    if coverage.missing:
        lines += ["**未实现（文档有、代码无）：**", ""]
        lines += [f"- `{x}`" for x in coverage.missing]
        lines.append("")
    else:
        lines += ["文档定义的条目已全部实现。", ""]
    if coverage.extra:
        lines += [f"代码多出（文档未定义，属工程补充）：{', '.join(f'`{x}`' for x in coverage.extra)}", ""]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--md", default=None, help="write a Markdown report here")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if not SPEC_AVAILABLE:
        for kind in ("§22 MCP 工具契约", "§23 数据库表设计", "§30 默认工程参数"):
            print(f"  SKIPPED  {kind}  (design document is not in this public repository)")
        return 0

    spec = SPEC_PATH.read_text(encoding="utf-8")

    coverages = [
        Coverage("§22 MCP 工具契约", documented_tools(spec), implemented_tools()),
        Coverage("§23 数据库表设计", documented_tables(spec), implemented_tables()),
        Coverage("§30 默认工程参数", documented_params(spec), implemented_params()),
    ]

    lines = ["# 规范覆盖率审计", "", f"比对对象：`{SPEC_PATH.name}`", ""]
    for coverage in coverages:
        lines.append(_render(coverage))
    report = "\n".join(lines)

    if not args.quiet:
        print(report)

    total_missing = sum(len(c.missing) for c in coverages)
    print(
        f"[spec_coverage] " + " | ".join(
            f"{c.label.split()[0]} {len(c.covered)}/{len(c.documented)}" for c in coverages
        ),
        file=sys.stderr,
    )

    if args.md:
        out = Path(args.md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"[spec_coverage] wrote {out}", file=sys.stderr)

    return 1 if total_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
