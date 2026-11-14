---
title: "LEAP Tutor Implementation Plan"
tags: ["leap", "engineering"]
aliases: ["LEAP Tutor Implementation Plan guide"]
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP Tutor implementation skill contract tests recovery foundations definitions workflow`
> Extension: `LEAP Tutor implementation skill contract tests recovery failure cases examples comparison`
> Advanced: `LEAP Tutor implementation skill contract tests recovery invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]]

# LEAP Tutor Implementation Plan

**Goal:** Implement the repository-skill route in `LEAP_MCP与Agent_Skill架构方案.md`.

**Architecture:** The skill orchestrates existing MCP tools. Runtime keeps all
state, evidence gates, mastery estimation and State Guard decisions. Expose the
existing assessment recovery, misconception resolution and session closure tools
in quickstart. Defer the MCP Skills extension as recommended by the design.

**Tech stack:** Python, pytest, MCP stdio, Markdown and YAML frontmatter.

## Constraints and baseline

- Preserve existing uncommitted delivery-policy and visual-authoring changes.
- Use the local checkout; do not pull into a dirty tree, commit, push or deploy.
- Local HEAD: `58b07a0135f2c9d03333f4f058ddfbac274ba897`.
- Installed MCP SDK: 2.3.0. Initial catalogs: full 70, quickstart 25.
- Baseline: 412 passed, 1 skipped (`python -m pytest -p no:cacheprovider`, using `.venv-dev`).
- Keep existing dynamic visual-generation requirements in MCP instructions.
- Skill metadata tracks LEAP 2.1.0, initially draft pending host validation.

## 1. Tool-profile recovery contract

Files: `src/leap/runtime/profiles.py`, `tests/test_tool_profiles.py`,
`tests/test_skill_mcp.py`.

- [x] Add failing catalog assertions for `commit_assessment`,
  `resolve_misconception`, and `complete_session` in quickstart.
- [x] Exercise both profiles over real MCP stdio: grounding rejection and repair,
  graph rejection and repair, package/item registration, split semantic assessment,
  invalid-score recovery without a second attempt, guard refusal, resumption,
  report failure, close failure and retry.
- [x] Add only those three existing tools to quickstart; retain full unchanged.
- [x] Run `python -m pytest tests/test_tool_profiles.py tests/test_skill_mcp.py -p no:cacheprovider`.

Key behavioral acceptance:

```python
assert "commit_assessment" in quickstart
assert "complete_session" in quickstart
assert recovered["attempt_id"] == failed["error"]["details"]["attempt_id"]
assert attempts_after_recovery == attempts_before_recovery
assert snapshot_after_rejected_advance == snapshot_before_rejected_advance
```

## 2. Repository skill

Files: `.agents/skills/leap-tutor/SKILL.md`, `references/lifecycle.md`,
`references/content-quality.md`, `references/recovery.md`,
`tests/test_skill_contract.py`.

- [x] Add static checks for standard frontmatter, repository-version metadata,
  resolvable references and actual tool schemas/profile availability.
- [x] Write the concise trigger, runtime boundaries and workflow router; load
  lifecycle, authoring and recovery details only when relevant.
- [x] Preserve original answers, independent checks, semantic review, delivery
  policy requirements and separate report/close receipts.
- [x] Run the skill validator and `python -m pytest tests/test_skill_contract.py -p no:cacheprovider`.

## 3. Instructions, documentation and acceptance

Files: `src/leap/server.py`, `docs/INTEGRATION.md`, `docs/INTEGRATION_CN.md`,
`docs/FACADE.md`, `docs/FACADE_CN.md`, `docs/content-quality.md`,
`docs/mcp-tools.md`, `docs/agent-skill.md`, `README.md`, `README_CN.md`, `CHANGELOG.md`.

- [x] Retain core server boundaries and dynamic generation policy; route detailed
  workflow to the optional skill with integration-guide fallback.
- [x] Document quickstart additions, separate report/close contracts, hidden
  fine-grained/page-bridge limitations, draft status and rollback.
- [x] Regenerate reference with `python scripts/generate_tool_reference.py`.
- [x] Record E2E-01 through E2E-14: distinguish runtime test evidence from host
  discovery/activation, semantic quality and token measurements requiring a fresh
  host run. Do not invent host activation or performance data.
- [x] Run all tests, reference check, skill validation and `git diff --check`.
- [x] Review final diff against the initial user changes.

> [!note]- Reading and verification sequence: LEAP Tutor implementation skill contract tests recovery
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.


## Verification record

- Full suite: 420 passed, 1 skipped (Python 3.12; isolated test directory).
- Skill creator validation: passed with Python UTF-8 mode.
- Generated tool reference check and git diff whitespace check: passed.
- Actual catalogs: full 70, quickstart 28.
- Knowledge-vault verification reports four formatting findings only in the original
  supplied architecture proposal; that input file is preserved unchanged.
- Host discovery/activation, semantic quality and enabled/disabled token comparison
  remain explicitly unverified; see docs/agent-skill.md. No commit or release was made.
