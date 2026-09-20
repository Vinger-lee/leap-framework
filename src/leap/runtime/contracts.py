"""Pluggable interfaces (LEAP-Framework-V2 section 35).

Section 35 promises that six components can be swapped without touching the
rest of the system::

    35.1 State Estimation   BKT -> Forgetting-aware BKT -> PFA -> DKT -> Bayesian -> Hybrid
    35.2 Assessment         Rule -> Rubric -> LLM -> Hybrid -> Human-in-the-loop
    35.3 Pedagogical Policy Rule -> LLM -> Hybrid -> Learned
    35.4 Review Scheduler   FSRS -> Other Scheduler
    35.5 Storage            SQLite -> PostgreSQL -> Distributed
    35.6 Artifact Storage   Local -> Object Storage -> Knowledge Base

These protocols are what makes that promise real. Each one describes the
*minimum* surface the runtime depends on, so a replacement only has to satisfy
the protocol - it never has to subclass a concrete implementation.

Section 10.2 states the same requirement for state estimation specifically:
"LEAP 的 State Estimation 是一个接口层，具体模型可以替换."
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Iterable, Mapping, Protocol, Sequence, runtime_checkable

__all__ = [
    "MasteryEstimator",
    "ScoreAggregator",
    "PolicyStrategy",
    "ReviewSchedulerBackend",
    "StorageBackend",
    "ArtifactStore",
]


# ---------------------------------------------------------------------------
# 35.1 State Estimation
# ---------------------------------------------------------------------------
@runtime_checkable
class MasteryEstimator(Protocol):
    """Estimates ``mastery_probability`` from assessment evidence.

    P0 ships ``BKTEstimator`` (simplified, forgetting-aware). P1 may register
    PFA / DKT / an external estimator behind the same surface.
    """

    def initial(self) -> float:
        """Prior mastery for a node with no evidence yet."""
        ...

    def update(
        self,
        prior: float | None,
        *,
        correct: bool | None = None,
        score: float | None = None,
        elapsed_days: float = 0.0,
    ) -> float:
        """Return the updated mastery estimate."""
        ...

    def confidence_weighted(
        self,
        prior: float | None,
        *,
        score: float,
        assessor_confidence: float = 1.0,
        elapsed_days: float = 0.0,
    ) -> float:
        """Update while discounting low-confidence assessments (section 29.2)."""
        ...


# ---------------------------------------------------------------------------
# 35.2 Assessment aggregation
# ---------------------------------------------------------------------------
@runtime_checkable
class ScoreAggregator(Protocol):
    """Collapses multi-dimensional scores into ``overall_score``.

    P0 uses the weighted mean of section 10.3-1. A rubric-based or learned
    aggregator can be registered instead.
    """

    def aggregate(self, scores: Mapping[str, float | None]) -> float | None:
        """Return the aggregate, or ``None`` when nothing was judged."""
        ...


# ---------------------------------------------------------------------------
# 35.3 Pedagogical Policy
# ---------------------------------------------------------------------------
@runtime_checkable
class PolicyStrategy(Protocol):
    """Chooses the next teaching strategy and action.

    P0 ships a rule-based engine. The rung above it on the ladder is an LLM
    policy, then a hybrid, then a learned policy - all behind this surface.
    """

    def evaluate(
        self,
        session_id: str,
        node_id: str | None = None,
        *,
        trigger_event: str | None = None,
        guard_checks: list[dict] | None = None,
    ) -> Any:
        """Return a decision object exposing ``as_dict()``."""
        ...


# ---------------------------------------------------------------------------
# 35.4 Review Scheduler
# ---------------------------------------------------------------------------
@runtime_checkable
class ReviewSchedulerBackend(Protocol):
    """Spaced-repetition scheduling.

    P0 ships ``ReviewScheduler`` on top of ``py-fsrs``.
    """

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
    ) -> Any:
        """Apply one 1-4 rating and return the new scheduling state."""
        ...

    def retrievability(
        self,
        *,
        stability: float | None,
        last_review_at: int | None,
        now: int | None = None,
    ) -> float | None:
        """Probability of recall right now."""
        ...

    def is_due(self, next_review_at: int | None, now: int | None = None) -> bool:
        """Whether a review item is due."""
        ...


# ---------------------------------------------------------------------------
# 35.5 Storage
# ---------------------------------------------------------------------------
@runtime_checkable
class StorageBackend(Protocol):
    """Persistence surface used by the runtime.

    P0 ships SQLite. PostgreSQL and distributed stores implement the same
    methods; nothing above this layer knows which one is in use.
    """

    def initialize(self) -> "StorageBackend": ...

    def close(self) -> None: ...

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any: ...

    def executemany(self, sql: str, seq: Sequence[Sequence[Any]]) -> Any: ...

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[Any]: ...

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> Any | None: ...

    def scalar(self, sql: str, params: Sequence[Any] = (), default: Any = None) -> Any: ...

    def transaction(self) -> AbstractContextManager[Any]: ...

    def table_names(self) -> list[str]: ...


# ---------------------------------------------------------------------------
# 35.6 Artifact storage
# ---------------------------------------------------------------------------
@runtime_checkable
class ArtifactStore(Protocol):
    """Where learner artefacts live.

    P0 keeps them in the local SQLite ``artifacts`` table. Object storage and
    knowledge bases implement the same two methods.
    """

    def save(
        self,
        *,
        artifact_id: str,
        learner_id: str | None,
        session_id: str | None,
        artifact_type: str,
        path_or_uri: str | None = None,
        content: str | None = None,
        metadata: Any = None,
        version: str = "1",
    ) -> str:
        """Persist an artefact and return its id."""
        ...

    def load(self, artifact_id: str) -> Mapping[str, Any] | None:
        """Fetch an artefact by id, or ``None`` when absent."""
        ...

    def list_for_session(
        self, session_id: str, artifact_type: str | None = None
    ) -> Iterable[Mapping[str, Any]]:
        """List artefacts belonging to a session."""
        ...
