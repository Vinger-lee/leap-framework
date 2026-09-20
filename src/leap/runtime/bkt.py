"""Simplified forgetting-aware Bayesian Knowledge Tracing (section 10.2-1).

Why this lives server-side
--------------------------
``mastery_probability`` is a *model estimate*, not ground truth. Letting the
host agent's LLM emit a probability directly produces unstable, unauditable
numbers. P0 therefore computes it here, from evidence the agent submits
through ``commit_assessment``.

The model
---------
One update step, in order:

1. **Time decay** - mastery drifts down while the learner is away from the
   node, using an exponential half-life (``forget_halflife_days``).
2. **Evidence update** - classic BKT posterior with ``p_guess`` / ``p_slip``.
   Partial credit is handled by blending the correct and incorrect posteriors
   with the observed score.
3. **Transition** - probability that the learner *learned* from the attempt
   (``p_transit``).
4. **Spontaneous forgetting** - a small per-opportunity leak (``p_forget``).

Every parameter is an engineering heuristic (section 30). This class is a
pluggable estimator behind :class:`~leap.runtime.state_guard.StateGuard`; P1
may replace it with an external estimator (mode B).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["BKTParams", "BKTEstimator"]

_EPS = 1e-9


@dataclass(frozen=True)
class BKTParams:
    """Parameters of the simplified forgetting-aware BKT."""

    p_init: float = 0.20
    p_transit: float = 0.30
    p_guess: float = 0.20
    p_slip: float = 0.10
    p_forget: float = 0.02
    forget_halflife_days: float = 30.0

    @classmethod
    def from_config(cls, cfg: Any) -> "BKTParams":
        """Build from a :class:`leap.config.Config` (or any mapping-like)."""
        get = cfg.get if hasattr(cfg, "get") else (lambda k, d=None: d)
        return cls(
            p_init=float(get("bkt.p_init", cls.p_init)),
            p_transit=float(get("bkt.p_transit", cls.p_transit)),
            p_guess=float(get("bkt.p_guess", cls.p_guess)),
            p_slip=float(get("bkt.p_slip", cls.p_slip)),
            p_forget=float(get("bkt.p_forget", cls.p_forget)),
            forget_halflife_days=float(
                get("bkt.forget_halflife_days", cls.forget_halflife_days)
            ),
        )

    def validate(self) -> "BKTParams":
        for name in ("p_init", "p_transit", "p_guess", "p_slip", "p_forget"):
            value = getattr(self, name)
            if not 0.0 <= value < 1.0:
                raise ValueError(f"BKT parameter {name} must be in [0, 1), got {value}")
        if self.p_guess + self.p_slip >= 1.0:
            raise ValueError("p_guess + p_slip must be < 1 for a discriminative model")
        if self.forget_halflife_days <= 0:
            raise ValueError("forget_halflife_days must be > 0")
        return self


class BKTEstimator:
    """Deterministic mastery estimator.

    The estimator is stateless: callers pass in the current prior and receive
    the updated posterior. Persistence is the storage layer's job.
    """

    def __init__(self, params: BKTParams | None = None) -> None:
        self.params = (params or BKTParams()).validate()

    # -- primitives --------------------------------------------------------
    def initial(self) -> float:
        """Prior mastery for a node with no evidence yet."""
        return self.params.p_init

    def time_decay(self, prior: float, elapsed_days: float) -> float:
        """Exponential retention decay toward zero over ``elapsed_days``."""
        if elapsed_days <= 0 or self.params.forget_halflife_days <= 0:
            return prior
        factor = 0.5 ** (elapsed_days / self.params.forget_halflife_days)
        return prior * factor

    def _posterior(self, prior: float, correct: bool) -> float:
        p = self.params
        if correct:
            numerator = prior * (1.0 - p.p_slip)
            denominator = numerator + (1.0 - prior) * p.p_guess
        else:
            numerator = prior * p.p_slip
            denominator = numerator + (1.0 - prior) * (1.0 - p.p_guess)
        if denominator <= _EPS:
            return prior
        return numerator / denominator

    def _transition(self, posterior: float) -> float:
        t = self.params.p_transit
        return posterior + (1.0 - posterior) * t

    def _spontaneous_forgetting(self, value: float) -> float:
        return value * (1.0 - self.params.p_forget)

    # -- public API --------------------------------------------------------
    def update(
        self,
        prior: float | None,
        *,
        correct: bool | None = None,
        score: float | None = None,
        elapsed_days: float = 0.0,
    ) -> float:
        """Return the updated mastery estimate.

        Parameters
        ----------
        prior:
            Current estimate; ``None`` means "no evidence yet" and falls back
            to :meth:`initial`.
        correct:
            Binary outcome. Ignored when ``score`` is provided.
        score:
            Partial credit in ``[0, 1]``. Blends the correct and incorrect
            posteriors, so "method right, arithmetic wrong" moves mastery
            less than a full success.
        elapsed_days:
            Time since the last assessment of this node, used for decay.
        """
        base = self.initial() if prior is None else _clamp(prior)
        decayed = self.time_decay(base, max(0.0, elapsed_days))

        if score is None and correct is None:
            # No new evidence: only time passed.
            return _clamp(self._spontaneous_forgetting(decayed))

        if score is None:
            posterior = self._posterior(decayed, bool(correct))
        else:
            s = _clamp(float(score))
            posterior = s * self._posterior(decayed, True) + (1.0 - s) * self._posterior(
                decayed, False
            )

        learned = self._transition(posterior)
        return _clamp(self._spontaneous_forgetting(learned))

    def confidence_weighted(
        self,
        prior: float | None,
        *,
        score: float,
        assessor_confidence: float = 1.0,
        elapsed_days: float = 0.0,
    ) -> float:
        """Update while discounting low-confidence assessments (section 29.2).

        When the assessor cannot judge reliably (``assessor_confidence`` near
        0) the observation is pulled toward the prior instead of being written
        in as if it were certain. This is the "do not turn uncertainty into
        ``mastery = 0``" rule of section 29.2.
        """
        updated = self.update(prior, score=score, elapsed_days=elapsed_days)
        base = self.initial() if prior is None else _clamp(prior)
        w = _clamp(assessor_confidence)
        return _clamp(base + (updated - base) * w)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))
