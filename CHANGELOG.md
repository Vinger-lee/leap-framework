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

## [Unreleased]

- Add on-demand A4 print materials with separate illustrated handout, workbook,
  and answer-key HTML. Export via the course bridge, MCP, or the `leap-print` CLI.
  The default combined edition starts the workbook on a fresh page. The
  linear-equations lesson ships all four offline editions, with eight questions
  and a matching worked answer key. See the [printing guide](docs/printing.md).

- Migrate SQLite columns before creating dependent indexes, preserving data
  written by earlier releases.
- Commit MCP request receipts and their writes atomically. Identical retries
  replay the original receipt, including recoverable partial submissions.
  Reusing a request ID with different arguments or a different tool is rejected.
- Scope spaced reviews to the node's owning session, support all four FSRS
  ratings, and prevent new assessment writes after session closure.
- Check unit advancement and apply it in a single write transaction.
- Weight BKT learning transitions by the observed score, so a fully incorrect
  answer cannot raise estimated mastery.

### Added

- Reviewed sources for the first higher-mathematics unit, covering limits,
  derivatives and differentiability. Both MCP profiles expose
  `get_grounding_sources` for reading locators, answering checks and retrieving
  the reviewed node, Markdown, HTML, items and print draft after calibration.
- An on-demand source precheck via `python scripts/review_grounding_sources.py`.
  The first pack has a 180-day review period. Maintainers approve updates manually.
- Full course export saves the registered teaching HTML and four A4 PDFs in one
  course-title folder under a configurable output directory. The file names carry
  the course title, and the course page requests PDFs for its own package version.

- Repository `leap-tutor` skill draft with conditional lifecycle, content-quality
  and recovery references, versioned with LEAP 2.1.0.
- Skill contracts and real MCP stdio tests for both profiles: evidence and DAG
  gates, teaching packages, split semantic assessment, partial-failure recovery,
  refused advancement and separate reporting/closure.
- **Repository event vocabulary:** `docs/ARCHITECTURE.md` documents the
  section 18.1 event names (net change in this batch: none) and
  `tests/test_spec_gaps.py` checks them against real emit call sites in both
  directions, replacing a permanently skipped placeholder test.
- `tests/test_packaging.py` keeps an installable wheel honest: packaged config
  bytes, package-data patterns, dependency floor, entry points and discovered
  package layout are asserted statically.
- `docs/host-config.md` with copy-paste `mcpServers` configuration samples for
  hosts that connect LEAP over stdio.

### Changed

- Formal teaching, assessment, review and export require current reviewed
  evidence. Teaching packages, items and print drafts must match the reviewed
  content. Legacy host attestations and grounding waivers are rejected. SQLite
  preserves calibration receipts and readable history across restarts.
  Hosts can save new content with `save_artifact` as a `teaching_draft` in full.
  The tool profiles provide 75 tools in full and 36 in quickstart.

- **Anatomy visual contracts are enforced for new deliveries.** A first teaching
  package for a session/node must carry a full `anatomy.v2` contract; legacy
  `anatomy.v1` or missing contracts only pass as an explicit `allow_legacy`
  compatibility path with warnings, so research, parts, inspection and model
  checks can no longer be skipped silently. Text-only lessons declare
  `no_visual_reason` and report `not_applicable`; `visual_authoring` is split
  into `visual_contract_state` / `visual_contract_valid` / `package_valid`; the
  policy is re-read at request time; and the repository gate runs a registration
  simulation over every shipped example so a manifest can no longer look valid
  while being unregistrable.
- **Anatomy manifests reject silent mistakes.** Unknown top-level fields are
  rejected with a case hint, semantic fields have minimum-content checks, source
  records bind to the latest completed benchmark report, visible-text parsing
  ignores non-rendered subtrees, selector/id errors are classified, and all
  eight example manifests carry documented `source_ids` placeholders plus
  `policy_id`/`policy_version`; example 04 is migrated to `anatomy.v2`.
- **Runtime hardening.** Database access is serialized so parallel tool calls
  cannot interleave a single SQLite transaction and leave partial writes;
  `learning_attempts` has a unique attempt index, assessment commits are
  idempotent per attempt, `request_id` replay returns the first response and the
  optimistic state-version check runs inside the write transaction.
- **State and metrics corrections.** Evidence stage no longer regresses when an
  optional `session_id` is omitted, an incomplete repeated benchmark report no
  longer downgrades completed Domain Grounding, diagnostic completion and unit
  advancement choose the next node from the DAG instead of dictionary order, and
  the learning-gain baseline splits results by evidence records rather than
  attempt counts.
- **Host surface is narrower and cheaper.** `manual_override` is no longer
  reachable from the host tool schema; closed sessions return `session_closed`
  with a null `next_call` and idempotent closing; `complete_session` requires the
  final report unless explicitly overridden; responses carry a compact
  `policy_version` instead of the full policy (fetch it with
  `get_teaching_delivery_policy`); `continue_lesson` defaults to a summary
  (`verbose=True` for the full context) and `get_teaching_context` takes
  `include_template=False` by default. Quickstart includes `assess_misconception`,
  `find_session` and `get_teaching_context`.
- Quickstart now exposes existing `commit_assessment`, `resolve_misconception`,
  `assess_misconception` and `complete_session` tools.
- Server instructions route detailed workflows to the optional skill, retaining
  Runtime boundaries and dynamic visual-authoring policy. Integration guides
  retain the full prompt for hosts without skill support.
- **Packaging and installation.** `config/default.yaml` ships inside the wheel
  (`leap/config/default.yaml`, kept byte-identical by a test), the dependency
  floor is the real `mcp>=2.3,<3` for the `MCPServer` API in use, data-only
  subdirectories stay out of package discovery, and an installed server resolves
  `database_path`/`artifact_root` against `LEAP_HOME` or the working directory
  instead of the install location.
- **Public documentation renders on GitHub and PyPI.** `README.md`,
  `README_CN.md` and the translated READMEs use standard Markdown links instead
  of Obsidian wikilinks; the repository vault keeps wikilinks.
- **CI covers the documented sequence.** The workflow runs on every branch and
  pull request and adds `leap-doctor` plus the reproducible drop-tower SVG check;
  verification reports are written outside the checkout, and the security scan
  documents the same 0/1/2 exit-code contract as the example gate.
- **Agent skill guidance tightened.** The `leap-tutor` description narrows its
  trigger conditions (ordinary one-off questions and LEAP source development do
  not trigger it); the skill documents reviewed-source calibration, closed
  session behaviour and the rule that review ratings must be real learner input;
  `docs/host-config.md` replaces per-host guesswork and the integration guide
  separates a quickstart-compatible prompt from full-only fine-grained tooling.
  Documented draft status, the host acceptance matrix, unmeasured token costs and
  the existing HTML outbox bridge's full-profile requirement remain explicit;
  MCP Skills extension distribution remains deferred.

### Fixed

- Teaching-repository gate: the root architecture proposal now carries Obsidian
  metadata (frontmatter, learning resources, foldable callout, reciprocal
  backlink) so `scripts/verify_teaching_repository.py` exits 0 again.
- Generated verification reports (`security-scan.md`, `*-verification.json`, ...)
  are ignored and never read as vault notes by the teaching-repository gate.
- `CHANGELOG` no longer references the removed `verify_math1_chapter.py` helper.

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
- Catalog-count assertions in `verify_mcp_bridge.py` compare against the live catalog instead of a
  hard-coded number, so adding a tool can no longer leave a stale constant behind.
- 38 new tests cover facade composition, error recovery, profile filtering and the self-check.

### Fixed

- Scenario assertions in `verify_example_runtime.py` now let queued browser tasks run before they
  are evaluated. An interaction that reports through a queued task (`<details>` fires its `toggle`
  event that way) could leave a stale event count behind, which made example 08 fail the folded
  worked-solution gate intermittently. The assertions themselves are unchanged.

## Pre-2.1.0 — 2026-10-11

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
