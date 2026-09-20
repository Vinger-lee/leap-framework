"""Infrastructure tests: configuration, storage and the privacy scanner.

security-scan: allow-file
This module intentionally contains synthetic PII and secret-shaped strings so
the scanner's rules can be tested. Every such line is annotated below; the
file-level marker exempts the module from the repository cleanliness gate.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from leap.config import REPO_ROOT, Config, load_config
from leap.storage import Database, new_id, now_ts


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
class TestConfig:
    def test_defaults_load(self, base_config):
        assert base_config.get("mastery_threshold") == 0.80
        assert base_config.get("mcp_transport") == "stdio"
        assert base_config.get("auth_enabled") is False

    def test_dotted_lookup_and_defaults(self, base_config):
        assert base_config.get("bkt.p_init") == 0.20
        assert base_config.get("does.not.exist", "fallback") == "fallback"

    def test_require_raises_on_missing_key(self, base_config):
        with pytest.raises(KeyError):
            base_config.require("nope.nope")

    def test_overrides_win(self):
        cfg = load_config(overrides={"mastery_threshold": 0.95, "bkt": {"p_init": 0.5}})
        assert cfg.get("mastery_threshold") == 0.95
        assert cfg.get("bkt.p_init") == 0.5
        assert cfg.get("bkt.p_transit") == 0.30  # untouched sibling survives the merge

    def test_env_overrides_are_applied(self, monkeypatch):
        monkeypatch.setenv("LEAP__MASTERY_THRESHOLD", "0.66")
        monkeypatch.setenv("LEAP__BKT__P_SLIP", "0.25")
        cfg = load_config()
        assert cfg.get("mastery_threshold") == 0.66
        assert cfg.get("bkt.p_slip") == 0.25

    def test_overall_score_weights_sum_to_one(self, base_config):
        weights = base_config.get("overall_score_weights")
        assert sum(weights.values()) == pytest.approx(1.0)
        assert "transfer" not in weights
        assert "hint_dependency" not in weights

    def test_config_returns_copies(self, base_config):
        snapshot = base_config.as_dict()
        snapshot["mastery_threshold"] = 0.0
        assert base_config.get("mastery_threshold") == 0.80


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
EXPECTED_TABLES = {
    "learners", "learning_sessions", "learning_goals", "knowledge_nodes", "knowledge_edges",
    "learner_knowledge_state", "misconceptions", "assessment_items", "learning_attempts",
    "assessment_results", "transfer_results", "pedagogical_strategies", "pedagogical_decisions",
    "review_items", "evidence_sources", "benchmark_claims", "event_log", "artifacts",
}


class TestStorage:
    def test_schema_creates_every_documented_table(self):
        db = Database(":memory:").initialize()
        assert EXPECTED_TABLES.issubset(set(db.table_names()))
        db.close()

    def test_initialization_is_idempotent(self):
        db = Database(":memory:")
        db.initialize()
        before = len(db.table_names())
        db.initialize()
        assert len(db.table_names()) == before
        db.close()

    def test_strategy_library_is_seeded_once(self):
        db = Database(":memory:")
        db.initialize()
        db.initialize()
        assert db.scalar("SELECT COUNT(*) FROM pedagogical_strategies") == 10
        db.close()

    def test_timestamps_are_unix_seconds(self):
        now = now_ts()
        assert isinstance(now, int)
        assert 1_600_000_000 < now < 4_000_000_000

    def test_foreign_keys_are_enforced(self):
        db = Database(":memory:").initialize()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO learning_sessions (session_id, learner_id, topic, created_at, updated_at) "
                "VALUES ('s', 'ghost-learner', 't', 1, 1)"
            )
        db.close()

    def test_raw_answer_cannot_be_null(self):
        db = Database(":memory:").initialize()
        db.execute("INSERT INTO learners VALUES ('L','n',1,1)")
        db.execute(
            "INSERT INTO learning_sessions (session_id, learner_id, topic, created_at, updated_at) "
            "VALUES ('s','L','t',1,1)"
        )
        db.execute(
            "INSERT INTO learning_attempts (attempt_id, session_id, answer, created_at) "
            "VALUES ('a','s','x',1)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO assessment_results "
                "(result_id, attempt_id, assessor_type, raw_answer, created_at) "
                "VALUES ('r','a','model',NULL,1)"
            )
        db.close()

    def test_evidence_stage_enum_is_constrained(self):
        db = Database(":memory:").initialize()
        db.execute("INSERT INTO learners VALUES ('L','n',1,1)")
        db.execute(
            "INSERT INTO knowledge_nodes (node_id, title, created_at, updated_at) "
            "VALUES ('n1','t',1,1)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO learner_knowledge_state "
                "(learner_id, node_id, mastery_probability, evidence_stage, updated_at) "
                "VALUES ('L','n1',0.5,'mastered',1)"
            )
        db.close()

    def test_transaction_rolls_back_on_error(self):
        db = Database(":memory:").initialize()
        db.execute("INSERT INTO learners VALUES ('L','n',1,1)")
        with pytest.raises(RuntimeError):
            with db.transaction():
                db.execute(
                    "INSERT INTO learning_sessions "
                    "(session_id, learner_id, topic, created_at, updated_at) "
                    "VALUES ('s1','L','t',1,1)"
                )
                raise RuntimeError("boom")
        assert db.scalar("SELECT COUNT(*) FROM learning_sessions") == 0
        db.close()

    def test_idempotency_store_round_trip(self):
        db = Database(":memory:").initialize()
        assert db.lookup_request("k1") is None
        db.remember_request("k1", "create_session", "s1", json.dumps({"ok": True}))
        assert json.loads(db.lookup_request("k1"))["ok"] is True
        # Remembering twice must not raise.
        db.remember_request("k1", "create_session", "s1", json.dumps({"ok": True}))
        db.close()

    def test_generated_ids_are_prefixed_and_unique(self):
        ids = {new_id("ses") for _ in range(200)}
        assert len(ids) == 200
        assert all(i.startswith("ses_") for i in ids)


# ---------------------------------------------------------------------------
# Privacy scanner
# ---------------------------------------------------------------------------
def _load_scanner():
    path = REPO_ROOT / "scripts" / "security_scan.py"
    spec = importlib.util.spec_from_file_location("leap_security_scan", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclasses resolves annotations via sys.modules, so register first.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCANNER = _load_scanner()


class TestSecurityScanner:
    def _scan(self, tmp_path: Path, filename: str, content: str) -> list:
        (tmp_path / filename).write_text(content, encoding="utf-8")
        files = list(SCANNER.iter_files(tmp_path, set(), set()))
        findings: list = []
        for path in files:
            findings.extend(SCANNER.scan_file(path, tmp_path, SCANNER.RULES))
        return SCANNER.dedupe(findings)

    def _rule_ids(self, tmp_path: Path, filename: str, content: str) -> set[str]:
        return {f.rule_id for f in self._scan(tmp_path, filename, content)}

    def test_clean_file_produces_no_findings(self, tmp_path):
        assert self._scan(tmp_path, "ok.md", "# Title\n\nNormal prose.\n") == []

    def test_detects_api_keys(self, tmp_path):
        assert "SEC002" in self._rule_ids(tmp_path, "k.md", "key: sk-abcdefghijklmnopqrstuvwx\n")

    def test_detects_private_key_blocks(self, tmp_path):
        ids = self._rule_ids(tmp_path, "p.md", "-----BEGIN RSA PRIVATE KEY-----\nabc\n")
        assert "SEC001" in ids

    def test_detects_windows_personal_paths(self, tmp_path):
        ids = self._rule_ids(tmp_path, "w.md", r"path: E:\Users\someone\Documents\a.md" + "\n")
        assert "PII002" in ids

    def test_detects_unix_personal_paths(self, tmp_path):
        assert "PII003" in self._rule_ids(tmp_path, "u.md", "home: /Users/bob/project\n")

    def test_windows_path_is_not_double_reported(self, tmp_path):
        findings = self._scan(tmp_path, "w2.md", "p: C:/Users/bob/x\n")
        unix = [f for f in findings if f.rule_id == "PII003"]
        assert unix == []

    def test_detects_email_and_phone(self, tmp_path):
        ids = self._rule_ids(tmp_path, "e.md", "a@b.com and 13812345678\n")
        assert {"PII004", "PII005"} <= ids

    def test_documented_non_identifying_addresses_are_allowlisted(self, tmp_path):
        """GitHub noreply and RFC 2606 example domains must not be flagged."""
        content = (
            "mail: 12345+user@users.noreply.github.com\n"
            "docs: someone@example.com\n"
            "reserved: nobody@example.org\n"
        )
        assert "PII004" not in self._rule_ids(tmp_path, "noreply.md", content)

    def test_allowlist_does_not_suppress_real_looking_addresses(self, tmp_path):
        ids = self._rule_ids(tmp_path, "real.md", "contact: alice@acme-corp.com\n")
        assert "PII004" in ids

    def test_inline_allow_marker_suppresses_a_line(self, tmp_path):
        content = (
            'FAKE = "sk-abcdefghijklmnopqrstuvwx"  # security-scan: allow\n'
            'REAL = "sk-zyxwvutsrqponmlkjihgfedc"  # security-scan: allow\n'
        )
        assert "SEC002" not in self._rule_ids(tmp_path, "marker.md", content)

    def test_file_level_marker_suppresses_the_whole_file(self, tmp_path):
        content = (
            '"""Fixtures.\n\nsecurity-scan: allow-file\n"""\n'
            'KEY = "sk-abcdefghijklmnopqrstuvwx"\n'
        )
        assert self._scan(tmp_path, "fixture.md", content) == []

    def test_detects_ai_citation_artifacts(self, tmp_path):
        ids = self._rule_ids(tmp_path, "c.md", "leftover fileciteturn0file0L17-L43 here\n")
        assert "ART001" in ids

    def test_detects_private_use_characters(self, tmp_path):
        ids = self._rule_ids(tmp_path, "pua.md", "text \ue000 hidden\n")
        assert "ART002" in ids

    def test_detects_bidi_control_characters(self, tmp_path):
        ids = self._rule_ids(tmp_path, "bidi.md", "text \u202e reversed\n")
        assert "ART003" in ids

    def test_markdown_report_renders(self):
        report = SCANNER.render_markdown([], REPO_ROOT, 0)
        assert "Security & Privacy Scan Report" in report
        assert "No findings" in report

    def test_repository_itself_is_clean(self):
        """The project must stay publishable - this is the regression gate."""
        findings: list = []
        files = list(
            SCANNER.iter_files(REPO_ROOT, SCANNER.DEFAULT_SKIP_DIRS, SCANNER.DEFAULT_SKIP_SUFFIXES)
        )
        for path in files:
            findings.extend(SCANNER.scan_file(path, REPO_ROOT, SCANNER.RULES))
        blocking = [f for f in SCANNER.dedupe(findings) if f.severity in ("P0", "P1")]
        assert blocking == [], f"privacy findings block public release: {blocking}"


class TestAiWorkspaceIsolation:
    """AI assistant workspaces are local state and must never be published."""

    def test_scanner_flags_ai_workspace_paths(self, tmp_path):
        for rel in (
            ".workbuddy-ai/memory/2026-09-19.md",
            ".claude/settings.json",
            ".cursor/rules.md",
            ".aider.chat.history.md",
            "agent-state/session.json",
            "ai-cache/blob.bin",
        ):
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("local agent state", encoding="utf-8")
            ids = {f.rule_id for f in SCANNER.scan_file(target, tmp_path, SCANNER.RULES)}
            assert "AI001" in ids, f"{rel} was not flagged"

    def test_scanner_does_not_flag_project_files(self, tmp_path):
        for rel in ("src/leap/server.py", "docs/README.md", "reports/step-01.md",
                    "examples/README.en.md", ".github/workflows/ci.yml"):
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("project source", encoding="utf-8")
            ids = {f.rule_id for f in SCANNER.scan_file(target, tmp_path, SCANNER.RULES)}
            assert "AI001" not in ids, f"{rel} was wrongly flagged"

    def test_no_ai_workspace_file_is_tracked_by_git(self):
        """The hard guarantee: nothing from an agent workspace is in the index.

        ``.gitignore`` can be bypassed with ``git add -f``, so the ignore rules
        alone are not sufficient - this asserts against the actual index.
        """
        import subprocess

        result = subprocess.run(
            ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            pytest.skip("not a git repository")

        offenders = [
            line for line in result.stdout.splitlines()
            if SCANNER.AI_WORKSPACE_PATTERN.search(line)
        ]
        assert offenders == [], f"AI workspace files are tracked: {offenders}"

    def test_no_ai_workspace_file_is_tracked_in_any_commit(self):
        """Also check history, so a force-added file cannot hide in a past commit."""
        import subprocess

        result = subprocess.run(
            ["git", "log", "--all", "--name-only", "--pretty=format:"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            pytest.skip("not a git repository")

        offenders = sorted({
            line for line in result.stdout.splitlines()
            if line.strip() and SCANNER.AI_WORKSPACE_PATTERN.search(line)
        })
        assert offenders == [], f"AI workspace files appear in history: {offenders}"

    def test_gitignore_covers_the_common_ai_workspaces(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        for entry in (".workbuddy", ".claude", ".cursor", ".aider", ".continue",
                      "agent-state", "_archive/"):
            assert entry in gitignore, f".gitignore does not cover {entry}"

    def test_ignored_paths_are_actually_ignored(self):
        """Ask git itself, rather than trusting the file's contents."""
        import subprocess

        probes = [".workbuddy-ai/memory/x.md", ".claude/settings.json",
                  ".cursor/rules.md", "_archive/internal/x.md"]
        for probe in probes:
            result = subprocess.run(
                ["git", "check-ignore", "-q", probe],
                cwd=REPO_ROOT, capture_output=True, check=False,
            )
            if result.returncode == 128:
                pytest.skip("not a git repository")
            assert result.returncode == 0, f"{probe} is NOT ignored"
