"""Knowledge DAG validation tests (section 6.4 / 22.3).

An invalid graph must be rejected at commit time - never stored and fixed
later. ``save_knowledge_edges`` therefore validates the *combined* graph.
"""

from __future__ import annotations

import pytest

from leap.tools import ToolError


class TestDagValidation:
    def test_valid_chain_is_accepted(self, grounded_service, dag):
        report = grounded_service.validate_knowledge_dag(dag)
        assert report["valid"] is True
        assert report["node_count"] == 3
        assert report["edge_count"] == 2
        assert report["errors"] == []

    def test_cycle_is_rejected_and_not_persisted(self, grounded_service, dag):
        before = grounded_service.get_knowledge_edges(dag)["count"]
        with pytest.raises(ToolError) as exc:
            grounded_service.save_knowledge_edges(
                dag,
                [{"edge_id": "e_cycle", "pre_node_id": "n3", "post_node_id": "n1",
                  "relation_type": "prerequisite"}],
            )
        assert exc.value.code == "invalid_knowledge_dag"
        assert any(e["code"] == "illegal_cycle" for e in exc.value.details["errors"])
        assert grounded_service.get_knowledge_edges(dag)["count"] == before

    def test_dangling_target_is_rejected(self, grounded_service, dag):
        with pytest.raises(ToolError) as exc:
            grounded_service.save_knowledge_edges(
                dag,
                [{"edge_id": "e_bad", "pre_node_id": "n1", "post_node_id": "ghost",
                  "relation_type": "support"}],
            )
        assert any(e["code"] == "dangling_edge_target" for e in exc.value.details["errors"])

    def test_dangling_source_is_rejected(self, grounded_service, dag):
        with pytest.raises(ToolError) as exc:
            grounded_service.save_knowledge_edges(
                dag,
                [{"edge_id": "e_bad2", "pre_node_id": "ghost", "post_node_id": "n1",
                  "relation_type": "support"}],
            )
        assert any(e["code"] == "dangling_edge_source" for e in exc.value.details["errors"])

    def test_self_loop_is_rejected(self, grounded_service, dag):
        with pytest.raises(ToolError) as exc:
            grounded_service.save_knowledge_edges(
                dag,
                [{"edge_id": "e_self", "pre_node_id": "n1", "post_node_id": "n1",
                  "relation_type": "prerequisite"}],
            )
        assert any(e["code"] == "self_loop" for e in exc.value.details["errors"])

    def test_related_cycles_are_not_treated_as_illegal(self, grounded_service, dag):
        """Only prerequisite/extension express a hard directed dependency."""
        result = grounded_service.save_knowledge_edges(
            dag,
            [
                {"edge_id": "r1", "pre_node_id": "n1", "post_node_id": "n3",
                 "relation_type": "related"},
                {"edge_id": "r2", "pre_node_id": "n3", "post_node_id": "n1",
                 "relation_type": "related"},
            ],
        )
        assert result["validation"]["valid"] is True

    def test_invalid_relation_type_is_rejected(self, grounded_service, dag):
        with pytest.raises(ToolError) as exc:
            grounded_service.save_knowledge_edges(
                dag,
                [{"edge_id": "e_x", "pre_node_id": "n1", "post_node_id": "n2",
                  "relation_type": "depends_on"}],
            )
        assert exc.value.code == "invalid_relation_type"

    def test_isolated_node_produces_a_warning_not_an_error(self, grounded_service, dag):
        grounded_service.save_knowledge_nodes(
            dag, [{"node_id": "n9", "title": "orphan", "bloom_level": "understand"}]
        )
        report = grounded_service.validate_knowledge_dag(dag)
        assert report["valid"] is True
        assert any(w["code"] == "isolated_nodes" for w in report["warnings"])


class TestNodePersistence:
    def test_duplicate_ids_in_one_payload_are_rejected(self, grounded_service, session_id):
        with pytest.raises(ToolError) as exc:
            grounded_service.save_knowledge_nodes(
                session_id,
                [{"node_id": "dup", "title": "a"}, {"node_id": "dup", "title": "b"}],
            )
        assert exc.value.code == "duplicate_node_id"

    def test_resaving_a_node_updates_it(self, grounded_service, dag):
        grounded_service.save_knowledge_nodes(
            dag, [{"node_id": "n1", "title": "renamed", "bloom_level": "apply"}]
        )
        nodes = {n["node_id"]: n for n in grounded_service.get_knowledge_nodes(dag)["nodes"]}
        assert nodes["n1"]["title"] == "renamed"
        assert grounded_service.get_knowledge_nodes(dag)["count"] == 3

    def test_unit_concept_budget_is_enforced(self, grounded_service, session_id):
        service = grounded_service
        budget = int(service.conf("unit_concept_budget", 8))
        with pytest.raises(ToolError) as exc:
            service.save_knowledge_nodes(
                session_id,
                [
                    {"node_id": f"b{i}", "title": f"node {i}", "unit_tag": "big"}
                    for i in range(budget + 1)
                ],
            )
        assert exc.value.code == "unit_budget_exceeded"

    def test_decompose_topic_returns_a_template_only(self, grounded_service, session_id):
        result = grounded_service.decompose_topic(session_id, "recursion")
        assert result["ok"] is True
        assert "node_field_template" in result
        # The runtime must not invent node content itself.
        assert "nodes" not in result
        assert grounded_service.get_knowledge_nodes(session_id)["count"] == 0
