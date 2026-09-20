"""Unit tests for the deterministic runtime components.

These cover the parts of LEAP that must behave identically on every machine:
the BKT estimator, the evidence-stage heuristic and the FSRS wrapper.
"""

from __future__ import annotations

import pytest

from leap.runtime.bkt import BKTEstimator, BKTParams
from leap.runtime.evidence import EvidenceInput, evaluate_stage, stage_index
from leap.runtime.scheduler import RATING_NAMES, ReviewScheduler, rating_from_int


# ---------------------------------------------------------------------------
# BKT
# ---------------------------------------------------------------------------
class TestBKT:
    def test_initial_matches_configured_prior(self, base_config):
        estimator = BKTEstimator(BKTParams.from_config(base_config))
        assert estimator.initial() == pytest.approx(0.20)

    def test_correct_answers_increase_mastery_monotonically(self, base_config):
        estimator = BKTEstimator(BKTParams.from_config(base_config))
        values = []
        p = estimator.initial()
        for _ in range(5):
            p = estimator.update(p, correct=True)
            values.append(p)
        assert values == sorted(values)
        assert values[-1] > 0.9

    def test_incorrect_answers_decrease_mastery(self, base_config):
        estimator = BKTEstimator(BKTParams.from_config(base_config))
        p = 0.9
        updated = estimator.update(p, correct=False)
        assert updated < p

    def test_partial_credit_sits_between_pass_and_fail(self, base_config):
        estimator = BKTEstimator(BKTParams.from_config(base_config))
        prior = 0.5
        perfect = estimator.update(prior, score=1.0)
        half = estimator.update(prior, score=0.5)
        zero = estimator.update(prior, score=0.0)
        assert zero < half < perfect

    def test_time_decay_reduces_mastery(self, base_config):
        estimator = BKTEstimator(BKTParams.from_config(base_config))
        assert estimator.time_decay(0.8, 30.0) == pytest.approx(0.4, abs=1e-6)
        assert estimator.time_decay(0.8, 0.0) == pytest.approx(0.8)

    def test_no_evidence_still_decays(self, base_config):
        estimator = BKTEstimator(BKTParams.from_config(base_config))
        decayed = estimator.update(0.8, elapsed_days=60.0)
        assert decayed < 0.8

    def test_low_assessor_confidence_barely_moves_the_estimate(self, base_config):
        """Section 29.2: uncertainty must not be written in as fact."""
        estimator = BKTEstimator(BKTParams.from_config(base_config))
        confident = estimator.confidence_weighted(0.8, score=0.0, assessor_confidence=1.0)
        unsure = estimator.confidence_weighted(0.8, score=0.0, assessor_confidence=0.05)
        assert unsure > confident
        assert unsure == pytest.approx(0.8, abs=0.05)

    def test_result_is_always_a_probability(self, base_config):
        estimator = BKTEstimator(BKTParams.from_config(base_config))
        p = estimator.initial()
        for correct in (True, False, True, False, True):
            p = estimator.update(p, correct=correct, elapsed_days=7.0)
            assert 0.0 <= p <= 1.0

    def test_invalid_parameters_are_rejected(self):
        with pytest.raises(ValueError):
            BKTParams(p_guess=0.7, p_slip=0.5).validate()
        with pytest.raises(ValueError):
            BKTParams(p_transit=1.5).validate()
        with pytest.raises(ValueError):
            BKTParams(forget_halflife_days=0).validate()


# ---------------------------------------------------------------------------
# Evidence stages
# ---------------------------------------------------------------------------
class TestEvidenceStages:
    def test_no_attempts_stays_estimated(self, base_config):
        result = evaluate_stage("estimated", EvidenceInput(), base_config)
        assert result.stage == "estimated"

    def test_effective_attempt_reaches_practiced(self, base_config):
        evidence = EvidenceInput(valid_attempts=1, hint_dependency=0.2)
        assert evaluate_stage("estimated", evidence, base_config).stage == "practiced"

    def test_high_hint_dependency_blocks_practiced(self, base_config):
        evidence = EvidenceInput(valid_attempts=3, hint_dependency=0.95)
        assert evaluate_stage("estimated", evidence, base_config).stage == "estimated"

    def test_mastery_without_independent_success_is_not_demonstrated(self, base_config):
        evidence = EvidenceInput(
            mastery_probability=0.95, hint_dependency=0.2, valid_attempts=5, unassisted_successes=0
        )
        assert evaluate_stage("estimated", evidence, base_config).stage == "practiced"

    def test_full_criteria_reaches_demonstrated(self, base_config):
        evidence = EvidenceInput(
            mastery_probability=0.9, hint_dependency=0.2, valid_attempts=5, unassisted_successes=2
        )
        assert evaluate_stage("estimated", evidence, base_config).stage == "demonstrated"

    def test_transfer_probe_promotes_to_transferred(self, base_config):
        evidence = EvidenceInput(
            mastery_probability=0.9, hint_dependency=0.2, valid_attempts=5,
            unassisted_successes=2, transfer_probes=1, transfer_score=0.8,
        )
        assert evaluate_stage("demonstrated", evidence, base_config).stage == "transferred"

    def test_transfer_below_threshold_does_not_promote(self, base_config):
        evidence = EvidenceInput(
            mastery_probability=0.9, hint_dependency=0.2, valid_attempts=5,
            unassisted_successes=2, transfer_probes=1, transfer_score=0.5,
        )
        assert evaluate_stage("demonstrated", evidence, base_config).stage == "demonstrated"

    def test_retention_lapse_rolls_back_to_practiced(self, base_config):
        evidence = EvidenceInput(
            mastery_probability=0.9, hint_dependency=0.2, valid_attempts=8,
            unassisted_successes=4, retention_lapsed=True,
        )
        result = evaluate_stage("retained", evidence, base_config)
        assert result.stage == "practiced"
        assert result.regressed is True

    def test_failed_transfer_rolls_back_to_demonstrated(self, base_config):
        evidence = EvidenceInput(
            mastery_probability=0.9, hint_dependency=0.2, valid_attempts=8,
            unassisted_successes=4, transfer_probes=2, transfer_score=0.2,
            latest_transfer_failed=True,
        )
        result = evaluate_stage("transferred", evidence, base_config)
        assert result.stage == "demonstrated"
        assert result.regressed is True

    def test_stage_order_is_stable(self):
        assert stage_index("estimated") < stage_index("practiced")
        assert stage_index("practiced") < stage_index("demonstrated")
        assert stage_index("demonstrated") < stage_index("retained")
        assert stage_index("retained") < stage_index("transferred")
        assert stage_index("nonsense") == 0


# ---------------------------------------------------------------------------
# FSRS scheduler
# ---------------------------------------------------------------------------
class TestScheduler:
    def test_rating_scale_matches_fsrs_standard(self):
        assert RATING_NAMES == {1: "again", 2: "hard", 3: "good", 4: "easy"}
        assert rating_from_int(1).name == "Again"
        assert rating_from_int(4).name == "Easy"

    def test_invalid_rating_is_rejected(self):
        with pytest.raises(ValueError):
            rating_from_int(5)
        with pytest.raises(ValueError):
            rating_from_int("nope")

    def test_review_produces_a_future_due_date(self, base_config):
        scheduler = ReviewScheduler(base_config)
        outcome = scheduler.review(rating=3, review_count=0)
        assert outcome.due_at > outcome.last_review_at
        assert outcome.interval_days > 0
        assert outcome.rating == 3

    def test_higher_rating_extends_the_interval(self, base_config):
        scheduler = ReviewScheduler(base_config)
        hard = scheduler.review(rating=2, review_count=0)
        easy = scheduler.review(rating=4, review_count=0)
        assert easy.interval_days >= hard.interval_days

    def test_intervals_are_not_hardcoded(self, base_config):
        """Section 13.5: LEAP must not hardcode 1/3/7 day steps."""
        scheduler = ReviewScheduler(base_config)
        intervals = {
            scheduler.review(
                rating=r,
                stability=5.0,
                difficulty=5.0,
                due_at=1_700_000_000,
                last_review_at=1_699_000_000,
                review_count=3,
            ).interval_days
            for r in (1, 2, 3, 4)
        }
        assert len(intervals) > 1

    def test_is_due(self):
        assert ReviewScheduler.is_due(1, now=1_000) is True
        assert ReviewScheduler.is_due(2_000, now=1_000) is False
        assert ReviewScheduler.is_due(None) is False

    def test_retrievability_is_none_without_history(self, base_config):
        assert ReviewScheduler(base_config).retrievability(stability=None, last_review_at=None) is None
