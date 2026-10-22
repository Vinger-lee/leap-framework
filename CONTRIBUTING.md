---
title: Contributing
tags:
- leap
- engineering
aliases:
- Contributing guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP Contributing foundations definitions workflow`
> Extension: `LEAP Contributing failure cases examples comparison`
> Advanced: `LEAP Contributing invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# Contributing

Thanks for considering a contribution to LEAP Framework.

## Getting started

```bash
git clone https://github.com/Vinger-lee/leap-framework.git
cd leap-framework
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
```

Python 3.11 or newer is required.

## Before you open a pull request

Use the development environment above for the core checks:

```bash
python -m pytest -q
python scripts/generate_tool_reference.py --check
python scripts/security_scan.py --root .
python scripts/verify_example.py --all
python scripts/verify_teaching_repository.py
python scripts/apply_leap_bridge.py --check
```

Browser and real page-to-MCP checks additionally need the examples dependencies and Chromium:

```bash
python -m pip install -e ".[dev,examples]"
python -m playwright install chromium
python scripts/verify_example_runtime.py --all --json runtime-verification.json
python scripts/verify_mcp_bridge.py
```

All commands must exit successfully; the static example and security scanners also use exit `2`
for warnings. Review those warnings; security findings at P0/P1 and any example error block release.
The generated reference check compares bytes, the teaching repository check validates reciprocal
links and complete paired bodies, and runtime checks validate the declared scenarios and real
transport receipts. None of these checks certifies subject-matter correctness.

This is the shared verification sequence. `.github/workflows/ci.yml` defines the automated subset;
CI installs Chromium with `--with-deps` on Linux. Focused tests are useful during development, but
run the full core suite before submitting a change.

## Code conventions

- Business logic lives in `src/leap/tools/`; the MCP layer in `src/leap/server.py` is a thin
  adapter, which keeps every tool testable without a transport.
- `ALL_TOOL_NAMES` in `src/leap/runtime/profiles.py` is the ordered MCP registry. Define a tool's
  annotations and host-facing docstring beside its implementation, register its name there,
  choose profile membership, then run `python scripts/generate_tool_reference.py`. Keep tool
  inventories exclusively in [[docs/mcp-tools|the generated reference]]; other pages link to it.
- **Coarse tools are a facade, never a second state machine.** A method in
  `src/leap/tools/facade.py` must compose the existing runtime methods and must not write state
  itself, re-derive mastery, or swallow a `ToolError`; a partially completed sequence must hand the
  caller the ids needed to finish it (see how `submit_answer` reports `attempt_id`). When you add a
  coarse tool, decide whether it belongs to `QUICKSTART_TOOL_NAMES` in `src/leap/runtime/profiles.py`
  and regenerate the tool reference.
- Tool layer code depends on the **protocols** in `src/leap/runtime/contracts.py`, never on a
  concrete class. New implementations register against a kind in `runtime/plugins.py`.
- Timestamps are **Unix seconds** everywhere. Because events can share a second, any before/after
  split must use the event log's append order, not the timestamp.
- Timestamps may only be converted to `datetime` in `runtime/scheduler.py`.
- Cached columns (for example `learner_knowledge_state.next_review_at`) are refreshed by the
  runtime; business code must not write them directly.
- A failed tool call must return `{ ok: false, error: { code, message, details } }` and must never
  become a silent state update.

## Schema changes

`CREATE TABLE IF NOT EXISTS` never alters an existing table. When you add a column, register it in
`ADDED_COLUMNS` in `src/leap/storage/database.py` so existing databases are migrated.

## Localization

Learner-facing text goes in `src/leap/i18n.py`. **Do not translate tool names, field names or
enum values** — doing so breaks host-agent integrations.

When you add a message key, add it to **every** catalogue. `pytest tests/test_i18n.py` enforces
identical key sets and placeholders.

## Do not commit

- AI assistant workspaces (`.workbuddy*/`, `.claude*/`, `.cursor*/`, …) and local scratch
  directories — see `.gitignore` and scanner rule `AI001`
- Secrets, tokens, or personal paths — `security_scan.py` blocks them in CI, and the test
  `TestAiWorkspaceIsolation` asserts the index and history are clean
- Local runtime data (`data/`, `artifacts/`, `logs/`, `*.db`)

## Commit and PR style

- Write the subject in the imperative mood: `add …`, `fix …`, `chore …`
- Keep one logical change per commit
- Explain *why* in the body when the change is not self-evident
- Link the relevant issue if there is one

## Reporting bugs

Open an issue including:

- what you expected and what happened
- Python version and OS
- the tool call and its response, with any secrets removed

For security issues, follow [[SECURITY|SECURITY.md]] instead.

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).

> [!note]- Reading and verification sequence: LEAP Contributing
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README]] · [[README_CN]] · [[docs/ARCHITECTURE]] · [[docs/ARCHITECTURE_CN]] · [[docs/EXAMPLES]] · [[docs/FACADE]] · [[docs/FACADE_CN]] · [[docs/LOCALIZATION_CN]] · [[docs/content-quality]] · [[docs/quality-audit-2026-10-10]]
