# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 2.0.x | ✅ |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Use GitHub's private vulnerability reporting instead:

<https://github.com/Vinger-lee/leap-framework/security/advisories/new>

If that is unavailable, open a private security advisory on the repository, or contact the
maintainer through GitHub.

Please include:

- a description of the issue and its impact
- steps to reproduce
- the affected version or commit
- any suggested mitigation

You can expect an initial response within 7 days. Once the report is confirmed, a fix and an
advisory will be prepared, and you will be credited unless you prefer otherwise.

## Scope

In scope:

- credential or secret exposure in tracked files
- injection or deserialisation issues in the MCP tool layer
- authentication or authorisation gaps, where enabled
- unsafe handling of persisted learner data
- path traversal in artifact storage

Out of scope:

- issues that require an already-compromised host machine
- the accuracy of pedagogical heuristics, which are engineering parameters rather than security
  controls
- reports produced by automated scanners without a demonstrable impact

## Handling sensitive data

LEAP persists learner state, assessment evidence and artifacts locally. Before sharing a database,
an artifact, or an event log for debugging, remove or redact:

- learner identifiers and free-text answers
- benchmark reports and source references
- any credentials in `config/` or environment overrides

## Deployment notes

The default configuration assumes a **single trusted machine**:

- `mcp_transport: stdio` — local process only
- `auth_enabled: false` — no network surface by default

If you expose LEAP over a network, enable authentication and TLS, and review the credential
handling of any MCP client configuration (`.mcp.json` commonly holds API credentials in its `env`
block and is therefore ignored by default in this repository).

## Automated checks

`scripts/security_scan.py` runs in CI and gates on P0/P1 findings. Suppression is explicit and
auditable:

- line-level: `security-scan: allow`
- file-level: `security-scan: allow-file` in the first lines of the file

Test fixtures that deliberately contain synthetic secrets must carry one of these markers,
otherwise the scanner flags its own samples.
