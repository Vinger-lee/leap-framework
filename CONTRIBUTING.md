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
pytest -q                                        # 260 tests
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

For security issues, follow [`SECURITY.md`](SECURITY.md) instead.

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
