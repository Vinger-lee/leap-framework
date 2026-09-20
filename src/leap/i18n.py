"""Internationalisation.

LEAP is model-agnostic and meant to be embedded in host agents written by
anyone, so user-facing text must not be hard-coded to one language. This module
holds the message catalogues and the lookup used by the runtime.

Scope: only strings that a **learner or operator actually reads** are
translated - State Guard rejection reasons, the Domain Grounding notice, mode
labels and the closing report headings. Internal log messages, exception types
and code comments stay in English so the codebase has one working language.

Adding a language
-----------------
1. Add the locale to :data:`SUPPORTED_LOCALES`.
2. Add a catalogue under the same keys. A missing key falls back to the default
   locale, and then to the key itself, so a partial translation never crashes.
3. Set ``locale: <code>`` in ``config/default.yaml`` or ``LEAP_LOCALE``.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

__all__ = [
    "DEFAULT_LOCALE",
    "SUPPORTED_LOCALES",
    "normalize_locale",
    "resolve_locale",
    "Translator",
    "translator_for",
    "MESSAGES",
]

DEFAULT_LOCALE = "zh-CN"

#: Locale codes this build ships catalogues for.
SUPPORTED_LOCALES: tuple[str, ...] = ("zh-CN", "en")

#: Aliases accepted from configuration or the environment.
_LOCALE_ALIASES: dict[str, str] = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "zh_cn": "zh-CN",
    "cn": "zh-CN",
    "chinese": "zh-CN",
    "中文": "zh-CN",
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "english": "en",
}


MESSAGES: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------
    "zh-CN": {
        # Domain Grounding (section 20 / 22.9)
        "domain_grounding.notice": (
            "即将执行【领域自学校准】，我会先学习该专题，生成知识基准报告后再对你开展教学。"
            "此过程会消耗更多 Token 并需要等待一段时间，但可以显著提升知识准确性。"
            "是否继续？或者你希望跳过该环节（跳过会增大回答幻觉、内容出错风险）？"
        ),
        "domain_grounding.reject.not_completed": (
            "尚未完成 Agent 领域自学校准，请先完成 Domain Grounding 阶段；"
            "如需跳过，请确认开启 allow_skip_domain_grounding 并知悉幻觉风险。"
        ),
        "domain_grounding.allow.waived": "本会话已明确跳过领域自学校准。",
        "domain_grounding.allow.completed": "领域自学校准已完成，基准报告已归档。",
        # Learning modes (section 32)
        "learning_mode.balanced.label": "均衡模式（默认）",
        "learning_mode.balanced.description": "不做任何覆写，完全使用工程默认参数。",
        "learning_mode.project_based.label": "以项目实战为主",
        "learning_mode.project_based.description": (
            "提高 PBL / 综合任务与迁移验证比重，降低纯讲解比重；"
            "迁移验证改为强制，允许更多次尝试后再给示范。"
        ),
        "learning_mode.exam_prep.label": "我要准备考试",
        "learning_mode.exam_prep.description": (
            "提高评估密度与检索练习比重，收窄提示上限（考试时没有提示），并把掌握阈值调高。"
        ),
        "learning_mode.core_only.label": "只学核心内容，尽快学会",
        "learning_mode.core_only.description": (
            "收窄范围与非核心节点，压缩单元颗粒度，提高练习密度，降低迁移验证要求以换取速度。"
        ),
        # Closing report (section 25)
        "report.title": "LEAP 学习报告",
        "report.topic": "主题",
        "report.learner": "学习者",
        "report.session": "会话",
        "report.learning_goal": "学习目标",
        "report.diagnostic_baseline": "诊断基线",
        "report.observed_evidence": "已观测证据",
        "report.estimated_state": "估计状态",
        "report.reasoning_quality": "推理质量",
        "report.learning_gain": "学习增益",
        "report.stage_distribution": "证据阶段分布",
        "report.remaining_uncertainty": "剩余不确定性",
        "report.recommended_next_step": "建议的下一步",
        "report.review_plan": "复习计划",
        "report.estimates_warning": "以下为**模型估计值**，不是实测事实。",
        "report.facts_warning": "以下为运行时记录的事实。",
    },
    # ------------------------------------------------------------------
    "en": {
        "domain_grounding.notice": (
            "About to run [domain self-calibration]: I will study this topic first and produce a "
            "knowledge baseline report before teaching you. This costs extra tokens and some "
            "waiting time, but substantially reduces hallucination and factual errors. Continue? "
            "Or would you rather skip this step (skipping increases the risk of hallucinated or "
            "incorrect content)?"
        ),
        "domain_grounding.reject.not_completed": (
            "Agent domain self-calibration has not been completed. Finish the Domain Grounding "
            "stage first; to skip it, enable allow_skip_domain_grounding and accept the "
            "hallucination risk."
        ),
        "domain_grounding.allow.waived": (
            "Domain grounding was explicitly waived for this session."
        ),
        "domain_grounding.allow.completed": (
            "Domain grounding completed with a benchmark report on file."
        ),
        "learning_mode.balanced.label": "Balanced (default)",
        "learning_mode.balanced.description": (
            "No overrides; the engineering defaults are used as-is."
        ),
        "learning_mode.project_based.label": "Project-first",
        "learning_mode.project_based.description": (
            "More problem-based and integrated tasks, more transfer verification, less pure "
            "explanation; transfer becomes mandatory and more retries are allowed before a "
            "worked example."
        ),
        "learning_mode.exam_prep.label": "Exam preparation",
        "learning_mode.exam_prep.description": (
            "Higher assessment density and more retrieval practice, a lower hint ceiling "
            "(there are no hints in an exam) and a higher mastery threshold."
        ),
        "learning_mode.core_only.label": "Core content only, learn fast",
        "learning_mode.core_only.description": (
            "Narrow the scope and skip non-core nodes, shrink unit granularity, raise practice "
            "density and relax transfer requirements in exchange for speed."
        ),
        "report.title": "LEAP Learning Report",
        "report.topic": "Topic",
        "report.learner": "Learner",
        "report.session": "Session",
        "report.learning_goal": "Learning Goal",
        "report.diagnostic_baseline": "Diagnostic Baseline",
        "report.observed_evidence": "Observed Evidence",
        "report.estimated_state": "Estimated State",
        "report.reasoning_quality": "Reasoning Quality",
        "report.learning_gain": "Learning Gain",
        "report.stage_distribution": "Evidence stage distribution",
        "report.remaining_uncertainty": "Remaining Uncertainty",
        "report.recommended_next_step": "Recommended Next Step",
        "report.review_plan": "Review Plan",
        "report.estimates_warning": "The following are **model estimates**, not measured facts.",
        "report.facts_warning": "Facts recorded by the runtime:",
    },
}


def normalize_locale(value: Any) -> str | None:
    """Map a user-supplied locale tag onto a supported locale, or ``None``."""
    if not value:
        return None
    needle = str(value).strip().lower().replace("_", "-")
    if needle in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[needle]
    # exact case-insensitive match against the supported list
    for locale in SUPPORTED_LOCALES:
        if locale.lower() == needle:
            return locale
    # prefix match, e.g. "en-AU" -> "en"
    prefix = needle.split("-")[0]
    return _LOCALE_ALIASES.get(prefix)


def resolve_locale(cfg: Any = None) -> str:
    """Determine the active locale.

    Precedence: explicit config value -> ``LEAP_LOCALE`` environment variable ->
    the platform locale -> :data:`DEFAULT_LOCALE`.
    """
    if cfg is not None and hasattr(cfg, "get"):
        resolved = normalize_locale(cfg.get("locale"))
        if resolved:
            return resolved

    resolved = normalize_locale(os.environ.get("LEAP_LOCALE"))
    if resolved:
        return resolved

    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        resolved = normalize_locale(os.environ.get(var))
        if resolved:
            return resolved

    return DEFAULT_LOCALE


class Translator:
    """Looks up a message key in the active locale, with safe fallbacks."""

    def __init__(self, locale: str | None = None) -> None:
        self.locale = normalize_locale(locale) or DEFAULT_LOCALE

    @property
    def catalogue(self) -> Mapping[str, str]:
        return MESSAGES.get(self.locale, MESSAGES[DEFAULT_LOCALE])

    def t(self, key: str, **kwargs: Any) -> str:
        """Return the message for ``key``.

        Resolution order: active locale -> default locale -> the key itself.
        ``kwargs`` are applied with :meth:`str.format`, and a formatting error
        falls back to the raw template rather than raising.
        """
        template = self.catalogue.get(key)
        if template is None:
            template = MESSAGES[DEFAULT_LOCALE].get(key, key)
        if not kwargs:
            return template
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return template

    def has(self, key: str) -> bool:
        return key in self.catalogue or key in MESSAGES[DEFAULT_LOCALE]

    def keys(self) -> set[str]:
        return set(MESSAGES[DEFAULT_LOCALE])

    def describe(self) -> dict:
        return {
            "locale": self.locale,
            "default_locale": DEFAULT_LOCALE,
            "supported_locales": list(SUPPORTED_LOCALES),
            "message_count": len(self.catalogue),
        }


def translator_for(cfg: Any = None) -> Translator:
    """Build a translator for the locale selected by configuration."""
    return Translator(resolve_locale(cfg))
