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
