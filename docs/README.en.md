# Documentation Index

> This repository does **not** include the full framework design or visual specification.
> Those authoritative documents are maintained by the project author separately and are **not**
> published in this repo. The code in `src/leap/` and the examples in `examples/` follow them;
> contact the author if you need access.


> This repository does **not** include the full framework design or visual specification.
> Those authoritative documents are maintained by the project author separately and are **not**
> published in this repo. The code in `src/leap/` and the examples in `examples/` follow them;
> contact the author if you need access.


**Language**: [简体中文](README.md) ｜ **English**

---

## Authoritative specifications (read before changing anything)

| Document | Language | Covers |
|---|---|---|
| *(Document not in this repo)* | — | (author-maintained design doc, not in this repository). The code follows it. |
| *(Document not in this repo)* | — | (author-maintained visual spec, not in this repository). Every example must follow it. |
| [`../examples/_shared/leap-web-spec.md`](../examples/_shared/leap-web-spec.md) | Chinese | Page **structure and data contract** |
| [`../examples/_shared/leap-bridge.md`](../examples/_shared/leap-bridge.md) | Chinese | **Host bridge contract**: the two-way page ↔ Runtime interface |
| [`../examples/_shared/interaction-output.schema.json`](../examples/_shared/interaction-output.schema.json) | — | Machine-readable JSON output contract |

> Conflict resolution: **structure** follows `leap-web-spec.md` (in this repo); **visuals and framework behaviour** follow the author-maintained design documents (not in this repo).
> document, **framework behaviour** follows the V2 design document.

---

## Integration guides

| Document | Language | Audience |
|---|---|---|
| [`host-agent-system-prompt.md`](host-agent-system-prompt.md) | Chinese | Developers integrating a host agent |
| [`host-agent-system-prompt.en.md`](host-agent-system-prompt.en.md) | English | Same, in English |
| [`i18n.md`](i18n.md) | Chinese | Anyone adding a UI language |
| [`i18n.en.md`](i18n.en.md) | English | Same, in English |

---

## Project documentation

| Document | Contents |
|---|---|
| [`../README.md`](../README.md) | Project overview (Chinese) |
| [`../README.en.md`](../README.en.md) | Project overview (English) |
| [`../examples/README.md`](../examples/README.md) | Examples: naming, acceptance checklist, automated verification |
| [`../reports/`](../reports/) | Staged implementation reports (step-01 … step-10) |

---

## Self-check scripts

Run these in order after a change or before a release:

```bash
pytest -q                                          # full test suite
python scripts/spec_coverage.py                    # spec vs. code coverage
python scripts/security_scan.py --root .           # privacy and secret scan
python scripts/verify_example.py --all             # static example compliance
python scripts/verify_example_runtime.py --all     # example runtime behaviour (needs playwright)
python scripts/apply_leap_bridge.py --check        # host bridge completeness
```

Exit codes: `0` clean / `1` blocking problem / `2` warnings only. The first four are wired into CI.

---

## What is excluded from publication

This repository is public. The following exist **locally only** and never reach a commit:

| Path | Contents | Why |
|---|---|---|
| `.workbuddy-ai/`, `.workbuddy*/` | AI assistant workspace (memory, drafts, session state) | Local agent state, not project source |
| `.claude*/`, `.cursor*/`, `.aider*`, `.continue*/`, `.codeium/`, `.copilot/`, `.windsurf/`, `.zed/`, `.specstory/`, `.gemini/` and similar | Configuration and state of various AI tools | As above, and often personalised |
| `agent-state/`, `.ai/`, `ai-cache/` | Generic agent state and caches | As above |
| `.mcp.json` | MCP client configuration | Its `env` block routinely holds API credentials; sanitise and `git add -f` if you need to ship one |
| `_archive/` | Internal working material and temporary artefacts | See [`../_archive/README.md`](../_archive/README.md) |
| `.pytest_cache/`, `__pycache__/`, `data/`, `artifacts/`, `logs/` | Caches, build output, local runtime data | Regenerated on demand |

### Three layers of protection

This does not rely on anyone remembering to be careful:

1. **`.gitignore`** — covers every path above, including wildcard forms (`.workbuddy*/`) so variant names are caught too;
2. **Scanner rule `AI001`** — path-level detection that reports P1 and blocks even when `.gitignore` is bypassed (e.g. `git add -f`);
3. **Tests** — `tests/test_infrastructure.py::TestAiWorkspaceIsolation` queries `git ls-files` and the full commit history and asserts zero tracked AI-workspace files. **CI runs it on every push.**

> In other words: even if the first two layers fail, CI still stops it.

---

## Adding a language

For a new **UI** language see [`i18n.en.md`](i18n.en.md) §4. For a new **documentation** language,
follow the `<name>.<locale>.md` convention in this directory and add a row to the tables above.
