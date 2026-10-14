"""Installation self-check: ``python -m leap.doctor`` / ``leap-doctor``.

The runtime needs a Python interpreter, three runtime dependencies, a writable
SQLite location, a readable configuration and a self-consistent message
catalogue. When one of those is wrong the failure usually surfaces much later as
an opaque tool error, so this module checks them up front and reports
individually.

It is read-only with respect to learner data: the schema check runs against a
throwaway database in the system temp directory, and the configured database is
only inspected (size, writability of its directory), never opened for writing.

Exit codes: ``0`` every check passed (warnings allowed), ``1`` at least one
check failed. ``--json`` prints the same report as machine-readable JSON.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable, Mapping, Sequence

from leap import __version__
from leap.config import REPO_ROOT, load_config
from leap.runtime.profiles import available_profiles, resolve_profile
from leap.storage import Database

__all__ = ["run_checks", "render", "main"]

MIN_PYTHON = (3, 11)
RUNTIME_DEPENDENCIES = ("mcp", "fsrs", "yaml")


def _check(name: str, fn: Callable[[], Any]) -> dict:
    """Run one check, converting any exception into a failed row."""
    try:
        status, detail = fn()
    except Exception as exc:  # pragma: no cover - defensive reporting path
        return {"name": name, "status": "fail", "detail": f"{type(exc).__name__}: {exc}"}
    return {"name": name, "status": status, "detail": detail}


def _python() -> tuple[str, str]:
    if sys.version_info < MIN_PYTHON:  # type: ignore[comparison-overlap]
        return "fail", (
            f"Python {sys.version_info.major}.{sys.version_info.minor} is unsupported; "
            f"LEAP needs {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+"
        )
    return "ok", f"Python {sys.version.split()[0]} at {sys.executable}"


def _dependencies() -> tuple[str, str]:
    missing: list[str] = []
    versions: list[str] = []
    for module in RUNTIME_DEPENDENCIES:
        try:
            imported = importlib.import_module(module)
        except ImportError:
            missing.append(module)
            continue
        version = getattr(imported, "__version__", None)
        versions.append(f"{module}{' ' + version if version else ''}")
    if missing:
        return "fail", (
            "missing runtime dependencies: "
            + ", ".join(missing)
            + ' - install with: pip install -e ".[dev]"'
        )
    return "ok", ", ".join(versions)


def _configuration() -> tuple[str, str]:
    cfg = load_config()
    key_count = len(cfg.as_dict())
    return "ok", (
        f"config loaded from {REPO_ROOT / 'config' / 'default.yaml'} "
        f"({key_count} keys) | locale={cfg.get('locale')} | "
        f"database_path={cfg.get('database_path')} | "
        f"tool_profile={cfg.get('tool_profile', 'unset')}"
    )


def _database() -> tuple[str, str]:
    cfg = load_config()
    raw = str(cfg.get("database_path", "data/leap.db"))
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    parent = path.parent
    if not parent.exists():
        return "warn", f"database directory does not exist yet: {parent} (created on first run)"
    if not os.access(parent, os.W_OK):
        return "fail", f"database directory is not writable: {parent}"
    exists = "existing file" if path.exists() else "not created yet"
    return "ok", f"{path} ({exists}) | directory writable"


def _schema() -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="leap-doctor-") as folder:
        db = Database(str(Path(folder) / "doctor.db")).initialize()
        try:
            tables = db.table_names()
        finally:
            db.close()
    return "ok", f"schema creates {len(tables)} tables in an empty database"


def _artifact_root() -> tuple[str, str]:
    cfg = load_config()
    raw = str(cfg.get("artifact_root", "artifacts"))
    root = Path(raw)
    if not root.is_absolute():
        root = REPO_ROOT / root
    probe = root
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not os.access(probe, os.W_OK):
        return "fail", f"artifact root is not writable: {root}"
    return "ok", f"{root} (writable via {probe})"


def _catalogues() -> tuple[str, str]:
    from leap.i18n import MESSAGES, SUPPORTED_LOCALES

    default_keys = set(MESSAGES["zh-CN"])
    mismatched = {
        locale: sorted(default_keys.symmetric_difference(set(MESSAGES.get(locale, {}))))
        for locale in SUPPORTED_LOCALES
        if set(MESSAGES.get(locale, {})) != default_keys
    }
    if mismatched:
        return "fail", f"locale catalogues differ from zh-CN: {mismatched}"
    return "ok", (
        f"{len(SUPPORTED_LOCALES)} catalogues ({', '.join(SUPPORTED_LOCALES)}) "
        f"share {len(default_keys)} keys"
    )


def _tool_profiles() -> tuple[str, str]:
    from leap.server import build_server, registered_tool_names

    full = sorted(registered_tool_names(build_server("full")))
    summary: dict[str, int] = {"full": len(full)}
    for profile in available_profiles():
        if profile == "full":
            continue
        exposed = registered_tool_names(build_server(profile))
        unknown = sorted(set(exposed) - set(full))
        if unknown:
            return "fail", f"profile {profile!r} exposes unregistered tools: {unknown}"
        summary[profile] = len(exposed)
    return "ok", " | ".join(f"{name}: {count} tools" for name, count in summary.items())


CHECKS: tuple[tuple[str, Callable[[], Any]], ...] = (
    ("python", _python),
    ("dependencies", _dependencies),
    ("configuration", _configuration),
    ("database", _database),
    ("schema", _schema),
    ("artifact_root", _artifact_root),
    ("i18n_catalogues", _catalogues),
    ("tool_profiles", _tool_profiles),
)


def run_checks() -> dict:
    """Run every check and return the report as a dictionary."""
    checks = [_check(name, fn) for name, fn in CHECKS]
    failed = [c for c in checks if c["status"] == "fail"]
    return {
        "version": __version__,
        "root": str(REPO_ROOT),
        "ok": not failed,
        "checks": checks,
        "failed": [c["name"] for c in failed],
    }


def render(report: Mapping[str, Any]) -> str:
    """Render the report as plain text (stdout is reserved for MCP otherwise)."""
    marks = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}
    lines = [
        f"LEAP doctor - version {report['version']}",
        f"repository: {report['root']}",
        "",
    ]
    for check in report["checks"]:
        lines.append(f"[{marks.get(check['status'], '????')}] {check['name']}: {check['detail']}")
    lines.append("")
    if report["ok"]:
        lines.append("all required checks passed")
    else:
        lines.append(f"failed checks: {', '.join(report['failed'])}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a LEAP installation.")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument(
        "--profile",
        default=None,
        help=f"verify a specific tool profile ({', '.join(available_profiles())})",
    )
    args = parser.parse_args(argv)

    if args.profile is not None:
        try:
            resolve_profile(args.profile)
        except ValueError as exc:
            print(f"[FAIL] {exc}", file=sys.stderr)
            return 1

    report = run_checks()
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
