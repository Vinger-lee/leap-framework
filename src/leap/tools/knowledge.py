"""Knowledge representation tools (section 22.3) and DAG validation (6.4).

LEAP never authors knowledge nodes itself. ``decompose_topic`` returns a
*structure template*; the host agent's LLM fills in the content and calls
``save_knowledge_nodes`` / ``save_knowledge_edges``. Before anything is
committed the runtime **forces** a DAG validation - an invalid graph is
rejected, never silently stored.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from leap.storage import new_id, now_ts
from leap.tools.base import LeapToolMixin, ToolError

__all__ = ["KnowledgeTools", "RELATION_TYPES"]

RELATION_TYPES: tuple[str, ...] = ("prerequisite", "support", "extension", "related")

#: Relations that express a hard, directed dependency. Cycles here are illegal.
_DEPENDENCY_RELATIONS = frozenset({"prerequisite", "extension"})

#: Suggested node fields the host agent should populate.
NODE_FIELD_TEMPLATE: dict[str, str] = {
    "node_id": "stable unique id, e.g. 'py.recursion.base_case'",
    "title": "short human-readable title",
    "description": "what this node covers",
    "domain": "subject or skill area",
    "learning_objective": "what the learner will be able to DO after mastering it",
    "bloom_level": "remember | understand | apply | analyze | evaluate | create",
    "difficulty": "0.0 - 1.0",
    "estimated_duration": "minutes",
    "required_evidence": "what evidence proves this node reached its objective",
    "assessment_requirements": "which assessment types are needed",
    "transfer_requirements": "required | none | (omit for the conditional default)",
    "unit_tag": "teaching unit this node belongs to",
}


class KnowledgeTools(LeapToolMixin):
    """Topic decomposition, node/edge persistence and DAG validation."""

    # ------------------------------------------------------------------
    # 22.3 Knowledge
    # ------------------------------------------------------------------
    def decompose_topic(self, session_id: str, topic: str | None = None) -> dict:
        """Return a DAG template. **No node content is generated here.**"""
        session = self.require_session(session_id)
        topic = topic or session.get("topic")
        budget = int(self.conf("unit_concept_budget", 8))

        return self.ok(
            session_id=session_id,
            topic=topic,
            unit_concept_budget=budget,
            node_field_template=NODE_FIELD_TEMPLATE,
            relation_types=list(RELATION_TYPES),
            relation_semantics={
                "prerequisite": "the later node depends on the earlier one for teaching order",
                "support": "helpful but not a hard prerequisite",
                "extension": "concept grows from basic to advanced",
                "related": "associated, but no mandatory dependency",
            },
            guidance=(
                "Generate nodes and edges with the host agent's LLM, then call "
                "save_knowledge_nodes and save_knowledge_edges. Keep each unit_tag at or "
                f"below {budget} core nodes. The runtime validates the DAG before commit and "
                "rejects invalid graphs."
            ),
        )

    def save_knowledge_nodes(
        self,
        session_id: str,
        nodes: Sequence[Mapping[str, Any]],
        *,
        request_id: str | None = None,
    ) -> dict:
        session = self.require_session(session_id)
        nodes = self.as_list(nodes)
        if not nodes:
            raise ToolError("invalid_argument", "nodes must be a non-empty list")

        seen: set[str] = set()
        unit_counts: dict[str, int] = {}
        prepared: list[tuple] = []
        ts = now_ts()

        for raw in nodes:
            node = dict(raw)
            node_id = self.require_text(node.get("node_id"), "nodes[].node_id")
            if node_id in seen:
                raise ToolError("duplicate_node_id", f"duplicate node_id in payload: {node_id}")
            seen.add(node_id)
            unit_tag = node.get("unit_tag")
            if unit_tag:
                unit_counts[unit_tag] = unit_counts.get(unit_tag, 0) + 1
            prepared.append(
                (
                    node_id, session_id, node.get("title") or node_id, node.get("description"),
                    node.get("domain"), node.get("learning_objective"), node.get("bloom_level"),
                    node.get("difficulty"), node.get("estimated_duration"),
                    self._as_text(node.get("required_evidence")),
                    self._as_text(node.get("assessment_requirements")),
                    self._as_text(node.get("transfer_requirements")),
                    unit_tag, str(node.get("version", "1")), ts, ts,
                )
            )

        budget = int(self.conf("unit_concept_budget", 8))
        oversized = {u: c for u, c in unit_counts.items() if c > budget}
        if oversized:
            raise ToolError(
                "unit_budget_exceeded",
                f"unit(s) exceed unit_concept_budget={budget}: {oversized}",
                {"budget": budget, "counts": unit_counts},
            )

        existing = {
            r["node_id"]
            for r in self.db.query(
                "SELECT node_id FROM knowledge_nodes WHERE session_id = ?", (session_id,)
            )
        }
        with self.db.transaction():
            for row in prepared:
                if row[0] in existing:
                    self.db.execute(
                        "UPDATE knowledge_nodes SET title=?, description=?, domain=?, "
                        "learning_objective=?, bloom_level=?, difficulty=?, estimated_duration=?, "
                        "required_evidence=?, assessment_requirements=?, transfer_requirements=?, "
                        "unit_tag=?, version=?, updated_at=? WHERE node_id=?",
                        (row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10],
                         row[11], row[12], row[13], ts, row[0]),
                    )
                else:
                    self.db.execute(
                        "INSERT INTO knowledge_nodes "
                        "(node_id, session_id, title, description, domain, learning_objective, "
                        " bloom_level, difficulty, estimated_duration, required_evidence, "
                        " assessment_requirements, transfer_requirements, unit_tag, version, "
                        " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        row,
                    )

        self.events.emit(
            "knowledge_dag_saved", session_id=session_id, learner_id=session["learner_id"],
            payload={"nodes": len(prepared)}, request_id=request_id,
        )
        return self.ok(
            session_id=session_id,
            saved=len(prepared),
            created=len(prepared) - len(seen & existing),
            updated=len(seen & existing),
            unit_counts=unit_counts,
        )

    def save_knowledge_edges(
        self,
        session_id: str,
        edges: Sequence[Mapping[str, Any]],
        *,
        request_id: str | None = None,
    ) -> dict:
        """Persist edges - but only after the combined graph validates."""
        session = self.require_session(session_id)
        edges = self.as_list(edges)
        if not edges:
            raise ToolError("invalid_argument", "edges must be a non-empty list")

        prepared: list[tuple] = []
        ts = now_ts()
        for raw in edges:
            edge = dict(raw)
            pre = self.require_text(edge.get("pre_node_id"), "edges[].pre_node_id")
            post = self.require_text(edge.get("post_node_id"), "edges[].post_node_id")
            relation = str(edge.get("relation_type") or "prerequisite")
            if relation not in RELATION_TYPES:
                raise ToolError(
                    "invalid_relation_type",
                    f"relation_type must be one of {RELATION_TYPES}, got {relation!r}",
                )
            prepared.append(
                (edge.get("edge_id") or new_id("edge"), session_id, pre, post, relation,
                 edge.get("weight"), ts)
            )

        # --- forced validation on the *combined* graph ---------------------
        existing_nodes = self.rows(
            "SELECT node_id FROM knowledge_nodes WHERE session_id = ?", (session_id,)
        )
        existing_edges = self.rows(
            "SELECT edge_id, pre_node_id, post_node_id, relation_type FROM knowledge_edges "
            "WHERE session_id = ?",
            (session_id,),
        )
        proposed_nodes = [{"node_id": r["node_id"]} for r in existing_nodes]
        proposed_edges = [
            {"edge_id": r["edge_id"], "pre_node_id": r["pre_node_id"],
             "post_node_id": r["post_node_id"], "relation_type": r["relation_type"]}
            for r in existing_edges
        ] + [
            {"edge_id": p[0], "pre_node_id": p[2], "post_node_id": p[3], "relation_type": p[4]}
            for p in prepared
        ]

        report = self._validate_graph(proposed_nodes, proposed_edges)
        if not report["valid"]:
            self.events.emit(
                "state_guard_rejected", session_id=session_id, learner_id=session["learner_id"],
                payload={"tool": "save_knowledge_edges", "errors": report["errors"]},
                request_id=request_id,
            )
            raise ToolError(
                "invalid_knowledge_dag",
                "knowledge DAG validation failed; edges were not saved",
                report,
            )

        with self.db.transaction():
            for row in prepared:
                self.db.execute(
                    "INSERT INTO knowledge_edges "
                    "(edge_id, session_id, pre_node_id, post_node_id, relation_type, weight, created_at) "
                    "VALUES (?,?,?,?,?,?,?) ON CONFLICT(edge_id) DO NOTHING",
                    row,
                )
            self.db.execute(
                "UPDATE learning_sessions SET updated_at = ? WHERE session_id = ?", (ts, session_id)
            )

        self.events.emit(
            "knowledge_dag_validated", session_id=session_id, learner_id=session["learner_id"],
            payload={"edges": len(prepared), "valid": True}, request_id=request_id,
        )
        return self.ok(session_id=session_id, saved=len(prepared), validation=report)

    def get_knowledge_nodes(self, session_id: str, unit_tag: str | None = None) -> dict:
        self.require_session(session_id)
        if unit_tag:
            rows = self.rows(
                "SELECT * FROM knowledge_nodes WHERE session_id = ? AND unit_tag = ? "
                "ORDER BY node_id",
                (session_id, unit_tag),
            )
        else:
            rows = self.rows(
                "SELECT * FROM knowledge_nodes WHERE session_id = ? ORDER BY node_id",
                (session_id,),
            )
        return self.ok(session_id=session_id, count=len(rows), nodes=rows)

    def get_knowledge_edges(self, session_id: str) -> dict:
        self.require_session(session_id)
        rows = self.rows(
            "SELECT * FROM knowledge_edges WHERE session_id = ? ORDER BY edge_id", (session_id,)
        )
        return self.ok(session_id=session_id, count=len(rows), edges=rows)

    def validate_knowledge_dag(self, session_id: str) -> dict:
        """Validate the persisted DAG and return the full report."""
        session = self.require_session(session_id)
        nodes = self.rows(
            "SELECT node_id FROM knowledge_nodes WHERE session_id = ?", (session_id,)
        )
        edges = self.rows(
            "SELECT edge_id, pre_node_id, post_node_id, relation_type FROM knowledge_edges "
            "WHERE session_id = ?",
            (session_id,),
        )
        report = self._validate_graph(nodes, edges)
        self.events.emit(
            "knowledge_dag_validated", session_id=session_id, learner_id=session["learner_id"],
            payload={"valid": report["valid"], "error_count": len(report["errors"])},
        )
        return self.ok(session_id=session_id, **report)

    # ------------------------------------------------------------------
    # validation engine
    # ------------------------------------------------------------------
    def _validate_graph(
        self, nodes: Iterable[Mapping[str, Any]], edges: Iterable[Mapping[str, Any]]
    ) -> dict:
        node_list = [dict(n) for n in nodes]
        edge_list = [dict(e) for e in edges]

        node_ids: set[str] = set()
        errors: list[dict] = []
        warnings: list[dict] = []

        for node in node_list:
            nid = node.get("node_id")
            if not nid:
                errors.append({"code": "node_missing_id", "detail": str(node)[:120]})
                continue
            if nid in node_ids:
                errors.append({"code": "duplicate_node_id", "node_id": nid})
            node_ids.add(nid)

        adjacency: dict[str, set[str]] = {nid: set() for nid in node_ids}
        seen_edge_keys: set[tuple] = set()

        for edge in edge_list:
            pre = edge.get("pre_node_id")
            post = edge.get("post_node_id")
            relation = edge.get("relation_type") or "prerequisite"
            key = (pre, post, relation)

            if pre not in node_ids:
                errors.append({"code": "dangling_edge_source", "edge_id": edge.get("edge_id"), "missing": pre})
            if post not in node_ids:
                errors.append({"code": "dangling_edge_target", "edge_id": edge.get("edge_id"), "missing": post})
            if pre == post:
                errors.append({"code": "self_loop", "node_id": pre, "edge_id": edge.get("edge_id")})
            if key in seen_edge_keys:
                warnings.append({"code": "duplicate_edge", "edge": list(key)})
            seen_edge_keys.add(key)

            if pre in node_ids and post in node_ids and pre != post and relation in _DEPENDENCY_RELATIONS:
                adjacency[pre].add(post)

        cycles = self._find_cycles(adjacency)
        for cycle in cycles:
            errors.append({"code": "illegal_cycle", "cycle": cycle})

        isolated = sorted(
            nid for nid in node_ids
            if not adjacency.get(nid) and not any(nid in targets for targets in adjacency.values())
        )
        if isolated:
            warnings.append({"code": "isolated_nodes", "node_ids": isolated})

        return {
            "valid": not errors,
            "node_count": len(node_ids),
            "edge_count": len(edge_list),
            "errors": errors,
            "warnings": warnings,
        }

    @staticmethod
    def _find_cycles(adjacency: Mapping[str, set[str]]) -> list[list[str]]:
        """Return elementary cycles in the directed dependency subgraph (DFS)."""
        WHITE, GREY, BLACK = 0, 1, 2
        colour: dict[str, int] = {node: WHITE for node in adjacency}
        stack: list[str] = []
        cycles: list[list[str]] = []
        seen_signatures: set[tuple] = set()

        def visit(node: str) -> None:
            colour[node] = GREY
            stack.append(node)
            for neighbour in sorted(adjacency.get(node, ())):
                if colour.get(neighbour, WHITE) == WHITE:
                    visit(neighbour)
                elif colour.get(neighbour) == GREY:
                    if neighbour in stack:
                        cycle = stack[stack.index(neighbour):] + [neighbour]
                        signature = tuple(sorted(cycle[:-1]))
                        if signature not in seen_signatures:
                            seen_signatures.add(signature)
                            cycles.append(cycle)
            stack.pop()
            colour[node] = BLACK

        for node in sorted(adjacency):
            if colour.get(node) == WHITE:
                visit(node)
        return cycles

    @staticmethod
    def _as_text(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        import json

        return json.dumps(value, ensure_ascii=False)
