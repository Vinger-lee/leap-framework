#!/usr/bin/env python3
"""Inject the LEAP host-bridge into a generated teaching page.

Why this exists
---------------
The example pages are *reference implementations*, not products. As generated
they are closed simulations: mastery is a hardcoded local number and nothing
leaves the page. That teaches the wrong thing about LEAP, where

* ``mastery_probability`` / ``evidence_stage`` are computed **server-side**
  (LEAP-Framework-V2 section 10.2-1), and
* every learner action is supposed to become an MCP tool call.

This script adds the missing half of the contract to a page:

**Input** - ``LEAP.hydrate(context)`` accepts the object returned by the
``get_teaching_context`` MCP tool, so the host agent can push real state in.

**Output** - every learner action is translated into a pending MCP call
(``submit_attempt``, ``commit_assessment``, ``record_reflection``) and queued
in ``LEAP.drainOutbox()`` for the host agent to execute.

The page keeps working standalone: without ``hydrate()`` it stays in
``demo`` mode and says so, and its locally derived numbers are flagged
``provisional: true``.

Usage:
    python scripts/apply_leap_bridge.py --check
    python scripts/apply_leap_bridge.py examples/01-python-recursion/leap-01-python-recursion.html
    python scripts/apply_leap_bridge.py --all

The script is idempotent: a file that already has the bridge is skipped.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_MARKER = "LEAP_HOST_BRIDGE"

#: Everything a complete bridge must contain. Checking only for the marker is
#: not enough: a regenerated page can carry the banner while missing a field,
#: which leaves the page broken at runtime with no static symptom.
REQUIRED_BRIDGE_PARTS: tuple[tuple[str, str], ...] = (
    ("banner", BRIDGE_MARKER),
    ("state object", "var bridge = {"),
    ("outbox queue", "outbox: []"),
    ("hydrate()", "function hydrate("),
    ("drainOutbox()", "function drainOutbox("),
    ("peekOutbox()", "function peekOutbox("),
    ("enqueue()", "function enqueue("),
    ("renderBridge()", "renderBridge()"),
)

#: Known-incomplete variants, as ``(missing_marker, anchor, insertion)``.
#: The anchor must appear exactly once.
REPAIR_RULES: tuple[tuple[str, str, str], ...] = (
    (
        "outbox: []",
        "    seq: 0,\n    hooks: [],",
        "    outbox: [],\n    seq: 0,\n    hooks: [],",
    ),
)


# ---------------------------------------------------------------------------
# Patch pieces
# ---------------------------------------------------------------------------

CSS_BLOCK = """  /* ── 宿主桥接条（LEAP_HOST_BRIDGE）──────────────────── */
  .bridge-strip{display:flex;align-items:center;justify-content:space-between;gap:var(--s-4);
    min-height:46px;padding:var(--s-3) var(--s-5);margin-bottom:var(--s-3);
    background:var(--accent-wash);border:1px solid var(--hairline);border-radius:var(--r-lg)}
  .bs-l{display:flex;flex-direction:column;gap:var(--s-1);min-width:0}
  .bs-t{font-size:var(--fs-small);color:var(--ink-2)}
  .bs-btn{flex:0 0 auto;height:32px;padding:0 var(--s-4);border:1px solid var(--rule);
    border-radius:var(--r-md);background:var(--surface);color:var(--accent);
    font:500 12.5px/1 var(--font-sans);cursor:pointer;transition:background var(--t-2) var(--ease-out)}
  .bs-btn:hover{background:var(--accent-wash)}
  .bs-btn:disabled{color:var(--ink-3);background:var(--surface-sunk);cursor:default}
  .bridge-out{margin:0 0 var(--s-3);padding:var(--s-5);background:var(--surface-mute);
    border:1px solid var(--hairline);border-radius:var(--r-lg);
    font:400 var(--fs-mono)/1.6 var(--font-mono);color:var(--ink-2);
    white-space:pre-wrap;word-break:break-all;max-height:320px;overflow:auto}

</style>"""

ZONE_BODY_BLOCK = """    <div class="zone-body">
      <div class="bridge-strip" id="bridgeStrip">
        <div class="bs-l">
          <span class="micro micro--accent" id="bridgeMode">BRIDGE · 演示模式</span>
          <span class="bs-t" id="bridgeSummary">未接入宿主 Agent；学习动作会累积为待执行的 MCP 调用。</span>
        </div>
        <button class="bs-btn" id="bridgeDrain" type="button">取出调用队列 ▾</button>
      </div>
      <pre class="bridge-out" id="bridgeOutbox" hidden></pre>
      <div class="console">"""

BRIDGE_STATE_BLOCK = """  /* ══ LEAP_HOST_BRIDGE · 宿主桥接 ══════════════════════════════════
     本页只负责「呈现 + 采集」，不做任何状态判定：
       · mastery_probability / evidence_stage / hint_dependency 由 LEAP Runtime
         计算（LEAP_Framework_V2 §10.2‑1），本页只显示 hydrate() 注入的值；
       · 学习者的每个动作都会被翻译成一条待执行的 MCP 调用，进入 outbox，
         由宿主 Agent 通过 LEAP.drainOutbox() 取走后真正执行。
     未调用 hydrate() 时保持 demo 模式，本地推算值一律标记 provisional。 */
  var bridge = {
    mode: "demo",
    context: null,
    server: {
      mastery_probability: mastery,
      evidence_stage: "estimated",
      hint_dependency: 0,
      next_review_at: null,
      transfer_required: false
    },
    outbox: [],
    seq: 0,
    hooks: [],
    last_attempt_call_id: null,
    last_raw_answer: ""
  };

  function clamp01(v) { return Math.max(0, Math.min(1, Number(v))); }
  function isHosted() { return bridge.mode === "hosted"; }
  function peekOutbox() { return clone(bridge.outbox); }
  function drainOutbox() { var out = clone(bridge.outbox); bridge.outbox.length = 0; renderAll(); return out; }
  function onOutboxChange(fn) { if (typeof fn === "function") bridge.hooks.push(fn); }

  function enqueue(tool, args, note) {
    var call = {
      call_id: "call_" + (++bridge.seq),
      tool: tool,
      args: args || {},
      status: "pending",
      created_at: nowSec(),
      note: note || ""
    };
    bridge.outbox.push(call);
    for (var i = 0; i < bridge.hooks.length; i++) { try { bridge.hooks[i](call, bridge.outbox.length); } catch (e) {} }
    return call;
  }

  /* 事件 → MCP 调用映射。hint_used / answer_revealed / item_completed 不单独
     产生调用：它们的信息通过后续 attempt 的 hint_level 一并提交。 */
  var EVENT_TO_TOOL = {
    attempt_submitted: "submit_attempt",
    drag_submitted: "submit_attempt",
    code_run: "submit_attempt",
    reflection_recorded: "record_reflection"
  };

  function enqueueForEvent(ev) {
    var tool = EVENT_TO_TOOL[ev.event_type];
    if (!tool) return null;
    var raw = ev.answer == null ? "" : String(ev.answer);

    if (tool === "submit_attempt") {
      bridge.last_raw_answer = raw;
      var call = enqueue("submit_attempt", {
        session_id: state.learner.session_id,
        answer: raw,
        node_id: state.node.node_id,
        item_id: ev.item_id || null,
        hint_level: typeof ev.hint_level === "number" ? ev.hint_level : state.ui_state.hint_level,
        response_time: typeof ev.response_time === "number" ? ev.response_time : null
      }, "提交本次作答；返回的 attempt_id 供 commit_assessment 使用");
      bridge.last_attempt_call_id = call.call_id;
      return call;
    }
    return enqueue("record_reflection", {
      session_id: state.learner.session_id,
      reflection: raw,
      node_id: state.node.node_id
    }, "保存反思");
  }

  /* 宿主注入：直接吃 get_teaching_context 的返回值 */
  function hydrate(ctx) {
    if (!ctx || typeof ctx !== "object") { throw new TypeError("LEAP.hydrate(context) 需要一个对象参数"); }
    bridge.context = clone(ctx);
    bridge.mode = "hosted";

    var sess = ctx.session || {};
    var node = ctx.current_node || ctx.node || {};
    var ks = ctx.knowledge_state || {};

    var learnerId = ctx.learner_id || sess.learner_id;
    var sessionId = ctx.session_id || sess.session_id;
    if (learnerId) state.learner.learner_id = learnerId;
    if (sessionId) state.learner.session_id = sessionId;
    if (node.node_id) state.node.node_id = node.node_id;
    if (node.title) state.node.title = node.title;
    if (node.unit_tag) state.node.unit_tag = node.unit_tag;

    if (typeof ks.mastery_probability === "number") {
      bridge.server.mastery_probability = clamp01(ks.mastery_probability);
      mastery = bridge.server.mastery_probability;
    }
    if (ks.evidence_stage) {
      bridge.server.evidence_stage = ks.evidence_stage;
      state.assessment.evidence_stage = ks.evidence_stage;
    }
    if (typeof ks.hint_dependency === "number") {
      bridge.server.hint_dependency = clamp01(ks.hint_dependency);
      state.ui_state.hint_dependency = bridge.server.hint_dependency;
    }
    if (ks.next_review_at) bridge.server.next_review_at = ks.next_review_at;
    if (typeof ctx.transfer_requirement === "boolean") bridge.server.transfer_required = ctx.transfer_requirement;

    bridge.available_actions = ctx.recommended_actions || [];
    bridge.recommended_strategy = ctx.recommended_strategy || "";
    bridge.due_reviews = ctx.due_reviews || [];

    renderAll();
    return snapshot();
  }

  function toggleOutboxView() {
    var pre = document.getElementById("bridgeOutbox");
    var btn = document.getElementById("bridgeDrain");
    if (!pre) return;
    var opening = pre.hidden;
    pre.hidden = !opening;
    if (btn) btn.textContent = opening ? "收起调用队列 ▴" : "取出调用队列 ▾";
    if (opening) {
      var calls = drainOutbox();
      pre.textContent = calls.length
        ? JSON.stringify(calls, null, 2)
        : "（队列为空：尚无需要提交给 LEAP Runtime 的调用）";
    }
  }

  var drainWired = false;
  function renderBridge() {
    var modeEl = document.getElementById("bridgeMode");
    var sumEl = document.getElementById("bridgeSummary");
    var noteEl = document.getElementById("spineNote");
    var n = bridge.outbox.length;

    if (modeEl) modeEl.textContent = "BRIDGE · " + (isHosted() ? "已接入宿主" : "演示模式");
    if (sumEl) {
      sumEl.textContent = isHosted()
        ? "已注入 Runtime 上下文（" + state.node.node_id + "）；待执行的 MCP 调用 " + n + " 条。"
        : "未接入宿主 Agent；学习动作会累积为待执行的 MCP 调用（当前 " + n + " 条）。";
    }
    if (noteEl) {
      noteEl.innerHTML = isHosted()
        ? "本页状态由 <b>LEAP Runtime</b> 注入（<code>LEAP.hydrate()</code>）；掌握度与证据阶段由服务端 BKT 与 State Guard 计算，本页不自行推算。"
        : "本页掌握度与证据阶段为<b>本地模拟</b>，用于演示界面如何呈现学习状态；真实系统中二者由 LEAP Runtime 的 BKT 估计器与 State Guard 计算（见 LEAP_Framework_V2 §10.2‑1）。";
    }

    var btn = document.getElementById("bridgeDrain");
    if (btn && !drainWired) { drainWired = true; btn.addEventListener("click", toggleOutboxView); }
    if (btn && !n) { btn.disabled = true; } else if (btn) { btn.disabled = false; }
  }
"""


def _patch(text: str, old: str, new: str, label: str, path: Path) -> str:
    if old not in text:
        raise SystemExit(f"[{path.name}] anchor not found for {label}")
    if text.count(old) != 1:
        raise SystemExit(f"[{path.name}] anchor for {label} is not unique ({text.count(old)} hits)")
    return text.replace(old, new, 1)


def _patch_table() -> list[tuple[str, str, str]]:
    """Every (label, before, after) transformation the bridge performs."""
    event_colour_marker = '    item_completed: "#2E7D5B"\n  };\n'

    return [
        (
            "spine note id",
            '<p class="spine-note">',
            '<p class="spine-note" id="spineNote">',
        ),
        (
            "css block",
            "\n</style>",
            "\n" + CSS_BLOCK,
        ),
        (
            "zone body",
            '    <div class="zone-body">\n      <div class="console">',
            ZONE_BODY_BLOCK,
        ),
        (
            "bridge state",
            event_colour_marker,
            event_colour_marker + "\n" + BRIDGE_STATE_BLOCK,
        ),
        (
            "pushEvent",
            "    state.events.push(ev);\n    renderAll();\n    return ev;",
            "    state.events.push(ev);\n    enqueueForEvent(ev);\n    renderAll();\n    return ev;",
        ),
        (
            "commitAssessment",
            "    a.overall_score = aggregate(a);\n"
            "    a.evidence_stage = deriveStage(a);\n"
            "    if (typeof item.transfer === \"number\" && item.transfer >= 0.7) a.evidence_stage = \"transferred\";\n"
            "    state.assessment = a;\n"
            "\n"
            "    mastery = Math.max(0, Math.min(0.98, mastery + (a.correctness - 0.5) * 0.14 - dep * 0.04));\n"
            "    renderAll();\n"
            "    return a;",
            "    a.overall_score = aggregate(a);\n"
            "\n"
            "    if (bridge.mode === \"demo\") {\n"
            "      /* 演示模式：本地粗略推进，仅为让界面动起来。\n"
            "         接入宿主后（hosted）这两项一律以 Runtime 返回值回填（§10.2‑1）。 */\n"
            "      a.evidence_stage = deriveStage(a);\n"
            "      if (typeof item.transfer === \"number\" && item.transfer >= 0.7) a.evidence_stage = \"transferred\";\n"
            "      mastery = Math.max(0, Math.min(0.98, mastery + (a.correctness - 0.5) * 0.14 - dep * 0.04));\n"
            "      bridge.server.mastery_probability = mastery;\n"
            "      bridge.server.evidence_stage = a.evidence_stage;\n"
            "      a.provisional = true;\n"
            "    } else {\n"
            "      a.evidence_stage = bridge.server.evidence_stage;\n"
            "      a.provisional = false;\n"
            "    }\n"
            "    state.assessment = a;\n"
            "    state.ui_state.hint_dependency = a.hint_dependency;\n"
            "\n"
            "    /* 评估证据必须回传 Runtime：raw_answer 不可丢弃（§22.8）。 */\n"
            "    enqueue(\"commit_assessment\", {\n"
            "      attempt_id: bridge.last_attempt_call_id\n"
            "        ? \"{{\" + bridge.last_attempt_call_id + \".attempt_id}}\" : \"{{attempt_id}}\",\n"
            "      raw_answer: bridge.last_raw_answer,\n"
            "      assessor_type: a.assessor_type,\n"
            "      correctness: a.correctness,\n"
            "      conceptual_understanding: a.conceptual_understanding,\n"
            "      reasoning_quality: a.reasoning_quality,\n"
            "      application: a.application,\n"
            "      transfer: a.transfer,\n"
            "      hint_dependency: a.hint_dependency,\n"
            "      confidence: a.confidence\n"
            "    }, \"提交评估证据；attempt_id 由上一条 submit_attempt 的返回值填充，mastery 由 Runtime 计算\");\n"
            "    renderAll();\n"
            "    return a;",
        ),
        (
            "renderAll",
            "    renderOutput(); renderSpine(); renderRail();",
            "    renderOutput(); renderSpine(); renderRail(); renderBridge();",
        ),
        (
            "snapshot",
            "  function snapshot() { return clone(state); }",
            "  function snapshot() {\n"
            "    var out = clone(state);\n"
            "    out.ui_state.mode = bridge.mode;\n"
            "    out.ui_state.hosted = isHosted();\n"
            "    out.ui_state.pending_mcp_calls = bridge.outbox.length;\n"
            "    out.outbox = clone(bridge.outbox);\n"
            "    return out;\n"
            "  }",
        ),
        (
            "return object",
            "  return {\n    getInteractionResult: getInteractionResult,",
            "  return {\n"
            "    /* ── 输入：宿主 Agent 注入 Runtime 上下文 ── */\n"
            "    hydrate: hydrate,\n"
            "    isHosted: isHosted,\n"
            "    /* ── 输出：契约对象 ── */\n"
            "    getInteractionResult: getInteractionResult,\n"
            "    /* ── 输出：待执行的 MCP 调用队列 ── */\n"
            "    peekOutbox: peekOutbox,\n"
            "    drainOutbox: drainOutbox,\n"
            "    onOutboxChange: onOutboxChange,",
        ),
    ]


def apply_bridge(path: Path, *, reverse: bool = False) -> str:
    """Apply (or undo) the bridge. Returns 'patched' / 'reverted' / 'already'."""
    raw = path.read_bytes()
    # Preserve the file's existing line endings. Generated pages use LF; writing
    # through the default text mode on Windows would silently convert them to
    # CRLF and turn a small patch into a whole-file diff.
    newline = "\r\n" if b"\r\n" in raw else "\n"
    # Normalise for matching so the anchors (written with \n) apply to either
    # convention, then let write_text restore the original ending.
    text = raw.decode("utf-8").replace("\r\n", "\n")
    has_bridge = BRIDGE_MARKER in text

    if reverse:
        if not has_bridge:
            return "no-bridge"
    elif has_bridge:
        return "already"

    for label, before, after in _patch_table():
        old, new = (after, before) if reverse else (before, after)
        text = _patch(text, old, new, label, path)

    path.write_text(text, encoding="utf-8", newline=newline)
    return "reverted" if reverse else "patched"


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def bridge_status(path: Path) -> dict:
    """Report which required bridge parts are missing from a file."""
    text = path.read_text(encoding="utf-8")
    missing = [name for name, marker in REQUIRED_BRIDGE_PARTS if marker not in text]
    return {
        "present": not missing,
        "missing": missing,
        "has_banner": BRIDGE_MARKER in text,
    }


def repair_bridge(path: Path) -> str:
    """Re-insert parts a regenerated page dropped.

    Returns ``'repaired'``, ``'ok'`` or ``'unrepairable'``. A page that never
    had the bridge at all should be handled with a normal patch instead.
    """
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")

    if BRIDGE_MARKER not in text:
        return "unrepairable"

    applied = 0
    for marker, anchor, replacement in REPAIR_RULES:
        if marker in text:
            continue
        if text.count(anchor) != 1:
            continue
        text = text.replace(anchor, replacement, 1)
        applied += 1

    if not applied:
        return "ok" if not bridge_status(path)["missing"] else "unrepairable"

    path.write_text(text, encoding="utf-8", newline=newline)
    return "repaired"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="HTML files to patch")
    parser.add_argument("--all", action="store_true", help="patch every example under examples/")
    parser.add_argument("--check", action="store_true",
                        help="report bridge completeness (not just presence)")
    parser.add_argument("--revert", action="store_true", help="remove the bridge again")
    parser.add_argument("--repair", action="store_true",
                        help="re-insert bridge parts a regenerated page dropped")
    args = parser.parse_args(argv)

    paths = [Path(p) for p in args.paths]
    if args.all or args.check or args.repair:
        paths = sorted((REPO_ROOT / "examples").rglob("*.html"))
    if not paths:
        parser.error("provide at least one HTML path, or use --all / --check / --repair")

    exit_code = 0
    for path in paths:
        if not path.exists():
            print(f"  MISSING     {path}")
            exit_code = 1
            continue

        if args.repair:
            status = repair_bridge(path)
            detail = ""
            if status == "unrepairable":
                detail = f"  缺失: {', '.join(bridge_status(path)['missing'])}"
                exit_code = 1
            print(f"  {status:<11} {_display(path)}{detail}")
            continue

        if args.check:
            status = bridge_status(path)
            if status["present"]:
                print(f"  COMPLETE    {_display(path)}")
            else:
                label = "INCOMPLETE" if status["has_banner"] else "LACKS"
                print(f"  {label:<11} {_display(path)}  缺失: {', '.join(status['missing'])}")
                exit_code = 2
            continue

        if args.revert:
            status = apply_bridge(path, reverse=True)
            print(f"  {status:<11} {_display(path)}")
            continue

        status = apply_bridge(path)
        if status == "already":
            problems = bridge_status(path)["missing"]
            if problems:
                print(f"  INCOMPLETE  {_display(path)}  缺失: {', '.join(problems)}"
                      f"  → 用 --repair 修复")
                exit_code = 2
                continue
        print(f"  {status:<11} {_display(path)}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
