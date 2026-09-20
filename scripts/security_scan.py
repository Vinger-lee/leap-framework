#!/usr/bin/env python3
"""LEAP Framework - privacy & secret scanner for public release.

Scans the repository for content that must not be pushed to a public remote:
secrets, personal absolute paths, private-use-area characters, AI citation
artifacts, contact details and other personally identifiable information.

Usage:
    python scripts/security_scan.py
    python scripts/security_scan.py --root . --md reports/security-scan.md
    python scripts/security_scan.py --json build/security-scan.json

Exit codes:
    0  no findings
    1  at least one P0/P1 finding (block public release)
    2  only P2 findings (review recommended)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence

# --------------------------------------------------------------------------
# Scan scope
# --------------------------------------------------------------------------

DEFAULT_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    ".idea",
    ".vscode",
    ".workbuddy-ai",
}

DEFAULT_SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp",
    ".pdf", ".zip", ".gz", ".tar", ".7z", ".rar",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".wav", ".mov", ".avi",
    ".so", ".dll", ".dylib", ".exe", ".bin", ".pyc",
    ".db", ".sqlite", ".sqlite3",
}

MAX_FILE_BYTES = 5 * 1024 * 1024  # skip anything larger; binaries are excluded anyway

#: Append this to a line to acknowledge a finding (e.g. scanner test fixtures).
#: The scanner's own tests and synthetic examples need this, otherwise the
#: fixtures would look exactly like real leaked secrets.
ALLOW_MARKER = "security-scan: allow"

#: Place this in the first few lines of a file to exempt the whole file.
ALLOW_FILE_MARKER = "security-scan: allow-file"

#: How many leading lines are inspected for ALLOW_FILE_MARKER.
ALLOW_FILE_HEADER_LINES = 5


# --------------------------------------------------------------------------
# Findings model
# --------------------------------------------------------------------------

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


@dataclass(frozen=True)
class Rule:
    """A single detection rule."""

    rule_id: str
    severity: str
    title: str
    pattern: re.Pattern[str] | None = None
    char_predicate: str | None = None
    hint: str = ""
    #: When the matched text also matches this pattern it is not reported.
    #: Used for addresses that are documented as non-identifying.
    allowlist: re.Pattern[str] | None = None


@dataclass
class Finding:
    rule_id: str
    severity: str
    title: str
    path: str
    line: int | None
    column: int | None
    excerpt: str
    hint: str = ""

    def as_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "title": self.title,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "excerpt": self.excerpt,
            "hint": self.hint,
        }


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------

RULES: list[Rule] = [
    # ---- P0: hard secrets -------------------------------------------------
    Rule(
        "SEC001", "P0", "Private key material",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        hint="Remove the key, rotate it, and load it from an environment variable.",
    ),
    Rule(
        "SEC002", "P0", "Cloud / API access key",
        re.compile(
            r"(?:AKIA|ASIA)[0-9A-Z]{16}"
            r"|gh[pousr]_[A-Za-z0-9]{16,}"
            r"|github_pat_[A-Za-z0-9_]{20,}"
            r"|sk-[A-Za-z0-9]{20,}"
            r"|xox[baprs]-[A-Za-z0-9-]{10,}"
            r"|AIza[0-9A-Za-z_\-]{35}"
        ),
        hint="Revoke the credential immediately; never commit live keys.",
    ),
    Rule(
        "SEC003", "P0", "Assigned secret / password literal",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|client[_-]?secret"
            r"|password|passwd|private[_-]?token)\b\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"
        ),
        hint="Use a placeholder such as <YOUR_API_KEY> in examples and docs.",
    ),
    Rule(
        "PII001", "P0", "Chinese resident ID number",
        re.compile(r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"),
        hint="Never publish national identity numbers.",
    ),

    # ---- P1: personal / environment leakage -------------------------------
    Rule(
        "PII002", "P1", "Personal absolute path (Windows)",
        re.compile(r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\s\"'<>|]+"),
        hint="Replace with a relative path or a placeholder such as <repo-root>.",
    ),
    Rule(
        "PII003", "P1", "Personal absolute path (macOS / Linux)",
        re.compile(r"(?<![A-Za-z]:)/(?:Users|home)/[A-Za-z0-9._-]+/"),
        hint="Replace with a relative path or a placeholder such as <repo-root>.",
    ),
    Rule(
        "PII004", "P1", "Email address",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        hint="Use a role address or remove it before publishing.",
        # Documented non-identifying addresses. GitHub's noreply form is the
        # recommended way to publish commits without exposing a real mailbox,
        # so documentation that recommends it must not be flagged.
        allowlist=re.compile(
            r"(?i)@(?:users\.noreply\.github\.com|noreply\.github\.com"
            r"|example\.com|example\.org|example\.net|localhost)$"
        ),
    ),
    Rule(
        "PII005", "P1", "Chinese mobile phone number",
        re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
        hint="Remove or mask as 138****0000.",
    ),
    Rule(
        "ART001", "P1", "AI citation artifact left in text",
        # This rule's own pattern contains the markers it looks for.
        re.compile(r"(?i)(?:filecite|cite)?turn\d+file\d+|oai_citation|\u3010\d+\u2020[^\u3011]*\u3011"),  # security-scan: allow
        hint="Strip tooling artifacts from generated content.",
    ),
    Rule(
        "ART002", "P1", "Private-use-area character",
        char_predicate="private_use",
        hint="Delete the invisible character; it usually comes from copy-paste of internal notes.",
    ),
    Rule(
        "ART003", "P1", "Bidirectional control character",
        char_predicate="bidi_control",
        hint="Remove bidi controls (Trojan-Source style hidden text).",
    ),

    # ---- P2: review-worthy ------------------------------------------------
    Rule(
        "CFG001", "P2", "Environment file committed",
        pattern=None,
        hint="Commit only .env.example; keep .env out of version control.",
    ),
    Rule(
        "NET001", "P2", "Private network address",
        re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"),
        hint="Confirm this is not an internal host before publishing.",
    ),
    Rule(
        "NET002", "P2", "Public IPv4 address",
        re.compile(r"\b(?!10\.|127\.|0\.|255\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)(?:\d{1,3}\.){3}\d{1,3}\b"),
        hint="Confirm no real host/IP is exposed.",
    ),
]

SENSITIVE_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "credentials", "credentials.json", "secrets.yml", "secrets.yaml",
    ".netrc", ".npmrc", ".pypirc", ".htpasswd",
}

SENSITIVE_SUFFIXES = {".pem", ".key", ".pfx", ".p12", ".jks", ".keystore", ".ppk"}

#: Path fragments that indicate an AI assistant workspace or local agent state.
#: These hold scratch files, memory, caches and session logs belonging to
#: whoever is working on the repo, and must never be published. The rule is
#: path-based, so it still fires when ``.gitignore`` is bypassed or a file is
#: force-added with ``git add -f``.
AI_WORKSPACE_PATTERN = re.compile(
    r"(?:^|/)("
    r"\.workbuddy[^/]*"
    r"|\.claude[^/]*"
    r"|\.cursor[^/]*"
    r"|\.aider[^/]*"
    r"|\.continue[^/]*"
    r"|\.codeium"
    r"|\.copilot"
    r"|\.windsurf"
    r"|\.zed"
    r"|\.specstory"
    r"|\.sourcegraph"
    r"|\.cody"
    r"|\.codegpt"
    r"|\.tabnine"
    r"|\.gemini"
    r"|agent-state"
    r"|ai-cache"
    r")(?:/|$)",
    re.I,
)


# --------------------------------------------------------------------------
# Character-level predicates
# --------------------------------------------------------------------------

def _is_private_use(ch: str) -> bool:
    code = ord(ch)
    return (
        0xE000 <= code <= 0xF8FF          # BMP private use area
        or 0xF0000 <= code <= 0xFFFFD     # Plane 15 private use
        or 0x100000 <= code <= 0x10FFFD   # Plane 16 private use
        or code in (0xFEFF, 0xFFFD)       # BOM / replacement char
    )


def _is_bidi_control(ch: str) -> bool:
    return ch in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200e\u200f"


CHAR_PREDICATES = {
    "private_use": _is_private_use,
    "bidi_control": _is_bidi_control,
}


# --------------------------------------------------------------------------
# Scanner
# --------------------------------------------------------------------------

def iter_files(root: Path, skip_dirs: set[str], skip_suffixes: set[str]) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip_dirs)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.suffix.lower() in skip_suffixes:
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path


def read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None  # binary
    return raw.decode("utf-8", errors="replace")


def _excerpt(line: str, start: int, end: int, width: int = 90) -> str:
    lo = max(0, start - width // 3)
    hi = min(len(line), end + width // 3)
    text = line[lo:hi].replace("\t", " ").strip()
    prefix = "..." if lo > 0 else ""
    suffix = "..." if hi < len(line) else ""
    return f"{prefix}{text}{suffix}"


def scan_file(path: Path, root: Path, rules: Sequence[Rule]) -> list[Finding]:
    text = read_text(path)
    if text is None:
        return []

    rel = path.relative_to(root).as_posix()
    findings: list[Finding] = []

    head = text.splitlines()[:ALLOW_FILE_HEADER_LINES]
    if any(ALLOW_FILE_MARKER in line for line in head):
        return []

    # --- filename heuristics ---
    if path.name in SENSITIVE_FILENAMES or path.suffix.lower() in SENSITIVE_SUFFIXES:
        findings.append(
            Finding(
                rule_id="CFG001",
                severity="P2",
                title="Potentially sensitive file name",
                path=rel,
                line=None,
                column=None,
                excerpt=path.name,
                hint="Confirm the file contains no live credentials.",
            )
        )

    # --- AI workspace paths (defence in depth behind .gitignore) ---
    match = AI_WORKSPACE_PATTERN.search(rel)
    if match:
        findings.append(
            Finding(
                rule_id="AI001",
                severity="P1",
                title="AI assistant workspace must not be published",
                path=rel,
                line=None,
                column=None,
                excerpt=f"matched directory: {match.group(1)}",
                hint=(
                    "Add this directory to .gitignore and untrack it with "
                    "`git rm -r --cached <path>`. It holds local agent state, not project source."
                ),
            )
        )
        # Nothing below is meaningful for a local scratch file.
        return findings

    # --- line-based regex rules ---
    line_rules = [r for r in rules if r.pattern is not None]
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or ALLOW_MARKER in line:
            continue
        for rule in line_rules:
            for match in rule.pattern.finditer(line):  # type: ignore[union-attr]
                if rule.allowlist is not None and rule.allowlist.search(match.group(0)):
                    continue
                findings.append(
                    Finding(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        title=rule.title,
                        path=rel,
                        line=lineno,
                        column=match.start() + 1,
                        excerpt=_excerpt(line, match.start(), match.end()),
                        hint=rule.hint,
                    )
                )

    # --- character-level rules ---
    char_rules = [r for r in rules if r.char_predicate]
    if char_rules:
        for lineno, line in enumerate(text.splitlines(), start=1):
            if ALLOW_MARKER in line:
                continue
            for col, ch in enumerate(line):
                if ch in " \t":
                    continue
                for rule in char_rules:
                    predicate = CHAR_PREDICATES[rule.char_predicate or ""]
                    if predicate(ch):
                        findings.append(
                            Finding(
                                rule_id=rule.rule_id,
                                severity=rule.severity,
                                title=rule.title,
                                path=rel,
                                line=lineno,
                                column=col + 1,
                                excerpt=(
                                    f"U+{ord(ch):04X} "
                                    f"({unicodedata.name(ch, 'UNKNOWN')})"
                                ),
                                hint=rule.hint,
                            )
                        )

    return findings


def dedupe(findings: Iterable[Finding]) -> list[Finding]:
    seen: set[tuple] = set()
    out: list[Finding] = []
    for f in findings:
        key = (f.rule_id, f.path, f.line, f.column, f.excerpt)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    out.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.path, f.line or 0, f.column or 0))
    return out


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def render_markdown(findings: Sequence[Finding], root: Path, scanned: int) -> str:
    counts = {sev: sum(1 for f in findings if f.severity == sev) for sev in ("P0", "P1", "P2")}
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Security & Privacy Scan Report",
        "",
        f"- Scope: `{root.as_posix()}`",
        f"- Files scanned: {scanned}",
        f"- Generated: {stamp}",
        f"- Findings: **P0 {counts['P0']}** / **P1 {counts['P1']}** / **P2 {counts['P2']}**",
        "",
    ]
    if not findings:
        lines += ["No findings. The repository is clear for public release.", ""]
        return "\n".join(lines)

    lines += [
        "| Severity | Rule | File | Line | Detail |",
        "|---|---|---|---|---|",
    ]
    for f in findings:
        detail = f.excerpt.replace("|", "\\|")
        loc = f"{f.path}:{f.line}" if f.line else f.path
        lines.append(f"| {f.severity} | `{f.rule_id}` {f.title} | `{loc}` | {f.line or '-'} | {detail} |")

    lines += ["", "## Remediation hints", ""]
    for rule_id in sorted({f.rule_id for f in findings}):
        rule = next((r for r in RULES if r.rule_id == rule_id), None)
        if rule and rule.hint:
            lines.append(f"- `{rule_id}` - {rule.hint}")
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan a repository for secrets and PII.")
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    parser.add_argument("--md", default=None, help="write a Markdown report to this path")
    parser.add_argument("--json", dest="json_out", default=None, help="write findings as JSON")
    parser.add_argument("--quiet", action="store_true", help="only print the summary line")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 1

    files = list(iter_files(root, DEFAULT_SKIP_DIRS, DEFAULT_SKIP_SUFFIXES))
    findings: list[Finding] = []
    for path in files:
        findings.extend(scan_file(path, root, RULES))
    findings = dedupe(findings)

    counts = {sev: sum(1 for f in findings if f.severity == sev) for sev in ("P0", "P1", "P2")}

    if not args.quiet:
        print(render_markdown(findings, root, len(files)))

    print(
        f"[security_scan] files={len(files)} "
        f"P0={counts['P0']} P1={counts['P1']} P2={counts['P2']}",
        file=sys.stderr,
    )

    if args.md:
        out = Path(args.md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(findings, root, len(files)), encoding="utf-8")
        print(f"[security_scan] wrote {out}", file=sys.stderr)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "root": root.as_posix(),
            "files_scanned": len(files),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "counts": counts,
            "findings": [f.as_dict() for f in findings],
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[security_scan] wrote {out}", file=sys.stderr)

    if counts["P0"] or counts["P1"]:
        return 1
    if counts["P2"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
