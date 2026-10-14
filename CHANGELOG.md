---
title: Changelog
tags:
- leap
- engineering
aliases:
- Changelog guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP Changelog foundations definitions workflow`
> Extension: `LEAP Changelog failure cases examples comparison`
> Advanced: `LEAP Changelog invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] — 2026-10-14

### Added

- **Coarse tutor API.** Eight tools compose the fine-grained runtime server-side, so a teaching turn
  takes one or two calls instead of six: `start_learning`, `continue_lesson`, `log_teaching_action`,
  `submit_answer`, `advance_lesson`, `get_review_queue`, `review_answer`, `get_learner_snapshot`.
  Each response carries `next_call` - the next tool to call, with its arguments and the reason - and
  the facade relaxes nothing: the State Guard still decides, a refused advance writes nothing, a
  failed assessment keeps the stored attempt recoverable, raw answers are preserved verbatim and
  mastery is still estimated server-side. The server now registers 70 tools.
- **Tool profiles.** `--tool-profile quickstart` (or `LEAP_TOOL_PROFILE`, or `tool_profile` in
  `config/default.yaml`) exposes 25 tools instead of 70. An unknown profile name is refused at
  startup instead of silently widening the surface to `full`.
- **`leap-doctor` / `python -m leap.doctor`.** Installation self-check covering the interpreter,
  runtime dependencies, configuration, database directory writability, schema creation in a throwaway
  database, artifact root, message catalogues and the per-profile tool counts. Supports `--json`,
  `--profile` and meaningful exit codes, and never opens the configured database for writing.
- **`docs/FACADE.md` / `docs/FACADE_CN.md`** (coarse API, profiles, verification) and
  **`docs/scope-and-limits.md` / `docs/scope-and-limits_CN.md`** (what the runtime does and does not
  guarantee, and which claims have no evidence yet).

### Changed

- `build_server(profile=...)` selects the exposed tool catalog; `leap.server:main` accepts
  `--tool-profile` and ignores unrecognised client arguments instead of aborting startup.
- The integration guide, both READMEs and the knowledge index document the coarse path, the profiles
  and the scope boundaries.
- Catalog-count assertions in `verify_mcp_bridge.py` and `verify_math1_chapter.py` compare against
  the live catalog instead of a hard-coded number, so adding a tool can no longer leave a stale
  constant behind.
- 38 new tests cover facade composition, error recovery, profile filtering and the self-check.

### Fixed

- Scenario assertions in `verify_example_runtime.py` now let queued browser tasks run before they
  are evaluated. An interaction that reports through a queued task (`<details>` fires its `toggle`
  event that way) could leave a stale event count behind, which made example 08 fail the folded
  worked-solution gate intermittently. The assertions themselves are unchanged.

## [Unreleased] — 2026-10-11

- Apply permanent delivery policy 3.0 to every MCP response and learning mode. Add full policy retrieval, an 11-subject starter catalog and registration of actual canonical Markdown/HTML teaching packages, bringing the server to 62 tools.
- Require accepted teaching packages before registering questions and teaching artifacts; diagnostic submissions use the same source and item gates. Keep structural acceptance distinct from subject-matter truth.
- Rewrite the five original lessons and add probability, stoichiometry and basic circuits. Add full Obsidian knowledge notes, controlled diagrams, wide desktop layouts and reciprocal links across repository Markdown.
- Preserve original per-item answers, unknown assessment dimensions and Runtime authority. Only matching assessment/progression receipts confirm scores or completion; free-text reasoning requires host review.
- Add a reproducible 2028 Math I first-chapter recipe with 32 reviewed questions, actual MCP registration, offline record/receipt exchange, source snapshot checks and a temporary-database browser verifier. Invalid numeric expressions are preserved and graded wrong without breaking synchronization.
- Expand browser scenarios to real correct, wrong, boundary, drag, keyboard, hint and retry paths; enforce complete Markdown coverage and prevent generated tool documentation drift in CI.

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

> [!note]- Reading and verification sequence: LEAP Changelog
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README]] · [[README_CN]]
