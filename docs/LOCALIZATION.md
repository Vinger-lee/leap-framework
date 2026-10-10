---
title: Localization
tags:
- leap
- engineering
aliases:
- Localization guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP Localization foundations definitions workflow`
> Extension: `LEAP Localization failure cases examples comparison`
> Advanced: `LEAP Localization invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# Localization

**Language**: English ｜ [[docs/LOCALIZATION_CN|中文]]

LEAP is model-agnostic and is embedded by host agents written by anyone, so text a **learner or
operator actually reads** must not be hard-coded to one language.

## Scope: what is translated and what is not

| ✅ Localised | ❌ Deliberately not localised |
|---|---|
| State Guard rejection reasons | Code comments, logs, exception types |
| Domain Grounding notice | **Tool names, field names, enum values** |
| Learning mode names and descriptions | Policy rationale (internal audit trail) |
| Closing report headings and section names | Internal Bloom level identifiers (`apply`, …) |

The rule is: **localise what a human reads, keep machine-facing identifiers stable.** Translating
a tool name or a field name would break every host agent that integrates with it.

## Usage

```yaml
# config/default.yaml
locale: zh-CN
```

Override with the environment:

```bash
LEAP_LOCALE=en python -m leap.server
```

Resolution order:

```
config `locale`  →  LEAP_LOCALE  →  LC_ALL / LC_MESSAGES / LANG  →  zh-CN (default)
```

Accepted aliases (case- and underscore-insensitive): `zh`, `zh-CN`, `zh_Hans`, `cn`, `中文`,
`en`, `en-US`, `english`.

## Reading a message in code

```python
# from a tool (preferred)
msg = self.t("domain_grounding.notice")

# anywhere else
from leap.i18n import translator_for
translator = translator_for(cfg)
msg = translator.t("report.title")
```

`Translator.t()` falls back in this order: **active locale → default locale → the key itself**.
A missing translation shows a key at worst; it never raises.

## Adding a language

1. Add the locale code to `SUPPORTED_LOCALES` in `src/leap/i18n.py`.
2. Add a catalogue under `MESSAGES` with **exactly the same keys** as the default locale.
3. Add common aliases (for example `ja`, `ja-JP`) to `_LOCALE_ALIASES`.
4. Run `pytest tests/test_i18n.py`.

The tests enforce:

- **identical key sets** across catalogues — a missing key fails the build rather than leaking a
  raw key to a learner
- **identical placeholders** — a translation may not drop a `{name}`-style variable
- no empty entries

## Why not gettext / Babel

The message set is small (a few dozen strings) and the project requires **zero external
dependencies and a readable single file**. A dict plus one `t()` function is sufficient, and it
lets constraints like "the two catalogues must have identical key sets" be expressed directly as
assertions.

If the message set grows to hundreds of strings and needs plurals or date formatting, migrating to
the standard toolchain becomes worthwhile — the `Translator.t()` call sites would not change.

## Related files

| File | Purpose |
|---|---|
| `src/leap/i18n.py` | Message catalogues and `Translator` |
| `config/default.yaml` | The `locale` parameter |
| `tests/test_i18n.py` | Catalogue integrity and locale tests |

> [!note]- Reading and verification sequence: LEAP Localization
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[docs/ARCHITECTURE]] · [[docs/LOCALIZATION_CN]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]] · [[docs/i18n/README.ru]]
