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

Run the quality gates — CI runs the first four on every push:

```bash
pytest -q                                        # the full suite
python scripts/security_scan.py --root .         # secrets & PII, must be P0/P1 = 0
python scripts/verify_example.py --all           # example static compliance
python scripts/verify_example_runtime.py --all   # example runtime compliance
python scripts/spec_coverage.py                  # spec coverage
python scripts/apply_leap_bridge.py --check      # host-bridge completeness
```

Exit codes are `0` clean / `1` blocking / `2` warnings only.

## Code conventions

- Business logic lives in `src/leap/tools/`; the MCP layer in `src/leap/server.py` is a thin
  adapter, which keeps every tool testable without a transport.
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

[[Knowledge_Index]] · [[README]] · [[README_CN]]
