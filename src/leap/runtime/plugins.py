"""Implementation registry for the pluggable seams of section 35.

Every swappable component is registered under a *kind* and a *name*. The
runtime never imports a concrete implementation directly - it asks the
registry for whatever ``config/default.yaml`` selected::

    mastery_estimator: simplified_bkt
    score_aggregator:  weighted
    policy_engine:     rule_based
    review_scheduler:  py-fsrs
    storage_backend:   sqlite
    artifact_store:    local

Adding an alternative (PFA, DKT, PostgreSQL, object storage) is a matter of
registering a factory under a new name; no call site changes.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

__all__ = [
    "PluginRegistry",
    "registry",
    "register_builtins",
    "KIND_MASTERY_ESTIMATOR",
    "KIND_SCORE_AGGREGATOR",
    "KIND_POLICY_ENGINE",
    "KIND_REVIEW_SCHEDULER",
    "KIND_STORAGE_BACKEND",
    "KIND_ARTIFACT_STORE",
    "KINDS",
]

KIND_MASTERY_ESTIMATOR = "mastery_estimator"
KIND_SCORE_AGGREGATOR = "score_aggregator"
KIND_POLICY_ENGINE = "policy_engine"
KIND_REVIEW_SCHEDULER = "review_scheduler"
KIND_STORAGE_BACKEND = "storage_backend"
KIND_ARTIFACT_STORE = "artifact_store"

KINDS: tuple[str, ...] = (
    KIND_MASTERY_ESTIMATOR,
    KIND_SCORE_AGGREGATOR,
    KIND_POLICY_ENGINE,
    KIND_REVIEW_SCHEDULER,
    KIND_STORAGE_BACKEND,
    KIND_ARTIFACT_STORE,
)


class PluginRegistry:
    """A tiny name -> factory registry.

    Deliberately not a general-purpose DI container: it exists to make the six
    section-35 seams addressable by configuration.
    """

    def __init__(self) -> None:
        self._factories: dict[str, dict[str, Callable[..., Any]]] = {k: {} for k in KINDS}

    # -- registration ------------------------------------------------------
    def register(self, kind: str, name: str, factory: Callable[..., Any]) -> None:
        if kind not in self._factories:
            raise KeyError(f"unknown plugin kind: {kind!r}; expected one of {KINDS}")
        self._factories[kind][name] = factory

    def unregister(self, kind: str, name: str) -> None:
        self._factories.get(kind, {}).pop(name, None)

    # -- lookup ------------------------------------------------------------
    def has(self, kind: str, name: str) -> bool:
        return name in self._factories.get(kind, {})

    def available(self, kind: str) -> list[str]:
        return sorted(self._factories.get(kind, {}))

    def create(self, kind: str, name: str, *args: Any, **kwargs: Any) -> Any:
        """Instantiate a registered implementation."""
        factory = self._factories.get(kind, {}).get(name)
        if factory is None:
            raise KeyError(
                f"no implementation registered for {kind}={name!r}; "
                f"available: {self.available(kind) or '(none)'}"
            )
        return factory(*args, **kwargs)

    def describe(self) -> dict[str, list[str]]:
        return {kind: self.available(kind) for kind in KINDS}

    # -- test support ------------------------------------------------------
    def snapshot(self) -> dict[str, dict[str, Callable[..., Any]]]:
        return {kind: dict(factories) for kind, factories in self._factories.items()}

    def restore(self, snapshot: dict[str, dict[str, Callable[..., Any]]]) -> None:
        self._factories = {kind: dict(factories) for kind, factories in snapshot.items()}


#: Process-wide registry used by the runtime.
registry = PluginRegistry()

_builtins_registered = False


def register_builtins(*, force: bool = False) -> PluginRegistry:
    """Register the P0 implementations. Idempotent unless ``force=True``."""
    global _builtins_registered
    if _builtins_registered and not force:
        return registry

    from leap.runtime.bkt import BKTEstimator, BKTParams
    from leap.runtime.policy import PolicyEngine
    from leap.runtime.scheduler import ReviewScheduler
    from leap.runtime.scoring import WeightedScoreAggregator
    from leap.storage.artifacts import LocalArtifactStore
    from leap.storage.database import Database

    # 35.1 State estimation
    registry.register(
        KIND_MASTERY_ESTIMATOR,
        "simplified_bkt",
        lambda cfg=None, **_: BKTEstimator(BKTParams.from_config(cfg) if cfg is not None else None),
    )

    # 35.2 Assessment aggregation
    registry.register(
        KIND_SCORE_AGGREGATOR,
        "weighted",
        lambda cfg=None, **_: WeightedScoreAggregator(
            (cfg.get("overall_score_weights", {}) if cfg is not None else None)
        ),
    )

    # 35.3 Pedagogical policy
    registry.register(
        KIND_POLICY_ENGINE,
        "rule_based",
        lambda db, cfg, events=None, **_: PolicyEngine(db, cfg, events),
    )

    # 35.4 Review scheduler
    registry.register(
        KIND_REVIEW_SCHEDULER,
        "py-fsrs",
        lambda cfg=None, **_: ReviewScheduler(cfg),
    )

    # 35.5 Storage
    registry.register(
        KIND_STORAGE_BACKEND,
        "sqlite",
        lambda path=":memory:", **_: Database(path),
    )

    # 35.6 Artifact storage
    registry.register(
        KIND_ARTIFACT_STORE,
        "local",
        lambda db, **_: LocalArtifactStore(db),
    )

    _builtins_registered = True
    return registry


def create_from_config(kind: str, cfg: Any, *args: Any, default: str, **kwargs: Any) -> Any:
    """Instantiate the implementation named by ``cfg`` for ``kind``.

    Falls back to ``default`` when the configuration omits the key, so adding a
    new seam does not break existing config files.
    """
    register_builtins()
    name = str(cfg.get(kind, default)) if hasattr(cfg, "get") else default
    return registry.create(kind, name, *args, cfg=cfg, **kwargs)


def describe_plugins() -> dict[str, list[str]]:
    register_builtins()
    return registry.describe()


def iter_kinds() -> Iterable[str]:
    return KINDS
