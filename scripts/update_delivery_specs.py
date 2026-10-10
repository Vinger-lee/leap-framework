"""Synchronize machine-readable projections of the permanent delivery policy."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "src/leap/specs"


def update() -> None:
    policy = json.loads((SPECS / "teaching_delivery_policy.json").read_text(encoding="utf-8"))
    web = json.loads((SPECS / "web_component_spec.json").read_text(encoding="utf-8"))
    web["delivery_policy_version"] = policy["version"]
    web["teaching_depth"] = policy["depth"]
    web["visualization"] = policy["visualization"]
    web["layout"] = policy["layout"]
    web["learning_resources"] = policy["learning_resources"]
    web["canonical_source"] = policy["markdown"]
    web["registration"] = {"tool": "save_teaching_package", "before": "save_assessment_item", "bodies_required": ["markdown", "html"], "semantic_truth_verified": False}
    web["design_tokens"]["layout"] = policy["layout"]
    web.setdefault("content_quality", {})["teaching_policy"] = policy["policy_id"]
    (SPECS / "web_component_spec.json").write_text(json.dumps(web, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    obs = json.loads((SPECS / "obsidian_structure.json").read_text(encoding="utf-8"))
    obs["delivery_policy_version"] = policy["version"]
    obs["role"] = "complete canonical human knowledge source, more detailed than HTML"
    obs["learning_resources"] = policy["learning_resources"]
    obs["markdown_requirements"] = policy["markdown"]
    obs["linking_rules"] = [
        "Use resolvable vault-root [[wikilinks]]; add reciprocal links on target notes or their real backlink indexes.",
        "Connect prerequisites, successor concepts, misconceptions, worked examples, exercises and source notes.",
        "State is a timestamped Runtime snapshot, never local evidence authority.",
        "Markdown contains all projected teaching prose plus extended derivations, assumptions, comparisons and extra cases.",
        "No verified video: insert topic-specific core/extension/advanced search queries at the top.",
    ]
    lesson = """---
title: <specific skill>
tags: [leap, <subject>, lesson]
aliases: [<descriptive alias>]
node_id: <runtime node id>
unit_tag: <runtime unit tag>
state_kind: runtime_snapshot
updated_at: <Unix seconds>
---

# <specific skill>

> [!info] Learning resources
> Verified video records only after accessibility and topical content checks.
> Otherwise core: <topic + operation + beginner>; extension: <conditions + comparison>; advanced: <proof + transfer>.

Related: [[01_Knowledge/Knowledge_Map]] · [[01_Knowledge/Nodes/<prerequisite>]]

## Prerequisite refresher and symbol glossary

Explain every prerequisite operation and check it with a short example.

## Principle, assumptions and mechanism

State precisely what is true, when it is true, and why it works.

## Labeled diagram and controllable walkthrough

Include a structure/process Mermaid diagram and a corresponding step trace or parameter view in HTML.

## Complete worked example

1. State exact inputs, units and domain constraints.
2. Show each operation and its reason, preserving intermediate results.
3. Check the final result independently and against boundary cases.

## Misconceptions, boundaries and contrasting cases

Show an incorrect method, explain the failure, repair it, and compare a valid nearby case.

## Graduated practice and full solutions

Basic, variation and challenge tasks each include conditions, full derivation and error analysis.

## Transfer and delayed review

Change parameters or context. Require a fresh learner answer; answer reveal is not evidence of mastery.

> [!example]- Extended derivation beyond the HTML projection
> Include additional original reasoning, annotated steps, alternate methods, counterexamples and extra practice here.

## Sources, limitations and projection coverage

Record actual source URL, locator, excerpt, date and checks; do not imply syllabus alignment from general sources.
Map each HTML teaching section to a full note section. Register both bodies through save_teaching_package.

## Backlinks and next concepts

[[01_Knowledge/Knowledge_Map]] · [[02_Lessons/<successor>]]
"""
    obs["templates"]["knowledge_node"] = lesson
    obs["templates"]["lesson"] = lesson
    obs["templates"]["knowledge_map"] = "---\ntitle: Knowledge map\ntags: [leap, index]\naliases: [Knowledge index]\n---\n\n# Knowledge map\n\n> [!info] Learning resources\n> Core: prerequisite graph learning path; extension: concept relations; advanced: transfer design.\n\nLink every node and its canonical lesson with reciprocal [[wikilinks]]. Draw prerequisite Mermaid edges; distinguish learning order from evidence stage.\n"
    obs["templates"]["goal"] = "---\ntitle: Learning goal\ntags: [leap, goal]\naliases: [Session objective]\n---\n\n# Learning goal\n\n> [!info] Learning resources\n> Core: <specific topic beginner>; extension: <topic conditions>; advanced: <topic transfer>.\n\nDefine observable outcome, prerequisites, constraints and assessment. Link [[01_Knowledge/Knowledge_Map]] and the canonical [[02_Lessons/Unit_001/lesson]].\n"
    for kind, title, purpose in [
        ("profile", "Learner profile", "Record the learner's stated goals, accessibility preferences, prior experience and constraints. Distinguish self-report from assessed evidence."),
        ("session_config", "Session configuration", "Record actual session id, locale, unit boundaries, Runtime version and policy version. Explain why the selected sequence meets the goal."),
        ("knowledge_edge", "Prerequisite relation", "Link both source and target notes, explain the exact prerequisite operation, give a failure example without it and a short readiness check. Do not conflate conceptual relations with prerequisite edges."),
    ]:
        obs["templates"][kind] = f"---\ntitle: {title}\ntags: [leap, {kind}]\naliases: [{title} note]\n---\n\n# {title}\n\n> [!info] Learning resources\n> Core: <topic-specific prerequisite>; extension: <learning conditions>; advanced: <transfer evidence>.\n\n{purpose}\n\nRelated: [[01_Knowledge/Knowledge_Map]] · [[00_System/learning_goal]]\n\n> [!note]- Interpretation and limitations\n> Include exact observations, assumptions, timestamp and unresolved questions; only Runtime receipts authorize learner-state claims.\n"
    (SPECS / "obsidian_structure.json").write_text(json.dumps(obs, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    schema = json.loads((SPECS / "interaction_output.schema.json").read_text(encoding="utf-8"))
    schema["properties"]["subject"]["enum"] = ["programming", "math", "computer-science", "physics", "logic", "statistics", "chemistry", "electronics", "biology", "economics", "language"]
    schema["properties"]["ui_state"]["properties"]["local_activity_completed"] = {"type": "boolean", "description": "Local exercise action ended; never equals authoritative Runtime unit completion."}
    schema["properties"]["ui_state"]["properties"]["completed"]["description"] = "True only when an explicit successful Runtime advance/complete receipt confirms completion; local answer reveal or correctness cannot set it."
    schema["properties"]["ui_state"]["properties"]["mode"]["description"] = "demo: offline collection; hosted: a Runtime context snapshot was loaded, not evidence of a persistent connection"
    schema["properties"]["ui_state"]["properties"]["hint_dependency"]["type"] = ["number", "null"]
    for name in ("correctness", "conceptual_understanding", "reasoning_quality", "application", "transfer", "hint_dependency", "confidence", "overall_score"):
        schema["properties"]["assessment"]["properties"][name]["type"] = ["number", "null"]
    schema["properties"]["assessment"]["properties"]["provisional"]["description"] = "Feedback has no corresponding successful Runtime assessment receipt. It never grants authority to change mastery, evidence stage or completion."
    tools = schema["properties"]["outbox"]["items"]["properties"]["tool"]["enum"]
    if "advance_unit" not in tools:
        tools.append("advance_unit")
    serialized = json.dumps(schema, ensure_ascii=False, indent=2)+"\n"
    (SPECS / "interaction_output.schema.json").write_text(serialized, encoding="utf-8")
    (ROOT / "examples/_shared/interaction-output.schema.json").write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    update()
