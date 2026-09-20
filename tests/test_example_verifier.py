"""Tests for the front-end example verifier.

Includes regression tests for three false positives the checker produced on its
first run against a compliant page - a checker that is wrong in the noisy
direction is worse than no checker, because it trains people to ignore it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from leap.config import REPO_ROOT

EXAMPLE = REPO_ROOT / "examples" / "01-python-recursion" / "leap-01-python-recursion.html"


def _load_verifier():
    path = REPO_ROOT / "scripts" / "verify_example.py"
    spec = importlib.util.spec_from_file_location("leap_verify_example", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VERIFIER = _load_verifier()


def _verify_text(tmp_path: Path, content: str):
    target = tmp_path / "example.html"
    target.write_text(content, encoding="utf-8")
    return VERIFIER.verify(target)


def _status(report, check_id: str) -> str:
    return next(r.status for r in report.results if r.check_id == check_id)


# ---------------------------------------------------------------------------
# Regression tests for checker false positives
# ---------------------------------------------------------------------------
class TestCheckerFalsePositives:
    def test_prose_mentioning_cdn_is_not_a_cdn_reference(self, tmp_path):
        """A footer saying '零 CDN' must not be flagged as a CDN dependency."""
        report = _verify_text(tmp_path, "<html><body>单文件零依赖 · 零 CDN · 零外部图片</body></html>")
        assert _status(report, "A4") == VERIFIER.PASS

    def test_real_cdn_host_is_flagged(self, tmp_path):
        report = _verify_text(
            tmp_path,
            '<html><head><link rel="stylesheet" href="//cdn.jsdelivr.net/npm/x.css"></head></html>',
        )
        assert _status(report, "A4") == VERIFIER.ERROR

    def test_responsive_token_override_does_not_break_font_check(self, tmp_path):
        """The root declaration is the spec anchor; a mobile override is legal."""
        report = _verify_text(
            tmp_path,
            "<style>:root{--fs-display:32px;}\n"
            "@media (max-width:600px){:root{--fs-display:23px;}}</style>",
        )
        detail = next(r.detail for r in report.results if r.check_id == "F4")
        assert "--fs-display" not in detail

    def test_arrow_glyphs_are_not_emoji(self, tmp_path):
        """'← → 单步' is a keyboard hint required by the design spec."""
        report = _verify_text(tmp_path, '<span class="kbd-hint">← → 单步　·　空格 播放</span>')
        assert _status(report, "F7") == VERIFIER.PASS

    def test_real_emoji_is_flagged(self, tmp_path):
        report = _verify_text(tmp_path, "<div>🎉 太棒了</div>")
        assert _status(report, "F7") == VERIFIER.ERROR

    def test_css_var_lookup_prefers_the_first_declaration(self):
        html = "<style>:root{--accent:#2B4AC4;} @media(x){:root{--accent:#fff;}}</style>"
        assert VERIFIER._css_vars(html)["--accent"] == "#2B4AC4"


# ---------------------------------------------------------------------------
# Detection tests
# ---------------------------------------------------------------------------
class TestDetections:
    def test_external_script_is_flagged(self, tmp_path):
        report = _verify_text(tmp_path, '<script src="https://example.com/x.js"></script>')
        assert _status(report, "A2") == VERIFIER.ERROR

    def test_network_call_is_flagged(self, tmp_path):
        report = _verify_text(tmp_path, "<script>fetch('/api')</script>")
        assert _status(report, "A5") == VERIFIER.ERROR

    def test_missing_output_contract_is_flagged(self, tmp_path):
        report = _verify_text(tmp_path, "<html><body>nothing</body></html>")
        assert _status(report, "B1") == VERIFIER.ERROR
        assert _status(report, "B3") == VERIFIER.ERROR

    def test_transition_all_is_flagged(self, tmp_path):
        report = _verify_text(tmp_path, "<style>.a{transition: all .2s}</style>")
        assert _status(report, "F6") == VERIFIER.ERROR

    def test_gradient_is_flagged(self, tmp_path):
        report = _verify_text(tmp_path, "<style>.a{background:linear-gradient(#fff,#000)}</style>")
        assert _status(report, "F6") == VERIFIER.ERROR

    def test_img_tag_is_flagged(self, tmp_path):
        report = _verify_text(tmp_path, '<img src="x.png">')
        assert _status(report, "F6") == VERIFIER.ERROR

    def test_wrong_token_value_is_flagged(self, tmp_path):
        report = _verify_text(tmp_path, "<style>:root{--accent:#2563eb;}</style>")
        detail = next(r.detail for r in report.results if r.check_id == "F1")
        assert "--accent" in detail

    def test_missing_learner_placeholder_is_flagged(self, tmp_path):
        report = _verify_text(tmp_path, "<script>const learner_id='real-id';</script>")
        assert _status(report, "E3") == VERIFIER.ERROR

    def test_events_reassignment_is_flagged(self, tmp_path):
        report = _verify_text(
            tmp_path, "<script>let events=[];events.push(1);events=[2];</script>"
        )
        assert _status(report, "B4") == VERIFIER.ERROR


# ---------------------------------------------------------------------------
# The real example
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not EXAMPLE.exists(), reason="example 01 not present")
class TestShippedExample:
    def test_passes_without_errors(self):
        report = VERIFIER.verify(EXAMPLE)
        assert report.errors == [], [f"{r.check_id}: {r.detail}" for r in report.errors]

    def test_declares_the_full_contract(self):
        report = VERIFIER.verify(EXAMPLE)
        for check_id in ("B1", "B2", "B3", "E1", "E2", "E3", "E4"):
            assert _status(report, check_id) == VERIFIER.PASS, check_id

    def test_is_fully_offline(self):
        report = VERIFIER.verify(EXAMPLE)
        for check_id in ("A1", "A2", "A3", "A4", "A5", "A6"):
            assert _status(report, check_id) == VERIFIER.PASS, check_id

    def test_exposes_the_host_bridge(self):
        report = VERIFIER.verify(EXAMPLE)
        for check_id in ("H1", "H2", "H4", "H5", "H6", "H7", "H8", "H9"):
            assert _status(report, check_id) == VERIFIER.PASS, check_id


# ---------------------------------------------------------------------------
# Host-bridge checks
# ---------------------------------------------------------------------------
class TestHostBridgeChecks:
    def test_missing_bridge_is_flagged(self, tmp_path):
        report = _verify_text(tmp_path, "<html><body>no bridge here</body></html>")
        assert _status(report, "H1") == VERIFIER.ERROR
        assert _status(report, "H2") == VERIFIER.ERROR

    def test_self_computed_mastery_in_commit_call_is_flagged(self, tmp_path):
        """The page must not smuggle its own mastery into the assessment call."""
        html = (
            '<script>window.LEAP={hydrate:function(){},drainOutbox:function(){},'
            'peekOutbox:function(){},mode:"demo",hosted:false,provisional:true,'
            'outbox:[]};'
            'function f(){ enqueue("commit_assessment", { mastery_probability: 0.9, '
            'raw_answer: "x" }, "n"); }</script>'
        )
        assert _status(_verify_text(tmp_path, html), "H8") == VERIFIER.ERROR

    def test_commit_call_without_mastery_passes(self, tmp_path):
        html = (
            '<script>window.LEAP={hydrate:function(){},drainOutbox:function(){},'
            'peekOutbox:function(){},mode:"demo",hosted:false,provisional:true,'
            'outbox:[]};'
            'function f(){ enqueue("commit_assessment", { raw_answer: "x" }, "n"); }</script>'
        )
        assert _status(_verify_text(tmp_path, html), "H8") == VERIFIER.PASS


class TestDomReferenceChecks:
    def test_missing_referenced_id_is_flagged(self, tmp_path):
        html = '<html><body><div id="a"></div><script>$("a");$("b");</script></body></html>'
        report = _verify_text(tmp_path, html)
        assert _status(report, "I1") == VERIFIER.ERROR
        assert "b" in next(r.detail for r in report.results if r.check_id == "I1")

    def test_all_references_resolve(self, tmp_path):
        html = (
            '<html><body><div id="a"></div><div id="c"></div>'
            '<script>getElementById("a"); $("c");</script></body></html>'
        )
        assert _status(_verify_text(tmp_path, html), "I1") == VERIFIER.PASS

    def test_query_selector_id_is_checked(self, tmp_path):
        html = '<html><body><div id="x"></div><script>document.querySelector("#y")</script></body></html>'
        assert _status(_verify_text(tmp_path, html), "I1") == VERIFIER.ERROR

    def test_shipped_examples_have_no_broken_references(self):
        """A renamed id with a stale script reference only fails at runtime."""
        for html_path in sorted((REPO_ROOT / "examples").rglob("*.html")):
            report = VERIFIER.verify(html_path)
            assert _status(report, "I1") == VERIFIER.PASS, (
                f"{html_path.name}: {next(r.detail for r in report.results if r.check_id == 'I1')}"
            )


# ---------------------------------------------------------------------------
# Bridge injector
# ---------------------------------------------------------------------------
BRIDGE_TOOL = REPO_ROOT / "scripts" / "apply_leap_bridge.py"


def _load_bridge_tool():
    spec = importlib.util.spec_from_file_location("leap_apply_bridge", BRIDGE_TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BRIDGE = _load_bridge_tool()


class TestBridgeInjector:
    @staticmethod
    def _sample() -> str:
        """A minimal page carrying every anchor the injector needs."""
        return (
            "<html><head><style>:root{--paper:#FAF9F6;}\n</style></head><body>\n"
            '<p class="spine-note">disclaimer</p>\n'
            '    <div class="zone-body">\n      <div class="console">\n'
            "      </div>\n    </div>\n"
            "<script>\n"
            "  var EVENT_COLOR = {\n"
            '    attempt_submitted: "#4C7BD9",\n'
            '    item_completed: "#2E7D5B"\n'
            "  };\n"
            "  function pushEvent(t, p) {\n"
            "    var ev = {};\n"
            "    state.events.push(ev);\n    renderAll();\n    return ev;\n  }\n"
            "  function commitAssessment(item) {\n"
            "    var a = {};\n"
            "    a.overall_score = aggregate(a);\n"
            "    a.evidence_stage = deriveStage(a);\n"
            '    if (typeof item.transfer === "number" && item.transfer >= 0.7) a.evidence_stage = "transferred";\n'
            "    state.assessment = a;\n\n"
            "    mastery = Math.max(0, Math.min(0.98, mastery + (a.correctness - 0.5) * 0.14 - dep * 0.04));\n"
            "    renderAll();\n    return a;\n  }\n"
            "  function renderAll() {\n"
            "    renderOutput(); renderSpine(); renderRail();\n  }\n"
            "  function snapshot() { return clone(state); }\n"
            "  return {\n    getInteractionResult: getInteractionResult,\n  };\n"
            "</script></body></html>\n"
        )

    def _write(self, tmp_path: Path) -> Path:
        target = tmp_path / "sample.html"
        target.write_text(self._sample(), encoding="utf-8", newline="\n")
        return target

    def test_patch_adds_the_bridge(self, tmp_path):
        target = self._write(tmp_path)
        assert BRIDGE.apply_bridge(target) == "patched"
        text = target.read_text(encoding="utf-8")
        assert BRIDGE.BRIDGE_MARKER in text
        assert "function hydrate(" in text
        assert "drainOutbox" in text

    def test_patch_is_idempotent(self, tmp_path):
        target = self._write(tmp_path)
        BRIDGE.apply_bridge(target)
        assert BRIDGE.apply_bridge(target) == "already"

    def test_revert_restores_the_original_byte_for_byte(self, tmp_path):
        target = self._write(tmp_path)
        original = target.read_bytes()
        BRIDGE.apply_bridge(target)
        assert target.read_bytes() != original
        assert BRIDGE.apply_bridge(target, reverse=True) == "reverted"
        assert target.read_bytes() == original

    def test_line_endings_are_preserved(self, tmp_path):
        """A CRLF file must stay CRLF; a LF file must stay LF."""
        target = self._write(tmp_path)
        BRIDGE.apply_bridge(target)
        assert b"\r\n" not in target.read_bytes()

        crlf = tmp_path / "crlf.html"
        crlf.write_bytes(self._sample().replace("\n", "\r\n").encode("utf-8"))
        BRIDGE.apply_bridge(crlf)
        assert b"\r\n" in crlf.read_bytes()

    def test_broken_anchor_fails_loudly(self, tmp_path):
        target = tmp_path / "broken.html"
        target.write_text("<html><body>nothing to patch</body></html>", encoding="utf-8")
        with pytest.raises(SystemExit):
            BRIDGE.apply_bridge(target)

    def test_patched_page_has_no_syntax_error(self, tmp_path):
        """The injected block must not duplicate a closing brace."""
        target = self._write(tmp_path)
        BRIDGE.apply_bridge(target)
        text = target.read_text(encoding="utf-8")
        assert text.count('item_completed: "#2E7D5B"') == 1
        # exactly one closing brace between the colour map and the bridge banner
        between = text.split('item_completed: "#2E7D5B"')[1].split("LEAP_HOST_BRIDGE")[0]
        assert between.count("};") == 1, between

    def test_check_reports_completeness_not_just_presence(self, tmp_path):
        """A regenerated page can keep the banner while dropping a field."""
        target = self._write(tmp_path)
        BRIDGE.apply_bridge(target)
        # simulate a regeneration that lost the outbox declaration
        text = target.read_text(encoding="utf-8").replace("    outbox: [],\n", "", 1)
        target.write_text(text, encoding="utf-8")

        status = BRIDGE.bridge_status(target)
        assert status["has_banner"] is True
        assert status["present"] is False
        assert "outbox queue" in status["missing"]

    def test_repair_reinserts_the_dropped_field(self, tmp_path):
        target = self._write(tmp_path)
        BRIDGE.apply_bridge(target)
        target.write_text(
            target.read_text(encoding="utf-8").replace("    outbox: [],\n", "", 1),
            encoding="utf-8",
        )
        assert BRIDGE.repair_bridge(target) == "repaired"
        assert BRIDGE.bridge_status(target)["present"] is True

    def test_repair_on_a_healthy_bridge_is_a_no_op(self, tmp_path):
        target = self._write(tmp_path)
        BRIDGE.apply_bridge(target)
        assert BRIDGE.repair_bridge(target) == "ok"

    def test_repair_refuses_a_page_without_a_bridge(self, tmp_path):
        target = tmp_path / "plain.html"
        target.write_text("<html><body>nothing</body></html>", encoding="utf-8")
        assert BRIDGE.repair_bridge(target) == "unrepairable"

    def test_repair_preserves_line_endings(self, tmp_path):
        target = self._write(tmp_path)
        BRIDGE.apply_bridge(target)
        target.write_text(
            target.read_text(encoding="utf-8").replace("    outbox: [],\n", "", 1),
            encoding="utf-8", newline="\n",
        )
        BRIDGE.repair_bridge(target)
        assert b"\r\n" not in target.read_bytes()

    def test_shipped_examples_have_complete_bridges(self):
        for html_path in sorted((REPO_ROOT / "examples").rglob("*.html")):
            status = BRIDGE.bridge_status(html_path)
            assert status["present"], f"{html_path.name} missing: {status['missing']}"
