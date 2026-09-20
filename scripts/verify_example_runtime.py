#!/usr/bin/env python3
"""Runtime verification for a LEAP teaching page.

Static analysis (``verify_example.py``) proves the file *contains* the right
things. This script proves the page actually *behaves*: it loads the HTML in a
headless browser, exercises the interactions, and validates the object returned
by ``window.LEAP.getInteractionResult()`` against the authoritative JSON Schema.

Requires the optional ``playwright`` dependency and a Chromium build. Point at
one explicitly with ``--chromium`` when the bundled download is unavailable.

Usage:
    python scripts/verify_example_runtime.py examples/01-python-recursion/leap-01-python-recursion.html
    python scripts/verify_example_runtime.py --all

Exit codes:
    0  all runtime checks pass
    1  at least one failure
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "examples" / "_shared" / "interaction-output.schema.json"

DEFAULT_CHROMIUM_CANDIDATES = [
    Path.home() / "AppData/Local/ms-playwright/chromium-1217/chrome-win64/chrome.exe",
    Path.home() / "AppData/Local/ms-playwright",
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/usr/bin/chromium"),
    Path("/usr/bin/google-chrome"),
]


@dataclass
class RuntimeReport:
    path: Path
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    payload_before: dict | None = None
    payload_after: dict | None = None
    schema_errors: list[str] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, ok, detail))

    @property
    def failures(self) -> list[tuple[str, bool, str]]:
        return [c for c in self.checks if not c[1]]


def _find_chromium(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    for candidate in DEFAULT_CHROMIUM_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    root = Path.home() / "AppData/Local/ms-playwright"
    if root.is_dir():
        hits = sorted(root.glob("chromium*/**/chrome.exe"))
        if hits:
            return str(hits[0])
        hits = sorted(root.glob("chromium*/**/chrome-headless-shell.exe"))
        if hits:
            return str(hits[0])
    return None


def _validate(payload: Any, schema: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed; schema validation skipped"]
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    out = []
    for err in errors[:12]:
        location = "/".join(str(p) for p in err.path) or "<root>"
        out.append(f"{location}: {err.message}")
    return out


def verify(path: Path, chromium: str | None, schema: dict, shots_dir: Path | None = None) -> RuntimeReport:
    from playwright.sync_api import sync_playwright

    report = RuntimeReport(path=path)
    url = path.resolve().as_uri()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium, headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        page.on("console", lambda m: report.console_errors.append(f"{m.type}: {m.text}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: report.console_errors.append(f"pageerror: {e}"))

        page.goto(url, wait_until="load")
        page.wait_for_timeout(400)

        # --- namespace + accessor -----------------------------------------
        has_ns = page.evaluate("typeof window.LEAP === 'object' && window.LEAP !== null")
        report.add("window.LEAP 存在", bool(has_ns))
        has_fn = page.evaluate("typeof window.LEAP?.getInteractionResult === 'function'")
        report.add("getInteractionResult() 可调用", bool(has_fn))

        if not has_fn:
            browser.close()
            return report

        # --- output container ---------------------------------------------
        container = page.evaluate(
            "() => { const el = document.getElementById('leap-interaction-output');"
            " return el ? {tag: el.tagName, len: el.textContent.length} : null; }"
        )
        report.add("输出容器 #leap-interaction-output 存在", container is not None,
                   f"tag={container['tag']}" if container else "未找到")

        # --- initial payload ----------------------------------------------
        payload_before = page.evaluate("() => window.LEAP.getInteractionResult()")
        report.payload_before = payload_before
        report.add("初始返回值是对象",
                   isinstance(payload_before, dict),
                   type(payload_before).__name__)

        if isinstance(payload_before, dict):
            report.add("leap_version == '2.0'", payload_before.get("leap_version") == "2.0",
                       f"实际 {payload_before.get('leap_version')!r}")
            learner = payload_before.get("learner") or {}
            report.add(
                "learner 使用占位符",
                learner.get("learner_id") == "REPLACE_WITH_LEARNER_ID"
                and learner.get("session_id") == "REPLACE_WITH_SESSION_ID",
                f"实际 {learner}",
            )
            events_before = payload_before.get("events")
            report.add("events 是数组", isinstance(events_before, list),
                       f"{len(events_before)} 条" if isinstance(events_before, list) else "")
            report.schema_errors = _validate(payload_before, schema)
            report.add("初始状态符合 JSON Schema", not report.schema_errors,
                       "; ".join(report.schema_errors[:3]))

        # --- exercise interactions ----------------------------------------
        clicked = 0
        for selector in ("[data-hint]", "[data-hint-level]", ".hint-card", ".hint-ladder button",
                         "[aria-label*='提示']", "button"):
            handles = page.query_selector_all(selector)
            for handle in handles[:4]:
                try:
                    if handle.is_visible() and handle.is_enabled():
                        handle.click(timeout=800)
                        clicked += 1
                        page.wait_for_timeout(120)
                except Exception:
                    continue
            if clicked >= 6:
                break
        report.add("可点击的交互元素存在", clicked > 0, f"点击 {clicked} 次")

        # try to submit a free-text answer if the page offers one
        submitted = False
        for sel in ("textarea", "input[type=text]", "input:not([type])"):
            try:
                box = page.query_selector(sel)
                if box and box.is_visible():
                    box.fill("def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)")
                    submitted = True
                    break
            except Exception:
                continue
        if submitted:
            for sel in ("button[type=submit]", "button"):
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click(timeout=800)
                        page.wait_for_timeout(200)
                        break
                except Exception:
                    continue

        page.wait_for_timeout(400)

        payload_after = page.evaluate("() => window.LEAP.getInteractionResult()")
        report.payload_after = payload_after

        if isinstance(payload_after, dict) and isinstance(payload_before, dict):
            events_after = payload_after.get("events") or []
            events_before = payload_before.get("events") or []
            report.add(
                "交互后 events 只增不减（append-only）",
                len(events_after) >= len(events_before),
                f"{len(events_before)} -> {len(events_after)}",
            )
            report.add(
                "交互产生新事件",
                len(events_after) > len(events_before),
                f"新增 {len(events_after) - len(events_before)} 条",
            )
            timestamps = [e.get("created_at") for e in events_after
                          if isinstance(e, dict) and e.get("created_at") is not None]
            report.add(
                "created_at 为 Unix 秒",
                bool(timestamps) and all(isinstance(t, int) and t > 1_600_000_000 for t in timestamps),
                f"样例 {timestamps[-1] if timestamps else 'N/A'}",
            )
            levels = [e.get("hint_level") for e in events_after
                      if isinstance(e, dict) and e.get("hint_level") is not None]
            report.add(
                "hint_level 落在 0..4",
                all(0 <= int(lv) <= 4 for lv in levels) if levels else True,
                f"取值 {sorted(set(levels))}",
            )
            after_errors = _validate(payload_after, schema)
            report.add("交互后仍符合 JSON Schema", not after_errors,
                       "; ".join(after_errors[:3]))

        # --- bridge: host injection + MCP outbox ---------------------------
        has_bridge = page.evaluate("typeof window.LEAP?.hydrate === 'function'")
        report.add("LEAP.hydrate() 可调用（宿主注入入口）", bool(has_bridge))

        if has_bridge:
            # Clear anything the interaction pass queued.
            page.evaluate("() => window.LEAP.drainOutbox()")

            hydrated = page.evaluate(
                """() => window.LEAP.hydrate({
                    session: { session_id: 'ses_verify', learner_id: 'learner-verify' },
                    current_node: { node_id: 'verify.node', title: 'Verify Node', unit_tag: 'verify-unit' },
                    knowledge_state: {
                      mastery_probability: 0.73,
                      evidence_stage: 'demonstrated',
                      hint_dependency: 0.31,
                      next_review_at: 1789900000
                    },
                    transfer_requirement: true,
                    recommended_actions: ['Generate Retrieval Item'],
                    recommended_strategy: 'Retrieval Practice'
                })"""
            )
            ui = hydrated.get("ui_state", {}) if isinstance(hydrated, dict) else {}
            report.add("hydrate 后进入 hosted 模式", ui.get("mode") == "hosted", f"mode={ui.get('mode')!r}")
            report.add("注入的 learner / session 生效",
                       hydrated.get("learner", {}).get("learner_id") == "learner-verify"
                       and hydrated.get("learner", {}).get("session_id") == "ses_verify",
                       str(hydrated.get("learner")))
            report.add("注入的 evidence_stage 生效",
                       hydrated.get("assessment", {}).get("evidence_stage") == "demonstrated",
                       f"实际 {hydrated.get('assessment', {}).get('evidence_stage')!r}")
            report.add("注入的 node 生效",
                       hydrated.get("node", {}).get("node_id") == "verify.node",
                       str(hydrated.get("node")))
            shown = page.inner_text("#masVal") if page.query_selector("#masVal") else None
            report.add("顶栏掌握度显示注入值 0.73", shown == "0.73", f"实际显示 {shown!r}")

            # A learner action must become a pending MCP call.
            page.evaluate(
                """() => window.LEAP.pushEvent('attempt_submitted', {
                    item_id: 'q_verify', answer: 'verify answer',
                    hint_level: 1, response_time: 9.5 })"""
            )
            calls = page.evaluate("() => window.LEAP.drainOutbox()")
            tools = [c.get("tool") for c in calls]
            report.add("作答产生 submit_attempt 调用", "submit_attempt" in tools, f"实际 {tools}")

            submit = next((c for c in calls if c.get("tool") == "submit_attempt"), None)
            if submit:
                args = submit.get("args", {})
                report.add(
                    "submit_attempt 参数取自注入上下文",
                    args.get("session_id") == "ses_verify"
                    and args.get("node_id") == "verify.node"
                    and args.get("answer") == "verify answer"
                    and args.get("hint_level") == 1,
                    str(args),
                )
            report.add("drainOutbox 取走后队列清空",
                       page.evaluate("() => window.LEAP.peekOutbox().length") == 0)

            # commit_assessment must carry the raw answer (section 22.8).
            page.evaluate(
                """() => window.LEAP.commitAssessment({
                    item_id: 'q_verify', correctness: 0.9, conceptual_understanding: 0.8,
                    reasoning_quality: 0.7, application: 0.8 })"""
            )
            calls2 = page.evaluate("() => window.LEAP.drainOutbox()")
            commit = next((c for c in calls2 if c.get("tool") == "commit_assessment"), None)
            report.add("评估产生 commit_assessment 调用", commit is not None,
                       f"实际 {[c.get('tool') for c in calls2]}")
            if commit:
                cargs = commit.get("args", {})
                report.add("commit_assessment 携带非空 raw_answer",
                           bool(str(cargs.get("raw_answer", "")).strip()),
                           f"raw_answer={cargs.get('raw_answer')!r}")
                report.add("commit_assessment 携带 attempt_id 引用",
                           "attempt_id" in cargs and "{{" in str(cargs.get("attempt_id")),
                           f"attempt_id={cargs.get('attempt_id')!r}")
                report.add("commit_assessment 不自行提交 mastery",
                           "mastery_probability" not in cargs)
            after_bridge = page.evaluate("() => window.LEAP.getInteractionResult()")
            report.schema_errors = _validate(after_bridge, schema)
            report.add("桥接后仍符合 JSON Schema", not report.schema_errors,
                       "; ".join(report.schema_errors[:3]))

        # --- console cleanliness ------------------------------------------
        report.add("无 JS 控制台错误", not report.console_errors,
                   "; ".join(report.console_errors[:2]))

        # --- responsive ----------------------------------------------------
        for width in (375, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            page.wait_for_timeout(250)
            overflow = page.evaluate(
                "() => ({doc: document.documentElement.scrollWidth,"
                " win: window.innerWidth})"
            )
            ok = overflow["doc"] <= overflow["win"] + 1
            report.add(f"{width}px 无横向滚动", ok,
                       f"scrollWidth={overflow['doc']} innerWidth={overflow['win']}")
            if shots_dir is not None:
                shots_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shots_dir / f"{path.stem}-{width}.png"), full_page=True)

        # --- reduced motion ------------------------------------------------
        page.emulate_media(reduced_motion="reduce")
        page.wait_for_timeout(150)
        report.add("prefers-reduced-motion 下页面正常渲染",
                   page.evaluate("() => document.body.scrollHeight > 200"))

        browser.close()
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--chromium", default=None, help="path to a Chromium/Chrome binary")
    parser.add_argument("--json", dest="json_out", default=None)
    parser.add_argument("--screenshots", default=None,
                        help="directory to write full-page screenshots into")
    args = parser.parse_args(argv)

    try:
        import playwright  # noqa: F401
    except ImportError:
        print("error: playwright is required. pip install playwright", file=sys.stderr)
        return 1

    chromium = _find_chromium(args.chromium)
    if not chromium:
        print("error: no Chromium binary found; pass --chromium", file=sys.stderr)
        return 1

    paths = [Path(p) for p in args.paths]
    if args.all:
        paths = sorted((REPO_ROOT / "examples").rglob("*.html"))
    if not paths:
        parser.error("provide at least one HTML path, or use --all")

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    failed = False
    results: list[dict] = []
    for path in paths:
        if not path.exists():
            print(f"error: not found: {path}", file=sys.stderr)
            failed = True
            continue
        report = verify(path, chromium, schema,
                        shots_dir=Path(args.screenshots) if args.screenshots else None)
        print(f"\n=== {path.name} ===")
        for name, ok, detail in report.checks:
            mark = "PASS" if ok else "FAIL"
            suffix = f"  <- {detail}" if detail and not ok else (f"  ({detail})" if detail else "")
            print(f"  [{mark}] {name}{suffix}")
        print(f"  -> {len(report.checks) - len(report.failures)}/{len(report.checks)} passed")
        results.append({
            "path": path.as_posix(),
            "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in report.checks],
            "console_errors": report.console_errors,
            "payload_before": report.payload_before,
            "payload_after": report.payload_after,
        })
        if report.failures:
            failed = True

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str),
                       encoding="utf-8")
        print(f"\n[verify_runtime] wrote {out}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
