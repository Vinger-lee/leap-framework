# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] — 2026-09-20

First public release.

### Added

**Runtime**
- MCP server over stdio exposing 58 tools, with SQLite persistence and an append-only event log
- Server-side **State Guard** — the only component that may authorise a state transition
- Forgetting-aware BKT mastery estimation, computed server-side (never emitted by the host LLM)
- Evidence stages `estimated → practiced → demonstrated → retained → transferred`, with regression
- FSRS-based review scheduling (rating 1–4) via `py-fsrs`
- Rule-based pedagogical policy with strategy/action separation, interleaving, and
  session-scoped policy overrides driven by learner-requested modes
- Misconception tracking, learning-friction signals, transfer probes, and learning-outcome metrics
- Six pluggable seams (state estimation, score aggregation, policy, review scheduler, storage,
  artifact store) declared as `Protocol`s and resolved through a plugin registry

**Internationalisation**
- Message-catalogue layer (`zh-CN`, `en`) for learner-facing text
- `locale` configuration plus `LEAP_LOCALE` environment override
- Tests enforcing identical key sets and placeholders across catalogues

**Tooling**
- `security_scan.py` — secret and PII scanner with a CI gate and suppression markers
- `verify_example.py` — static compliance checker for the teaching pages
- `verify_example_runtime.py` — headless Chromium runtime checker with JSON Schema validation
- `apply_leap_bridge.py` — host-bridge injector with `--check`, `--repair` and `--revert`
- `spec_coverage.py` — mechanical spec-versus-code auditor
- 260 tests

**Examples**
- Five single-file teaching pages: programming, mathematics, computer science, physics, logic
- Shared structural spec, host-bridge contract and JSON output schema
- Every page demonstrates `LEAP.hydrate()` / `LEAP.drainOutbox()` and passes both verifiers

**Documentation**
- Bilingual READMEs (English, 中文) plus Japanese, Korean, French, Spanish, Russian and Arabic
- Architecture, integration, examples and localization guides
- Contributing guide, security policy and code of conduct

### Security

- AI assistant workspaces and local scratch directories are excluded from publication by
  `.gitignore`, scanner rule `AI001` (path-based, so it fires even when the ignore rules are
  bypassed), and a CI test asserting the index and full history contain zero such files
- Line endings normalised to LF via `.gitattributes`, with binaries marked to prevent rewriting

[2.0.0]: https://github.com/Vinger-lee/leap-framework/releases/tag/v2.0.0
