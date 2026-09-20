"""Shared pytest fixtures for the LEAP test suite."""

from __future__ import annotations

import pytest

from leap.config import Config, load_config
from leap.tools import LeapService, build_service


@pytest.fixture(scope="session")
def base_config() -> Config:
    return load_config()


@pytest.fixture
def service() -> LeapService:
    """A fully isolated in-memory runtime."""
    svc = build_service(":memory:")
    yield svc
    svc.close()


@pytest.fixture
def grounded_service(service: LeapService) -> LeapService:
    """A service with one session that already passed Domain Grounding."""
    session = service.create_session("learner-test", "python recursion")
    service.save_benchmark_report(
        session["session_id"],
        "# Baseline\n\nRecursion = base case + recursive case.",
        source_refs=[{"source": "textbook ch.4", "source_type": "textbook", "authority": "high"}],
    )
    return service


@pytest.fixture
def session_id(grounded_service: LeapService) -> str:
    return grounded_service.find_session("learner-test")["sessions"][0]["session_id"]


@pytest.fixture
def dag(grounded_service: LeapService, session_id: str) -> str:
    """A three-node linear prerequisite chain inside one teaching unit."""
    grounded_service.save_knowledge_nodes(
        session_id,
        [
            {"node_id": "n1", "title": "call stack", "bloom_level": "understand", "unit_tag": "u1"},
            {"node_id": "n2", "title": "base case", "bloom_level": "apply", "unit_tag": "u1"},
            {"node_id": "n3", "title": "recursive case", "bloom_level": "apply", "unit_tag": "u1"},
        ],
    )
    grounded_service.save_knowledge_edges(
        session_id,
        [
            {"edge_id": "e1", "pre_node_id": "n1", "post_node_id": "n2",
             "relation_type": "prerequisite"},
            {"edge_id": "e2", "pre_node_id": "n2", "post_node_id": "n3",
             "relation_type": "prerequisite"},
        ],
    )
    return session_id


def answer_and_assess(
    service: LeapService,
    session_id: str,
    node_id: str,
    *,
    hint_level: int = 0,
    correctness: float = 1.0,
    reasoning_quality: float = 0.9,
    answer: str = "a worked answer",
) -> dict:
    """Submit an attempt and commit its assessment in one step."""
    attempt = service.submit_attempt(
        session_id, answer, node_id=node_id, hint_level=hint_level, response_time=30.0
    )
    return service.commit_assessment(
        attempt["attempt_id"],
        answer,
        correctness=correctness,
        conceptual_understanding=correctness,
        reasoning_quality=reasoning_quality,
        application=correctness,
        hint_dependency=min(1.0, hint_level / 3),
    )
