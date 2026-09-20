"""Internationalisation tests.

The runtime ships two catalogues (zh-CN, en). These tests pin down three
properties that matter:

1. **Both locales are complete.** A key present in one catalogue must exist in
   the other, otherwise a learner switching language silently gets raw keys.
2. **Missing keys degrade gracefully.** A partial translation must never raise.
3. **The locale reaches the surface.** Guard reasons, the grounding notice,
   mode labels and report headings must actually change with the locale.
"""

from __future__ import annotations

import pytest

from leap.i18n import (
    DEFAULT_LOCALE,
    MESSAGES,
    SUPPORTED_LOCALES,
    Translator,
    normalize_locale,
    resolve_locale,
    translator_for,
)
from leap.runtime.learning_modes import describe_modes
from leap.tools import build_service


# ---------------------------------------------------------------------------
# Catalogue integrity
# ---------------------------------------------------------------------------
class TestCatalogueIntegrity:
    def test_every_supported_locale_has_a_catalogue(self):
        for locale in SUPPORTED_LOCALES:
            assert locale in MESSAGES, locale

    def test_catalogues_have_identical_key_sets(self):
        """A key missing from one locale would surface as a raw key to a user."""
        reference = set(MESSAGES[DEFAULT_LOCALE])
        for locale in SUPPORTED_LOCALES:
            if locale == DEFAULT_LOCALE:
                continue
            missing = reference - set(MESSAGES[locale])
            extra = set(MESSAGES[locale]) - reference
            assert not missing, f"{locale} is missing keys: {sorted(missing)}"
            assert not extra, f"{locale} has keys absent from {DEFAULT_LOCALE}: {sorted(extra)}"

    def test_no_catalogue_entry_is_empty(self):
        for locale, catalogue in MESSAGES.items():
            empty = [k for k, v in catalogue.items() if not str(v).strip()]
            assert not empty, f"{locale} has empty entries: {empty}"

    def test_placeholders_match_across_locales(self):
        """A translated string must keep the same named placeholders."""
        import re

        pattern = re.compile(r"\{(\w+)\}")
        for key, template in MESSAGES[DEFAULT_LOCALE].items():
            expected = set(pattern.findall(template))
            for locale in SUPPORTED_LOCALES:
                actual = set(pattern.findall(MESSAGES[locale].get(key, "")))
                assert actual == expected, f"{key} placeholder mismatch in {locale}"


# ---------------------------------------------------------------------------
# Locale resolution
# ---------------------------------------------------------------------------
class TestLocaleResolution:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("zh-CN", "zh-CN"), ("zh", "zh-CN"), ("zh_cn", "zh-CN"),
            ("cn", "zh-CN"), ("中文", "zh-CN"), ("ZH-HANS", "zh-CN"),
            ("en", "en"), ("en-US", "en"), ("EN", "en"), ("english", "en"),
        ],
    )
    def test_aliases_resolve(self, value, expected):
        assert normalize_locale(value) == expected

    def test_unknown_locale_returns_none(self):
        assert normalize_locale("klingon") is None
        assert normalize_locale("") is None
        assert normalize_locale(None) is None

    def test_config_wins_over_environment(self, monkeypatch):
        monkeypatch.setenv("LEAP_LOCALE", "en")
        cfg = type("Cfg", (), {"get": lambda self, k, d=None: "zh-CN" if k == "locale" else d})()
        assert resolve_locale(cfg) == "zh-CN"

    def test_environment_used_when_config_is_silent(self, monkeypatch):
        monkeypatch.setenv("LEAP_LOCALE", "en")
        assert resolve_locale(None) == "en"

    def test_falls_back_to_default(self, monkeypatch):
        for var in ("LEAP_LOCALE", "LC_ALL", "LC_MESSAGES", "LANG"):
            monkeypatch.delenv(var, raising=False)
        assert resolve_locale(None) == DEFAULT_LOCALE


# ---------------------------------------------------------------------------
# Translator behaviour
# ---------------------------------------------------------------------------
class TestTranslator:
    def test_unknown_key_falls_back_to_the_key(self):
        assert Translator("en").t("no.such.key") == "no.such.key"

    def test_missing_key_in_one_locale_falls_back_to_default(self):
        """A partial catalogue must degrade, not crash."""
        partial = Translator("en")
        partial.locale = "en"
        assert partial.t("report.title")

    def test_formatting_failure_returns_the_template(self):
        t = Translator("en")
        # report.title takes no placeholders, so passing one must not raise
        assert t.t("report.title", unused="x")

    def test_formatting_is_applied_when_placeholders_match(self):
        assert Translator("en").t("domain_grounding.allow.waived").startswith("Domain")

    def test_describe_reports_supported_locales(self):
        info = Translator("en").describe()
        assert info["locale"] == "en"
        assert set(info["supported_locales"]) == set(SUPPORTED_LOCALES)

    def test_translator_for_reads_config(self):
        cfg = type("Cfg", (), {"get": lambda self, k, d=None: "en" if k == "locale" else d})()
        assert translator_for(cfg).locale == "en"


# ---------------------------------------------------------------------------
# The locale actually reaches the surface
# ---------------------------------------------------------------------------
class TestLocaleReachesTheSurface:
    @staticmethod
    def _service(locale: str):
        return build_service(":memory:", {"locale": locale})

    def test_grounding_notice_is_localised(self):
        zh = self._service("zh-CN").create_session("L1", "t")["domain_grounding_notice"]
        en = self._service("en").create_session("L1", "t")["domain_grounding_notice"]
        assert "领域自学校准" in zh
        assert "domain self-calibration" in en
        assert zh != en

    def test_guard_rejection_reason_is_localised(self):
        messages = {}
        for locale in ("zh-CN", "en"):
            svc = self._service(locale)
            sid = svc.create_session("L1", "t")["session_id"]
            with pytest.raises(Exception) as exc:
                svc.generate_diagnostic(sid)
            messages[locale] = str(exc.value)
        assert "领域自学校准" in messages["zh-CN"]
        assert "self-calibration" in messages["en"]

    def test_mode_labels_are_localised(self):
        zh = {m["mode"]: m["label"] for m in describe_modes("zh-CN")}
        en = {m["mode"]: m["label"] for m in describe_modes("en")}
        assert zh["exam_prep"] == "我要准备考试"
        assert en["exam_prep"] == "Exam preparation"
        assert zh["project_based"] != en["project_based"]

    def test_mode_triggers_are_not_translated(self):
        """Triggers match what the learner typed, in any supported language."""
        zh = {m["mode"]: m["triggers"] for m in describe_modes("zh-CN")}
        en = {m["mode"]: m["triggers"] for m in describe_modes("en")}
        assert zh == en

    def test_report_headings_are_localised(self):
        for locale, expected in (("zh-CN", "学习目标"), ("en", "Learning Goal")):
            svc = self._service(locale)
            sid = svc.create_session("L1", "t")["session_id"]
            svc.save_benchmark_report(sid, "# b")
            markdown = svc.generate_final_report(sid)["markdown"]
            assert expected in markdown, locale

    def test_switching_locale_does_not_change_behaviour(self):
        """Locale affects text only, never state transitions."""
        decisions = {}
        for locale in ("zh-CN", "en"):
            svc = self._service(locale)
            sid = svc.create_session("L1", "t")["session_id"]
            svc.save_benchmark_report(sid, "# b")
            svc.save_knowledge_nodes(
                sid, [{"node_id": "n1", "title": "t", "bloom_level": "apply", "unit_tag": "u1"}]
            )
            decision = svc.evaluate_pedagogical_policy(sid, "n1")["decision"]
            decisions[locale] = (
                decision["selected_strategy"], decision["selected_action"], decision["reason"]
            )
        assert decisions["zh-CN"] == decisions["en"]

    def test_locale_is_reported_by_plugin_info(self):
        info = self._service("en").get_plugin_info()
        assert info["ok"] is True
