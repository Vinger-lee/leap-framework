"""Evidence Stage heuristics (section 11).

``estimated -> practiced -> demonstrated -> retained -> transferred``

Two important framing rules from the spec:

* This is LEAP's **internal evidence-stage operational model**. It is not
  presented as a universally agreed pedagogical standard.
* The thresholds below are a **reference default**. Per section 11.4 the
  authoritative criteria live in the Pedagogical Policy engine and are
  configurable; the State Guard only reads the resulting ``evidence_stage``
  and never re-derives it.

Evidence stages may regress. A node that once reached ``retained`` but has not
been touched for a long time drops back to ``practiced`` and re-enters review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "STAGES",
    "STAGE_ORDER",
    "EvidenceInput",
    "StageEvaluation",
    "evaluate_stage",
    "stage_index",
]

STAGES: tuple[str, ...] = ("estimated", "practiced", "demonstrated", "retained", "transferred")
STAGE_ORDER: dict[str, int] = {name: i for i, name in enumerate(STAGES)}


def stage_index(stage: str) -> int:
    return STAGE_ORDER.get(stage, 0)


@dataclass
class EvidenceInput:
    """Everything the reference heuristic needs to place a node."""

    mastery_probability: float = 0.0
    hint_dependency: float = 0.0
    valid_attempts: int = 0
    #: Successes produced with hint_level <= ``low_hint_max``.
    unassisted_successes: int = 0
    transfer_probes: int = 0
    transfer_score: float | None = None
    #: True when a spaced review re-confirmed the node after the configured gap.
    retention_confirmed: bool = False
    #: Days since the last assessment of this node.
    days_since_last_assessment: float | None = None
    #: Set by the caller when a long absence has eroded retention evidence.
    retention_lapsed: bool = False
    #: Set by the caller when the most recent transfer probe failed.
    latest_transfer_failed: bool = False


@dataclass
class StageEvaluation:
    stage: str
    reasons: list[str] = field(default_factory=list)
    regressed: bool = False
    previous: str = "estimated"

    @property
    def advanced(self) -> bool:
        return stage_index(self.stage) > stage_index(self.previous)

    def as_dict(self) -> dict:
        return {
            "previous": self.previous,
            "stage": self.stage,
            "regressed": self.regressed,
            "advanced": self.advanced,
            "reasons": self.reasons,
        }


def evaluate_stage(
    current: str,
    evidence: EvidenceInput,
    cfg: Any = None,
    *,
    low_hint_max: int = 1,
) -> StageEvaluation:
    """Return the evidence stage implied by ``evidence``.

    ``current`` is the authoritative stage currently stored on
    ``learner_knowledge_state``. The returned evaluation may move forward or
    backward; the caller (Policy) decides whether to persist it.
    """
    get = cfg.get if cfg is not None and hasattr(cfg, "get") else (lambda _k, d=None: d)

    mastery_threshold = float(get("mastery_threshold", 0.80))
    hint_ceiling_demo = 0.50
    hint_ceiling_practiced = 0.90
    transfer_pass = float(get("transfer_pass_score", 0.70))
    retention_interval_days = float(get("retention_interval_days", 1.0))

    reasons: list[str] = []
    ev = evidence

    # --- rollback paths (checked first: regression wins over promotion) ----
    if ev.retention_lapsed and stage_index(current) >= stage_index("retained"):
        reasons.append(
            "retention evidence decayed after a long gap; returning to practiced and "
            "re-entering the review queue"
        )
        return StageEvaluation(
            stage="practiced", reasons=reasons, regressed=True, previous=current
        )

    if ev.latest_transfer_failed and current == "transferred":
        reasons.append("latest transfer probe failed; transfer evidence withdrawn")
        return StageEvaluation(
            stage="demonstrated", reasons=reasons, regressed=True, previous=current
        )

    # --- forward evaluation -------------------------------------------------
    achieved = "estimated"
    if ev.valid_attempts < 1:
        reasons.append("no attempt evidence for this node; stage inferred only")
    elif ev.hint_dependency >= hint_ceiling_practiced:
        reasons.append(
            f"hint_dependency {ev.hint_dependency:.2f} >= {hint_ceiling_practiced}; "
            "attempts are not counted as effective practice"
        )
    else:
        achieved = "practiced"
        reasons.append(f"{ev.valid_attempts} effective attempt(s) with acceptable hint dependency")

    if achieved == "practiced":
        if (
            ev.mastery_probability >= mastery_threshold
            and ev.hint_dependency <= hint_ceiling_demo
            and ev.unassisted_successes >= 1
        ):
            achieved = "demonstrated"
            reasons.append(
                f"mastery {ev.mastery_probability:.2f} >= {mastery_threshold:.2f}, "
                f"hint_dependency {ev.hint_dependency:.2f} <= {hint_ceiling_demo:.2f}, "
                "and at least one low-hint success"
            )
        else:
            missing = []
            if ev.mastery_probability < mastery_threshold:
                missing.append(f"mastery {ev.mastery_probability:.2f} < {mastery_threshold:.2f}")
            if ev.hint_dependency > hint_ceiling_demo:
                missing.append(f"hint_dependency {ev.hint_dependency:.2f} > {hint_ceiling_demo:.2f}")
            if ev.unassisted_successes < 1:
                missing.append("no independent (low-hint) success yet")
            reasons.append("demonstrated not reached: " + "; ".join(missing))

    if achieved == "demonstrated":
        gap = ev.days_since_last_assessment or 0.0
        if ev.retention_confirmed and gap >= retention_interval_days:
            achieved = "retained"
            reasons.append(
                f"retained: re-confirmed after {gap:.1f} day(s) "
                f"(>= {retention_interval_days:.1f})"
            )
        else:
            reasons.append(
                "retained not reached: needs a successful spaced review after the "
                "configured interval"
            )

    if stage_index(achieved) >= stage_index("demonstrated"):
        if ev.transfer_probes >= 1 and (ev.transfer_score or 0.0) >= transfer_pass:
            achieved = "transferred"
            reasons.append(
                f"transfer probe passed with score {ev.transfer_score:.2f} "
                f">= {transfer_pass:.2f}"
            )
        elif ev.transfer_probes >= 1:
            reasons.append(
                f"transfer probe present but score {ev.transfer_score} below {transfer_pass:.2f}"
            )

    previous = current if current in STAGE_ORDER else "estimated"
    regressed = stage_index(achieved) < stage_index(previous)
    if regressed:
        reasons.append("stage regression: evidence no longer supports the recorded stage")

    return StageEvaluation(
        stage=achieved, reasons=reasons, regressed=regressed, previous=previous
    )
