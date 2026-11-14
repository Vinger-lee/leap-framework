"""SQLite connection management, schema bootstrap and transaction helpers.

Design notes
------------
* The connection runs in autocommit mode (``isolation_level=None``); write
  operations opt into an explicit ``BEGIN IMMEDIATE`` transaction so that the
  optimistic-concurrency checks of section 19.4 are applied atomically.
* **Every access is serialized by a single re-entrant lock.** One MCP server
  process owns one connection while the MCP transport dispatches synchronous
  tool handlers on different threads. Without the lock those handlers
  interleave ``BEGIN IMMEDIATE``/``COMMIT`` on the same connection and corrupt
  each other ("cannot start a transaction within a transaction", partial
  writes). The lock is re-entrant so a tool may call helpers that open their
  own transaction; nested ``transaction()`` calls become SQLite SAVEPOINTs.
* Every timestamp written by LEAP is a Unix timestamp in seconds.
* All access goes through this class so the rest of the codebase never has to
  care about SQLite specifics.
"""

from __future__ import annotations

import logging
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

LOGGER = logging.getLogger(__name__)

__all__ = [
    "Database",
    "now_ts",
    "new_id",
    "new_request_id",
    "SCHEMA_PATH",
    "SEED_PATH",
    "SCHEMA_VERSION",
]

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
SEED_PATH = Path(__file__).resolve().parent / "seed.sql"
SCHEMA_VERSION = "2.0.0"

#: Columns added after the initial release, as ``(table, column, column_ddl)``.
#: ``initialize()`` applies these to databases created by an older build.
ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("learning_sessions", "learning_mode", "learning_mode TEXT NOT NULL DEFAULT 'balanced'"),
    ("learning_sessions", "policy_overrides", "policy_overrides TEXT"),
    ("request_log", "arguments_hash", "arguments_hash TEXT"),
    (
        "transfer_results",
        "session_id",
        "session_id TEXT REFERENCES learning_sessions(session_id) ON DELETE SET NULL",
    ),
)


#: Indexes added after the initial release, as ``(label, sql)``. These carry the
#: uniqueness guarantees that turn a partial/duplicate write into a detectable
#: conflict. They are created after the base schema so databases created by an
#: older build are upgraded in place; a database that already violates the
#: invariant gets a readable migration error instead of a silent pass.
POST_MIGRATION_INDEXES: tuple[tuple[str, str], ...] = (
    (
        "assessment_results.attempt_id must be unique (one committed assessment per attempt)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_results_attempt_unique "
        "ON assessment_results (attempt_id)",
    ),
    (
        "learning_attempts (session_id, node_id, attempt_index) must be unique",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_attempts_unique "
        "ON learning_attempts (session_id, COALESCE(node_id, ''), attempt_index)",
    ),
    (
        "transfer_results.session_id index",
        "CREATE INDEX IF NOT EXISTS idx_transfer_session "
        "ON transfer_results (session_id, learner_id, node_id)",
    ),
)


def now_ts() -> int:
    """Current time as a Unix timestamp in SECONDS (project-wide convention)."""
    return int(time.time())


def new_id(prefix: str) -> str:
    """Generate a short, collision-resistant, prefixed identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def new_request_id() -> str:
    """Opaque identifier used to correlate an MCP request with the event log."""
    return secrets.token_hex(16)


class Database:
    """Thin, explicit wrapper around a single SQLite database."""

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        schema_path: str | Path | None = None,
        seed_path: str | Path | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.path = str(path)
        self._schema_path = Path(schema_path) if schema_path else SCHEMA_PATH
        self._seed_path = Path(seed_path) if seed_path else SEED_PATH

        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            self.path,
            timeout=timeout,
            isolation_level=None,       # autocommit; transactions are explicit
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)}")
        if self.path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")
        #: Serializes every access from this process. Re-entrant because tools
        #: call helper methods that open their own transaction.
        self._lock = threading.RLock()
        self._tx_depth = 0

    # -- lifecycle ---------------------------------------------------------
    def initialize(self) -> "Database":
        """Apply ``schema.sql`` and ``seed.sql``; safe to call repeatedly."""
        if not self._schema_path.exists():
            raise FileNotFoundError(f"schema not found: {self._schema_path}")
        with self._lock:
            self._conn.executescript(self._schema_path.read_text(encoding="utf-8"))
            if self._seed_path.exists():
                self._conn.executescript(self._seed_path.read_text(encoding="utf-8"))
            with self.transaction():
                self._migrate()
                self._post_migrate()
                self._conn.execute(
                    "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (SCHEMA_VERSION,),
                )
        return self

    def _migrate(self) -> None:
        """Add columns introduced after a database was first created.

        ``CREATE TABLE IF NOT EXISTS`` leaves an existing table untouched, so a
        database created by an earlier build would silently miss new columns.
        This keeps upgrades idempotent without a migration framework.
        """
        for table, column, ddl in ADDED_COLUMNS:
            if self._has_column(table, column):
                continue
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    def _has_column(self, table: str, column: str) -> bool:
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(row["name"] == column for row in rows)

    def _post_migrate(self) -> None:
        """Create the uniqueness indexes that make duplicate writes detectable.

        A database that already contains duplicates cannot take the index. That
        is a real data problem, so it surfaces as a readable startup error that
        names the invariant and the repair action instead of a raw sqlite error.
        """
        for label, statement in POST_MIGRATION_INDEXES:
            try:
                self._conn.execute(statement)
            except sqlite3.IntegrityError as exc:  # pragma: no cover - needs dirty DB
                raise RuntimeError(
                    f"database migration failed: {label}. Existing rows violate the "
                    f"invariant ({exc}). Back up the database and repair the affected "
                    "records before restarting LEAP."
                ) from exc

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:  # pragma: no cover - defensive
                pass

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- raw access --------------------------------------------------------
    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, tuple(params))

    def executemany(self, sql: str, seq: Sequence[Sequence[Any]]) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, [tuple(p) for p in seq])

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchall()

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchone()

    def scalar(self, sql: str, params: Sequence[Any] = (), default: Any = None) -> Any:
        row = self.query_one(sql, params)
        if row is None:
            return default
        return row[0]

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Explicit write transaction with rollback on any exception.

        Re-entrant: a nested ``transaction()`` on the same thread becomes a
        SQLite SAVEPOINT, so composing tools keeps one atomic unit. The
        process-wide lock is held for the whole outermost transaction, which is
        what stops concurrent MCP tool handlers from interleaving BEGIN/COMMIT
        on the single connection.
        """
        with self._lock:
            if self._tx_depth:
                depth = self._tx_depth
                savepoint = f"leap_sp_{depth}"
                self._conn.execute(f"SAVEPOINT {savepoint}")
                self._tx_depth = depth + 1
                try:
                    yield self._conn
                except BaseException:
                    self._tx_depth = depth
                    self._conn.execute(f"ROLLBACK TO {savepoint}")
                    self._conn.execute(f"RELEASE {savepoint}")
                    raise
                else:
                    self._tx_depth = depth
                    self._conn.execute(f"RELEASE {savepoint}")
                return

            self._conn.execute("BEGIN IMMEDIATE")
            self._tx_depth = 1
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except BaseException:
                if self._conn.in_transaction:
                    try:
                        self._conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        LOGGER.debug("rollback after failure could not run", exc_info=True)
                raise
            finally:
                self._tx_depth = 0

    # -- introspection -----------------------------------------------------
    def table_names(self) -> list[str]:
        rows = self.query(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [r["name"] for r in rows]

    # -- idempotency (section 19.4) ---------------------------------------
    def lookup_request(self, idempotency_key: str) -> str | None:
        """Return the stored JSON response for a previously seen request."""
        row = self.query_one(
            "SELECT response FROM request_log WHERE idempotency_key = ?",
            (idempotency_key,),
        )
        return row["response"] if row else None

    def request_record(self, idempotency_key: str) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT tool_name, arguments_hash, response FROM request_log WHERE idempotency_key = ?",
            (idempotency_key,),
        )

    def remember_request(
        self,
        idempotency_key: str,
        tool_name: str,
        session_id: str | None,
        response: str,
        *,
        arguments_hash: str | None = None,
    ) -> None:
        self.execute(
            "INSERT INTO request_log "
            "(idempotency_key, tool_name, session_id, response, arguments_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(idempotency_key) DO NOTHING",
            (idempotency_key, tool_name, session_id, response, arguments_hash, now_ts()),
        )

    # -- convenience -------------------------------------------------------
    def rows_to_dicts(self, rows: Sequence[sqlite3.Row]) -> list[dict]:
        return [dict(r) for r in rows]

    @staticmethod
    def row_to_dict(row: sqlite3.Row | None) -> dict | None:
        return dict(row) if row is not None else None

    def dict_from(self, sql: str, params: Sequence[Any] = ()) -> Mapping[str, Any] | None:
        return self.row_to_dict(self.query_one(sql, params))
