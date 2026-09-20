"""Custom learning modes and policy overrides (section 32).

A learner can say things like "以项目实战为主" / "我要准备考试" /
"只学核心内容，尽快学会". Section 32 requires the system to respond by
adjusting the **configuration layer**, explicitly *not* by changing the
underlying program::

    这些调整应保存为：Learning Configuration + Pedagogical Policy Overrides
    而不是修改底层程序。

Two kinds of adjustment are produced:

* **overrides** - concrete configuration keys the rule engine actually reads
  (thresholds, retry limits, transfer requirement, interleaving). These change
  behaviour.
* **preferences** - a preferred strategy and action set. The rule engine keeps
  its own correctness invariants and does not let a preference bypass a
  State Guard check; preferences are guidance for the host agent's
  presentation choice, and are surfaced through ``get_teaching_context``.

Anything unrecognised is reported back rather than silently ignored.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = [
    "LEARNING_MODES",
    "DEFAULT_MODE",
    "resolve_mode",
    "build_overrides",
    "describe_modes",
    "resolve_request",
]

DEFAULT_MODE = "balanced"

#: Configuration keys a mode is allowed to override. Keeping this list explicit
#: stops a mode from reaching into unrelated parameters.
OVERRIDABLE_KEYS: frozenset[str] = frozenset(
    {
        "mastery_threshold",
        "max_hint_level",
        "max_retry_before_example",
        "default_transfer_requirement",
        "interleaving_enabled",
        "diagnostic_depth",
        "unit_concept_budget",
        "hint_dependency_high",
        "reasoning_quality_low",
    }
)


LEARNING_MODES: dict[str, dict[str, Any]] = {
    "balanced": {
        "label": "均衡模式（默认）",
        "triggers": ["默认", "balanced", "正常"],
        "description": "不做任何覆写，完全使用工程默认参数。",
        "overrides": {},
        "preferences": {},
    },
    "project_based": {
        "label": "以项目实战为主",
        "triggers": ["以项目实战为主", "项目实战", "项目驱动", "多做项目", "project", "pbl"],
        "description": (
            "提高 PBL / 综合任务与迁移验证比重，降低纯讲解比重；"
            "迁移验证改为强制，允许更多次尝试后再给示范。"
        ),
        "overrides": {
            "default_transfer_requirement": "always",
            "max_retry_before_example": 4,
            "interleaving_enabled": "conditional",
        },
        "preferences": {
            "preferred_strategy": "PBL",
            "preferred_actions": ["Generate Practice", "Run Transfer Probe", "Record Reflection"],
            "deprioritised_actions": ["Explain Concept"],
        },
    },
    "exam_prep": {
        "label": "我要准备考试",
        "triggers": ["准备考试", "考试", "备考", "应试", "exam", "test prep"],
        "description": (
            "提高评估密度与检索练习比重，收窄提示上限（考试时没有提示），"
            "并把掌握阈值调高。"
        ),
        "overrides": {
            "mastery_threshold": 0.85,
            "max_hint_level": 2,
            "default_transfer_requirement": "always",
            "interleaving_enabled": "conditional",
        },
        "preferences": {
            "preferred_strategy": "Retrieval Practice",
            "preferred_actions": ["Generate Retrieval Item", "Generate Practice"],
            "deprioritised_actions": ["Provide Worked Example"],
        },
    },
    "core_only": {
        "label": "只学核心内容，尽快学会",
        "triggers": ["只学核心", "核心内容", "尽快学会", "速成", "精简", "core only", "fast"],
        "description": (
            "收窄范围与非核心节点，压缩单元颗粒度，提高练习密度，"
            "降低迁移验证要求以换取速度。"
        ),
        "overrides": {
            "mastery_threshold": 0.75,
            "unit_concept_budget": 5,
            "max_retry_before_example": 2,
            "default_transfer_requirement": "none",
            "diagnostic_depth": "shallow",
        },
        "preferences": {
            "preferred_strategy": "Explanation",
            "preferred_actions": ["Explain Concept", "Generate Practice"],
            "deprioritised_actions": ["Run Transfer Probe"],
        },
    },
}


def describe_modes(locale: str | None = None) -> list[dict]:
    """Return the mode catalogue for the host agent, localised.

    ``triggers`` are deliberately **not** translated: they are matched against
    what the learner actually typed, and learners may type in any language the
    catalogue covers.
    """
    from leap.i18n import Translator

    translator = Translator(locale)
    out: list[dict] = []
    for name, spec in LEARNING_MODES.items():
        label_key = f"learning_mode.{name}.label"
        desc_key = f"learning_mode.{name}.description"
        out.append(
            {
                "mode": name,
                "label": translator.t(label_key) if translator.has(label_key) else spec["label"],
                "description": (
                    translator.t(desc_key) if translator.has(desc_key) else spec["description"]
                ),
                "triggers": spec["triggers"],
                "overrides": spec["overrides"],
                "preferences": spec["preferences"],
            }
        )
    return out


def resolve_mode(request: str | None) -> str | None:
    """Map a free-text request onto a known mode name.

    Returns ``None`` when nothing matches, so the caller can tell the user
    instead of silently doing nothing.
    """
    if not request:
        return None
    needle = str(request).strip().lower()
    if not needle:
        return None
    if needle in LEARNING_MODES:
        return needle
    for name, spec in LEARNING_MODES.items():
        for trigger in spec["triggers"]:
            if trigger.lower() in needle:
                return name
    return None


def resolve_request(
    request: str | None = None,
    mode: str | None = None,
    extra_overrides: Mapping[str, Any] | None = None,
) -> dict:
    """Turn a learner request into a concrete configuration change.

    Returns a dict with ``mode``, ``overrides``, ``preferences`` and
    ``unrecognised``. Unknown mode names and disallowed override keys are
    reported rather than dropped.
    """
    result: dict[str, Any] = {
        "mode": DEFAULT_MODE,
        "overrides": {},
        "preferences": {},
        "unrecognised": [],
    }

    resolved = None
    if mode:
        resolved = mode if mode in LEARNING_MODES else None
        if resolved is None:
            result["unrecognised"].append(f"unknown mode: {mode}")
    if resolved is None and request:
        resolved = resolve_mode(request)
        if resolved is None:
            result["unrecognised"].append(f"request did not match any known learning mode: {request}")

    if resolved:
        spec = LEARNING_MODES[resolved]
        result["mode"] = resolved
        result["overrides"].update(spec["overrides"])
        result["preferences"].update(spec["preferences"])

    for key, value in (extra_overrides or {}).items():
        if key in OVERRIDABLE_KEYS:
            result["overrides"][key] = value
        elif key == "preferred_strategy" or key == "preferred_actions":
            result["preferences"][key] = value
        else:
            result["unrecognised"].append(f"override key is not allowed: {key}")

    return result


def build_overrides(
    mode: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict:
    """Convenience wrapper returning just the override mapping."""
    return resolve_request(mode=mode, extra_overrides=extra)["overrides"]
