"""Multi-dimensional score aggregation (section 10.3-1).

The default policy is a **weighted mean over the judged dimensions**, with the
weights renormalised over whatever was actually scored - so a multiple-choice
item without a reasoning rubric still produces a meaningful aggregate.

Two dimensions are deliberately excluded from the aggregate:

* ``transfer`` and ``hint_dependency`` are separate Policy inputs. Folding them
  into ``overall_score`` would double-count them and mislead the learner, which
  is why the design doc calls this out explicitly.

This class is the built-in implementation of
:class:`leap.runtime.contracts.ScoreAggregator`; a rubric-based or learned
aggregator can be registered under the same kind.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = ["WeightedScoreAggregator", "AGGREGATED_DIMENSIONS", "EXCLUDED_DIMENSIONS"]

#: Dimensions that participate in ``overall_score``.
AGGREGATED_DIMENSIONS: tuple[str, ...] = (
    "correctness",
    "conceptual_understanding",
    "reasoning_quality",
    "application",
)

#: Dimensions that must NOT participate, and why.
EXCLUDED_DIMENSIONS: tuple[str, ...] = ("transfer", "hint_dependency")

DEFAULT_WEIGHTS: dict[str, float] = {
    "correctness": 0.40,
    "conceptual_understanding": 0.30,
    "reasoning_quality": 0.20,
    "application": 0.10,
}


class WeightedScoreAggregator:
    """Weighted mean with automatic renormalisation (section 10.3-1)."""

    def __init__(self, weights: Mapping[str, float] | None = None) -> None:
        merged = dict(DEFAULT_WEIGHTS)
        if weights:
            for key, value in weights.items():
                if key in EXCLUDED_DIMENSIONS:
                    continue
                try:
                    merged[str(key)] = float(value)
                except (TypeError, ValueError):
                    continue
        self.weights = merged

    def aggregate(self, scores: Mapping[str, Any]) -> float | None:
        total = 0.0
        total_weight = 0.0
        for dimension in AGGREGATED_DIMENSIONS:
            raw = scores.get(dimension)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            weight = float(self.weights.get(dimension, 0.0))
            if weight <= 0:
                continue
            total += value * weight
            total_weight += weight
        if total_weight <= 0:
            return None
        return round(total / total_weight, 6)

    def describe(self) -> dict:
        return {
            "implementation": "weighted",
            "aggregated_dimensions": list(AGGREGATED_DIMENSIONS),
            "excluded_dimensions": list(EXCLUDED_DIMENSIONS),
            "weights": dict(self.weights),
            "note": (
                "transfer and hint_dependency are excluded from the aggregate; "
                "they are consumed by the Policy engine as separate inputs"
            ),
        }
