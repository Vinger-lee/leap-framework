#!/usr/bin/env python3
"""Verify a LEAP teaching page against the front-end specifications.

Checks a single-file example HTML against:

* ``examples/_shared/leap-web-spec.md``            - structure and data contract
* ``（作者维护的视觉规范，不在本仓库）``                 - visual rules and anti-patterns
* ``examples/_shared/interaction-output.schema.json`` - the JSON contract

This is deliberately **static analysis**: it reads the file as text. It cannot
prove runtime behaviour, so it is a gate for the mechanical requirements, not a
substitute for opening the page in a browser.

Usage:
    python scripts/verify_example.py examples/01-python-recursion/leap-01-python-recursion.html
    python scripts/verify_example.py --all --md reports/example-verification.md

Exit codes:
    0  all checks pass
    1  at least one ERROR
    2  warnings only
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

PASS, WARN, ERROR = "PASS", "WARN", "ERROR"
_ORDER = {ERROR: 0, WARN: 1, PASS: 2}

#: Emoji and pictographic ranges that must not be used as icons.
#: Arrow glyphs (U+2190-U+21FF) are deliberately excluded: the design spec
#: requires keyboard-shortcut hints such as "← → 单步", which are typography,
#: not emoji.
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000026FF\U00002700-\U000027BF"
    "\U00002B00-\U00002BFF\uFE0F]"
)


@dataclass
class CheckResult:
    check_id: str
    category: str
    title: str
    status: str
    detail: str = ""


@dataclass
class Report:
    path: Path
    results: list[CheckResult] = field(default_factory=list)

    def add(self, check_id: str, category: str, title: str, ok: bool, detail: str = "",
            *, warn_only: bool = False) -> None:
        if ok:
            status = PASS
        else:
            status = WARN if warn_only else ERROR
        self.results.append(CheckResult(check_id, category, title, status, detail))

    @property
    def errors(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == ERROR]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == WARN]

    @property
    def passed(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == PASS]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_comments(html: str) -> str:
    """Remove HTML comments and JS/CSS comments so checks ignore prose."""
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(r"/\*.*?\*/", " ", html, flags=re.S)
    html = re.sub(r"(?m)^\s*//.*$", " ", html)
    return html


def _has(text: str, *needles: str) -> bool:
    return all(n in text for n in needles)


def _css_vars(html: str) -> dict[str, str]:
    """Collect custom-property declarations, keeping the FIRST occurrence.

    Responsive overrides (``@media (max-width:600px){ :root{ --fs-display:23px } }``)
    legitimately redeclare tokens further down the file. The root declaration is
    the one the spec pins, so the first occurrence wins.
    """
    found: dict[str, str] = {}
    for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;{}]+);", html, flags=re.I):
        found.setdefault(m.group(1), m.group(2).strip())
    return found


def _require_tokens(html: str, tokens: dict[str, str]) -> list[str]:
    """Return the token names whose declared value does not match the spec."""
    found = _css_vars(html)
    missing: list[str] = []
    for name, expected in tokens.items():
        actual = found.get(name)
        if actual is None:
            missing.append(f"{name} (missing)")
        elif expected.lower() not in actual.lower():
            missing.append(f"{name} = {actual!r}, expected {expected!r}")
    return missing


#: Design tokens that must appear verbatim (LEAP 视觉设计理念 §4).
REQUIRED_TOKENS: dict[str, str] = {
    "--paper": "#FAF9F6",
    "--surface-sunk": "#F3F1EC",
    "--ink": "#191B20",
    "--hairline": "#E8E4DC",
    "--accent": "#2B4AC4",
    "--ok": "#2E7D5B",
    "--warn": "#B3861A",
    "--err": "#B4432F",
}

#: Evidence-stage colours, in ascending perceptual strength (§4.1).
EVIDENCE_TOKENS: dict[str, str] = {
    "--ev-estimated": "#9AA1AD",
    "--ev-practiced": "#4C7BD9",
    "--ev-demonstrated": "#2E8B84",
    "--ev-retained": "#4C8B3F",
    "--ev-transferred": "#B3861A",
}

#: Hint-ladder colours (§4.1).
HINT_TOKENS: dict[str, str] = {
    "--hint-1": "#E4C77C",
    "--hint-2": "#D4A43C",
    "--hint-3": "#B3861A",
    "--hint-4": "#7A7F8A",
}

#: The four font-size tiers plus the auxiliary ones (§4.2).
FONT_TOKENS: dict[str, str] = {
    "--fs-display": "32px",
    "--fs-h2": "22px",
    "--fs-h3": "17px",
    "--fs-body": "15.5px",
    "--fs-small": "13px",
    "--fs-micro": "11.5px",
    "--fs-mono": "12px",
}

#: Spacing scale must stay on the 4pt grid (§4.3).
SPACING_TOKENS: dict[str, str] = {
    "--s-1": "4px", "--s-2": "8px", "--s-3": "12px", "--s-4": "16px",
    "--s-5": "20px", "--s-6": "24px", "--s-8": "32px", "--s-10": "40px",
    "--s-12": "48px", "--s-16": "64px", "--s-20": "80px",
}

#: Required components per subject (leap-web-spec.md subject table).
SUBJECT_COMPONENTS: dict[str, list[tuple[str, tuple[str, ...]]]] = {
    "programming": [
        ("调用栈动画", ("call stack", "callstack", "调用栈")),
        ("代码运行器", ("run", "运行")),
        ("三级提示", ("hint", "提示")),
        ("拖拽连线", ("drag", "拖拽")),
        ("代码填空", ("blank", "填空")),
    ],
    "math": [
        ("MathML 公式", ("<math",)),
        ("参数计算器", ("calc", "计算")),
        ("拖拽排序", ("drag", "拖拽")),
        ("分步求解", ("step", "步骤")),
        ("数轴", ("number line", "数轴", "axis")),
    ],
    "computer-science": [
        ("七层 SVG 示意", ("svg",)),
        ("拖拽连线", ("drag", "拖拽")),
        ("封装动画", ("encapsulat", "封装")),
        ("选择题", ("choice", "选项")),
    ],
    "physics": [
        ("MathML 公式", ("<math",)),
        ("Canvas 模拟", ("<canvas",)),
        ("参数滑块", ('type="range"', "slider")),
        ("计算填空", ("blank", "填空")),
        ("h-t 曲线", ("chart", "曲线", "graph")),
    ],
    "logic": [
        ("可拖拽节点流程图", ("drag", "拖拽")),
        ("补全题", ("blank", "补全")),
        ("执行动画", ("anim", "动画")),
        ("三级提示", ("hint", "提示")),
        ("结果输出", ("output", "输出")),
    ],
}


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_single_file(report: Report, html: str, raw: str) -> None:
    cat = "A · 单文件零依赖"

    external = re.findall(
        r'(?:src|href)\s*=\s*["\'](https?:)?//[^"\']+', html, flags=re.I
    )
    report.add("A1", cat, "无外部资源引用 (src/href 指向 http)", not external,
               f"发现 {len(external)} 处: {external[:3]}" if external else "")

    script_src = re.findall(r"<script[^>]+src\s*=", html, flags=re.I)
    report.add("A2", cat, "无外部脚本 (<script src>)", not script_src,
               f"发现 {len(script_src)} 处" if script_src else "")

    link_css = re.findall(r'<link[^>]+rel\s*=\s*["\']?stylesheet', html, flags=re.I)
    report.add("A3", cat, "无外部样式表 (<link rel=stylesheet>)", not link_css,
               f"发现 {len(link_css)} 处" if link_css else "")

    # Match only host-like CDN references, so prose such as "零 CDN" is not a hit.
    cdn = re.findall(
        r"(?://|\.)(?:cdn|cdnjs|jsdelivr|unpkg|bootstrapcdn|googleapis|fonts)\.[a-z0-9.-]+",
        html, flags=re.I,
    )
    report.add("A4", cat, "无 CDN 引用", not cdn,
               f"命中: {sorted(set(c.lower() for c in cdn))[:4]}" if cdn else "")

    network = re.findall(r"\b(?:fetch\s*\(|XMLHttpRequest|WebSocket\s*\(|navigator\.sendBeacon)", html)
    report.add("A5", cat, "无运行时网络请求", not network,
               f"命中: {sorted(set(network))[:3]}" if network else "")

    report.add("A6", cat, "无 @import 外部字体/样式",
               not re.search(r"@import\s+url\s*\(", html, flags=re.I))


def check_three_zones(report: Report, html: str) -> None:
    cat = "B · 三段式结构"

    report.add("B1", cat, "存在 Agent 数据输出区 id=\"leap-interaction-output\"",
               'id="leap-interaction-output"' in html or "id='leap-interaction-output'" in html)

    report.add("B2", cat, "存在 window.LEAP 命名空间",
               re.search(r"window\.LEAP\s*=", html) is not None)

    report.add("B3", cat, "暴露 getInteractionResult()",
               "getInteractionResult" in html)

    pushes = len(re.findall(r"events\s*\.\s*push\s*\(", html))
    reassign = re.findall(r"(?<![\w.])events\s*=\s*\[", html)
    report.add("B4", cat, "events 只追加不覆盖",
               pushes > 0 and not reassign,
               f"push {pushes} 次, 重新赋值 {len(reassign)} 次")

    zones = {
        "Teaching 区": ("TEACHING", "教学内容"),
        "Practice 区": ("PRACTICE", "交互练习"),
        "Agent Output 区": ("AGENT OUTPUT", "AGENT"),
    }
    missing = [name for name, needles in zones.items()
               if not any(n in html for n in needles)]
    report.add("B5", cat, "三段 Zone 标识齐备", not missing,
               f"缺少: {missing}" if missing else "")

    report.add("B6", cat, "教学内容区含「理解检查」",
               _has(html, "CHECKPOINT") or "理解检查" in html)


def check_progressive_disclosure(report: Report, html: str) -> None:
    cat = "C · 渐进式答案披露"

    for level, label in ((1, "第 1 级 引导问题"), (2, "第 2 级 策略提示"),
                         (3, "第 3 级 部分示范"), (4, "第 4 级 完整答案")):
        report.add(f"C{level}", cat, f"{label}存在",
                   re.search(rf"hint[-_]?level\s*[=:]\s*{level}|hint_level['\"]?\s*:\s*{level}|HINT_LEVEL\s*=\s*{level}",
                             html) is not None
                   or f"L{level}" in html or f"hint-{level}" in html
                   or re.search(rf"--hint-{level}", html) is not None,
                   warn_only=True)

    report.add("C5", cat, "记录 hint_level 字段",
               re.search(r"hint_level", html) is not None)

    report.add("C6", cat, "完整答案需二次确认",
               any(n in html for n in ("confirm", "二次确认", "确认展开", "确定展开")),
               warn_only=True)

    report.add("C7", cat, "完整答案后强制后置验证",
               any(n in html for n in ("变式", "自我解释", "后置验证", "verification", "follow")),
               warn_only=True)

    # 提示不得由答错自动弹出（M4 自主性）
    auto = re.findall(r"(?:onerror|wrong|incorrect)[^{;]{0,80}(?:showHint|revealHint|openHint)", html, flags=re.I)
    report.add("C8", cat, "提示不自动弹出（须主动点击）", not auto,
               f"疑似自动触发 {len(auto)} 处" if auto else "", warn_only=True)


def check_feedback_and_scoring(report: Report, html: str) -> None:
    cat = "D · 多维反馈与评分"

    for err in ("answer_error", "reasoning_error", "misconception"):
        report.add(f"D-{err}", cat, f"区分错误类型 {err}", err in html)

    dims = ("correctness", "conceptual_understanding", "reasoning_quality",
            "application", "transfer", "hint_dependency", "confidence", "overall_score")
    missing = [d for d in dims if d not in html]
    report.add("D2", cat, "输出全部 8 个多维评分字段", not missing,
               f"缺少: {missing}" if missing else "")

    report.add("D3", cat, "overall_score 权重 0.4/0.3/0.2/0.1",
               _has(html, "0.4", "0.3", "0.2", "0.1"))

    report.add("D4", cat, "三段式反馈（肯定→定位→行动）",
               sum(1 for n in ("你做对", "卡在", "下一步") if n in html) >= 3,
               warn_only=True)

    report.add("D5", cat, "支持部分正确（非二元判定）",
               any(n in html for n in ("部分正确", "partial", "0.5", "0.7")), warn_only=True)


def check_contract(report: Report, html: str) -> None:
    cat = "E · Agent 数据契约"

    top = ("leap_version", "example_id", "subject", "node", "learner",
           "events", "assessment", "ui_state")
    missing = [k for k in top if k not in html]
    report.add("E1", cat, "顶层字段齐备 (8 个)", not missing,
               f"缺少: {missing}" if missing else "")

    report.add("E2", cat, "leap_version = \"2.0\"",
               re.search(r'leap_version["\']?\s*[:=]\s*["\']2\.0["\']', html) is not None)

    report.add("E3", cat, "learner_id / session_id 使用占位符",
               _has(html, "REPLACE_WITH_LEARNER_ID", "REPLACE_WITH_SESSION_ID"))

    report.add("E4", cat, "created_at 使用 Unix 秒",
               re.search(r"Date\.now\(\)\s*/\s*1000|Math\.floor\(\s*Date\.now", html) is not None)

    report.add("E5", cat, "node 含 node_id / title / unit_tag",
               _has(html, "node_id", "title", "unit_tag"))

    report.add("E6", cat, "assessment 含 item_id / error_type / overall_score",
               _has(html, "item_id", "error_type", "overall_score"))

    subject = re.search(r'subject["\']?\s*[:=]\s*["\']([a-z-]+)["\']', html)
    report.add("E7", cat, "subject 取值合法",
               subject is not None and subject.group(1) in
               {"programming", "math", "computer-science", "physics", "logic"},
               f"实际: {subject.group(1)!r}" if subject else "未找到 subject")


def check_visual(report: Report, html: str) -> None:
    cat = "F · 视觉规范"

    missing = _require_tokens(html, REQUIRED_TOKENS)
    report.add("F1", cat, "核心设计令牌齐备且取值正确", not missing,
               "; ".join(missing) if missing else "")

    ev_missing = _require_tokens(html, EVIDENCE_TOKENS)
    report.add("F2", cat, "证据阶段五色令牌齐备", not ev_missing,
               "; ".join(ev_missing) if ev_missing else "", warn_only=True)

    hint_missing = _require_tokens(html, HINT_TOKENS)
    report.add("F3", cat, "提示阶梯四色令牌齐备", not hint_missing,
               "; ".join(hint_missing) if hint_missing else "", warn_only=True)

    font_missing = _require_tokens(html, FONT_TOKENS)
    report.add("F4", cat, "四档字阶 + 辅助档齐备", not font_missing,
               "; ".join(font_missing) if font_missing else "", warn_only=True)

    spacing_missing = _require_tokens(html, SPACING_TOKENS)
    report.add("F5", cat, "4pt 间距栅格齐备", not spacing_missing,
               "; ".join(spacing_missing) if spacing_missing else "", warn_only=True)

    # -- anti-patterns (设计理念 §7) ------------------------------------
    bad = []
    if re.search(r"transition\s*:\s*all", html, flags=re.I):
        bad.append("transition: all")
    if re.search(r"(?:linear|radial|conic)-gradient", html, flags=re.I):
        bad.append("渐变")
    if re.search(r"backdrop-filter", html, flags=re.I):
        bad.append("玻璃拟态")
    if re.search(r"<img\b", html, flags=re.I):
        bad.append("<img> 外部/位图图片")
    report.add("F6", cat, "无反模式（transition:all / 渐变 / 玻璃拟态 / <img>）", not bad,
               f"命中: {bad}" if bad else "")

    emoji = sorted({m.group(0) for m in _EMOJI.finditer(_strip_comments(html))})
    report.add("F7", cat, "无 emoji 图标", not emoji,
               f"命中 {len(emoji)} 种: {emoji[:6]}" if emoji else "")

    has_svg = bool(re.search(r"<svg\b", html, flags=re.I))
    has_canvas = bool(re.search(r"<canvas\b", html, flags=re.I))
    # The spec's binding intent is "no external images"; it names SVG/Canvas as
    # the way to achieve that. Pure-DOM drawing satisfies the intent but not the
    # letter, so it is reported as a deviation rather than a failure.
    report.add("F8", cat, "图形使用内联 SVG 或 Canvas",
               has_svg or has_canvas,
               "未发现 <svg> 或 <canvas>；若采用纯 DOM 绘制，属对规范字面的偏离"
               if not (has_svg or has_canvas) else "",
               warn_only=True)

    report.add("F9", cat, "标题使用衬线字体栈",
               bool(re.search(r"--font-display", html)) and "serif" in html)

    report.add("F10", cat, "中文正文行高 ≥ 1.7",
               bool(re.search(r"1\.7[0-9]", html)))

    report.add("F11", cat, "声明 prefers-reduced-motion",
               "prefers-reduced-motion" in html)

    report.add("F12", cat, "关键交互元素带 aria-label",
               html.count("aria-label") >= 3,
               f"aria-label 出现 {html.count('aria-label')} 次", warn_only=True)

    report.add("F13", cat, "输出区不是黑底裸 <pre>",
               not re.search(r"<pre[^>]*(?:background\s*:\s*#(?:000|111|1e1e1e|222))", html, flags=re.I))

    report.add("F14", cat, "无外部图片/字体文件引用",
               not re.search(r'url\(\s*["\']?(?!data:)[^)"\']+\.(?:png|jpe?g|gif|woff2?|ttf)', html, flags=re.I))

    report.add("F15", cat, "存在证据轨 (Evidence Rail)",
               any(n in html for n in ("EVIDENCE TRAIL", "证据轨", "evidence-rail", "evidenceRail")),
               warn_only=True)

    report.add("F16", cat, "存在进度脊柱 (Progress Spine)",
               any(n in html for n in ("EVIDENCE STAGE", "证据阶段", "progress-spine", "progressSpine")),
               warn_only=True)

    report.add("F17", cat, "提示阶梯为递增高度形态（非三按钮）",
               bool(re.search(r"--hint-\d", html)) and
               bool(re.search(r"(?:ladder|阶梯|hintLadder|hint-ladder)", html, flags=re.I)),
               warn_only=True)


def check_host_bridge(report: Report, html: str) -> None:
    """Host bridge: the page must be able to receive state and emit MCP calls.

    See ``examples/_shared/leap-bridge.md``. A page without this is a closed
    simulation, which is exactly what the examples must not be.
    """
    cat = "H · 宿主桥接"

    report.add("H1", cat, "暴露 LEAP.hydrate() 注入入口",
               bool(re.search(r"hydrate\s*:\s*hydrate|hydrate\s*=\s*function|function\s+hydrate\s*\(", html)))

    report.add("H2", cat, "暴露 LEAP.drainOutbox() 调用出队",
               bool(re.search(r"drainOutbox\s*:\s*drainOutbox|function\s+drainOutbox\s*\(", html)))

    report.add("H3", cat, "暴露 LEAP.peekOutbox() 只读查看",
               bool(re.search(r"peekOutbox\s*:\s*peekOutbox|function\s+peekOutbox\s*\(", html)),
               warn_only=True)

    report.add("H4", cat, "区分 demo / hosted 两种模式",
               bool(re.search(r'mode\s*:\s*["\']demo["\']', html))
               and bool(re.search(r'["\']hosted["\']', html)))

    report.add("H5", cat, "产生 submit_attempt 调用",
               "submit_attempt" in html)

    report.add("H6", cat, "产生 commit_assessment 调用",
               "commit_assessment" in html)

    report.add("H7", cat, "契约对象包含 outbox",
               bool(re.search(r"out\s*\.\s*outbox\s*=", html)) or "outbox:" in html)

    # The page must not smuggle a self-computed mastery into the assessment call.
    commit_block = re.search(
        r'enqueue\(\s*["\']commit_assessment["\'](.*?)\}\s*,', html, flags=re.S
    )
    if commit_block:
        report.add("H8", cat, "commit_assessment 入参不含 mastery_probability",
                   "mastery_probability" not in commit_block.group(1))
    else:
        report.add("H8", cat, "commit_assessment 入参不含 mastery_probability",
                   False, "未能定位 commit_assessment 入参块", warn_only=True)

    # Local demo numbers must be flagged as provisional rather than presented as fact.
    report.add("H9", cat, "demo 模式下标记 provisional",
               "provisional" in html)


def check_dom_references(report: Report, html: str) -> None:
    """Every element the script looks up must exist in the markup.

    A renamed DOM id with a stale script reference is invisible to static
    structure checks and only shows up as a runtime TypeError. This check
    catches the whole class.
    """
    cat = "I · DOM 引用完整性"

    defined = set(re.findall(r'\bid\s*=\s*"([^"]+)"', html))
    defined |= set(re.findall(r"\bid\s*=\s*'([^']+)'", html))

    referenced: set[str] = set()
    for pattern in (
        r'getElementById\(\s*["\']([^"\']+)["\']',
        r'\$\(\s*["\']([^"\']+)["\']',
        r'querySelector\(\s*["\']#([^"\']+)["\']',
    ):
        referenced |= set(re.findall(pattern, html))

    missing = sorted(referenced - defined)
    report.add(
        "I1", cat, "脚本引用的 DOM id 全部存在",
        not missing,
        f"引用了不存在的 id: {missing}" if missing else f"{len(referenced)} 个引用全部命中",
    )


def check_subject_components(report: Report, html: str, subject: str | None) -> None:
    cat = "G · 学科交互组件"
    if not subject or subject not in SUBJECT_COMPONENTS:
        report.add("G0", cat, "识别学科并检查必含组件", False,
                   f"未识别的 subject: {subject!r}", warn_only=True)
        return

    low = html.lower()
    for idx, (name, needles) in enumerate(SUBJECT_COMPONENTS[subject], start=1):
        hit = any(n.lower() in low for n in needles)
        report.add(f"G{idx}", cat, f"{subject} · {name}", hit,
                   "" if hit else "未检测到相关标识", warn_only=True)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def verify(path: Path) -> Report:
    raw = path.read_text(encoding="utf-8", errors="replace")
    html = _strip_comments(raw)
    report = Report(path=path)

    check_single_file(report, html, raw)
    check_three_zones(report, html)
    check_progressive_disclosure(report, html)
    check_feedback_and_scoring(report, html)
    check_contract(report, html)
    check_host_bridge(report, html)
    check_dom_references(report, html)
    check_visual(report, html)

    subject_match = re.search(r'subject["\']?\s*[:=]\s*["\']([a-z-]+)["\']', html)
    check_subject_components(report, html, subject_match.group(1) if subject_match else None)

    report.results.sort(key=lambda r: (_ORDER[r.status], r.check_id))
    return report


def render_markdown(reports: Sequence[Report]) -> str:
    lines = ["# 前端示例规范符合性检查", ""]
    for report in reports:
        total = len(report.results)
        lines += [
            f"## `{report.path.name}`",
            "",
            f"- 检查项：{total} ｜ 通过 **{len(report.passed)}** ｜ "
            f"警告 **{len(report.warnings)}** ｜ 失败 **{len(report.errors)}**",
            "",
        ]
        failures = report.errors + report.warnings
        if not failures:
            lines += ["全部检查项通过。", ""]
            continue
        lines += ["| 结果 | 检查项 | 说明 |", "|---|---|---|"]
        for r in failures:
            icon = "❌" if r.status == ERROR else "⚠️"
            detail = r.detail.replace("|", "\\|")
            lines.append(f"| {icon} {r.status} | `{r.check_id}` {r.title} | {detail} |")
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="HTML files to verify")
    parser.add_argument("--all", action="store_true",
                        help="verify every .html under examples/")
    parser.add_argument("--md", default=None, help="write a Markdown report here")
    parser.add_argument("--verbose", action="store_true", help="print passing checks too")
    args = parser.parse_args(argv)

    paths: list[Path] = [Path(p) for p in args.paths]
    if args.all:
        paths = sorted((REPO_ROOT / "examples").rglob("*.html"))
        if not paths:
            print("[verify_example] no example HTML files found; nothing to verify")
            return 0
    if not paths:
        parser.error("provide at least one HTML path, or use --all")

    reports = [verify(p) for p in paths if p.exists()]
    missing = [str(p) for p in paths if not p.exists()]
    for m in missing:
        print(f"error: file not found: {m}", file=sys.stderr)

    for report in reports:
        print(f"\n=== {report.path} ===")
        for r in report.results:
            if r.status == PASS and not args.verbose:
                continue
            mark = {PASS: "PASS ", WARN: "WARN ", ERROR: "FAIL "}[r.status]
            suffix = f"  <- {r.detail}" if r.detail else ""
            print(f"  [{mark}] {r.check_id:<6} {r.title}{suffix}")
        print(f"  -> {len(report.passed)} passed, {len(report.warnings)} warnings, "
              f"{len(report.errors)} errors")

    if args.md:
        out = Path(args.md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(reports), encoding="utf-8")
        print(f"\n[verify_example] wrote {out}", file=sys.stderr)

    if any(r.errors for r in reports) or missing:
        return 1
    if any(r.warnings for r in reports):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
