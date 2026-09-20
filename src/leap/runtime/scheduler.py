"""Review scheduling on top of ``py-fsrs`` (section 13).

Positioning (section 13.2): FSRS is a *review scheduling algorithm*, not the
whole learner-state model. Knowledge nodes and review items are therefore
separate tables - one node may own several review cards at different
granularities.

All boundaries of this module speak Unix seconds. ``datetime`` conversion
happens here and nowhere else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fsrs import Card, Rating, Scheduler, State

__all__ = ["ReviewOutcome", "ReviewScheduler", "RATING_NAMES", "rating_from_int"]

#: FSRS standard 1-4 scale (section 13.5). LEAP does not invent its own scale.
RATING_NAMES: dict[int, str] = {1: "again", 2: "hard", 3: "good", 4: "easy"}
_RATING_BY_INT: dict[int, Rating] = {
    1: Rating.Again,
    2: Rating.Hard,
    3: Rating.Good,
    4: Rating.Easy,
}


def rating_from_int(value: int) -> Rating:
    try:
        return _RATING_BY_INT[int(value)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"rating must be an integer in 1..4, got {value!r}") from exc


def _to_dt(unix_seconds: int | float | None) -> datetime | None:
    if unix_seconds is None:
        return None
    return datetime.fromtimestamp(float(unix_seconds), tz=timezone.utc)


def _to_ts(moment: datetime | None) -> int | None:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp())


@dataclass(frozen=True)
class ReviewOutcome:
    """Result of feeding one review rating back into the scheduler."""

    stability: float
    difficulty: float
    due_at: int
    last_review_at: int
    interval_days: float
    retrievability: float | None
    rating: int
    scheduler_version: str

    def as_dict(self) -> dict:
        return {
            "stability": self.stability,
            "difficulty": self.difficulty,
            "due_at": self.due_at,
            "last_review_at": self.last_review_at,
            "interval_days": self.interval_days,
            "retrievability": self.retrievability,
            "rating": self.rating,
            "rating_name": RATING_NAMES.get(self.rating, "unknown"),
            "scheduler_version": self.scheduler_version,
        }


class ReviewScheduler:
    """Thin, LEAP-shaped wrapper around :class:`fsrs.Scheduler`.

    LEAP never hardcodes 1/3/7-day intervals (section 13.5); intervals are
    always produced by the scheduler from the card's memory state.
    """

    def __init__(self, cfg: Any = None) -> None:
        get = cfg.get if cfg is not None and hasattr(cfg, "get") else (lambda _k, d=None: d)
        desired_retention = float(get("fsrs.desired_retention", 0.90))
        maximum_interval = int(get("fsrs.maximum_interval_days", 365))
        self.version = str(get("fsrs.scheduler_version", "fsrs-6"))

        # Learning steps are expressed as timedeltas. LEAP defaults suit a
        # tutoring session rather than flashcard drilling, and are configurable.
        self._scheduler = Scheduler(
            desired_retention=desired_retention,
            maximum_interval=maximum_interval,
            learning_steps=(timedelta(minutes=10), timedelta(days=1)),
            relearning_steps=(timedelta(minutes=10),),
        )

    # -- state reconstruction ---------------------------------------------
    @staticmethod
    def _card(
        *,
        stability: float | None,
        difficulty: float | None,
        due_at: int | None,
        last_review_at: int | None,
        review_count: int,
    ) -> Card:
        # A card that has never been reviewed is still in the learning phase.
        state = State.Learning if not review_count else State.Review
        return Card(
            state=state,
            step=0,
            stability=stability,
            difficulty=difficulty,
            due=_to_dt(due_at) or datetime.now(timezone.utc),
            last_review=_to_dt(last_review_at),
        )

    # -- public API --------------------------------------------------------
    def review(
        self,
        *,
        rating: int,
        stability: float | None = None,
        difficulty: float | None = None,
        due_at: int | None = None,
        last_review_at: int | None = None,
        review_count: int = 0,
        now: int | None = None,
    ) -> ReviewOutcome:
        """Apply one rating and return the new scheduling state."""
        now_dt = _to_dt(now) or datetime.now(timezone.utc)
        card = self._card(
            stability=stability,
            difficulty=difficulty,
            due_at=due_at,
            last_review_at=last_review_at,
            review_count=review_count,
        )
        updated, _log = self._scheduler.review_card(
            card, rating_from_int(rating), review_datetime=now_dt
        )

        due_ts = _to_ts(updated.due) or int(now_dt.timestamp())
        last_ts = _to_ts(updated.last_review) or int(now_dt.timestamp())
        interval_days = max(0.0, (due_ts - last_ts) / 86400.0)

        return ReviewOutcome(
            stability=float(updated.stability or 0.0),
            difficulty=float(updated.difficulty or 0.0),
            due_at=due_ts,
            last_review_at=last_ts,
            interval_days=interval_days,
            retrievability=self.retrievability(
                stability=updated.stability, last_review_at=last_ts, now=now
            ),
            rating=int(rating),
            scheduler_version=self.version,
        )

    def retrievability(
        self,
        *,
        stability: float | None,
        last_review_at: int | None,
        now: int | None = None,
    ) -> float | None:
        """Probability of recall right now, per the FSRS forgetting curve."""
        if not stability or not last_review_at:
            return None
        card = Card(
            state=State.Review,
            stability=float(stability),
            due=_to_dt(last_review_at),
            last_review=_to_dt(last_review_at),
        )
        try:
            return float(
                self._scheduler.get_card_retrievability(
                    card, current_datetime=_to_dt(now) or datetime.now(timezone.utc)
                )
            )
        except Exception:  # pragma: no cover - defensive, library edge cases
            return None

    @staticmethod
    def is_due(next_review_at: int | None, now: int | None = None) -> bool:
        if next_review_at is None:
            return False
        reference = now if now is not None else int(datetime.now(timezone.utc).timestamp())
        return next_review_at <= reference
