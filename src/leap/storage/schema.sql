-- ===========================================================================
-- LEAP Framework V2.0 - SQLite schema (P0)
-- ---------------------------------------------------------------------------
-- Design rules (LEAP-Framework-V2 section 23):
--   1. Knowledge ontology and learner state are separated.
--   2. Review items are separated from knowledge nodes.
--   3. Event log is separated from business state.
--   4. Every `*_at` column is a Unix timestamp in SECONDS.
--   5. Where one semantic value exists in two tables, the authoritative source
--      is documented and the other column is a read-only cache refreshed by
--      the Runtime. Business code must never write cache columns directly.
-- ===========================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- 23.1 learners
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS learners (
    learner_id  TEXT PRIMARY KEY,
    name        TEXT,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

-- ---------------------------------------------------------------------------
-- 23.2 learning_sessions
--   Domain-grounding configuration is PER-SESSION, not global.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS learning_sessions (
    session_id                    TEXT PRIMARY KEY,
    learner_id                    TEXT NOT NULL REFERENCES learners(learner_id),
    topic                         TEXT NOT NULL,
    status                        TEXT NOT NULL DEFAULT 'active'
                                  CHECK (status IN ('active', 'paused', 'completed', 'abandoned')),
    current_node_id               TEXT,
    state_version                 INTEGER NOT NULL DEFAULT 1,
    -- Domain grounding (per-session config)
    allow_skip_domain_grounding   INTEGER NOT NULL DEFAULT 0 CHECK (allow_skip_domain_grounding IN (0, 1)),
    domain_grounding_warn_user    INTEGER NOT NULL DEFAULT 1 CHECK (domain_grounding_warn_user IN (0, 1)),
    domain_grounding_stage        TEXT CHECK (domain_grounding_stage IN ('pending', 'in_progress', 'completed')),
    -- Authoritative source: artifacts.artifact_id
    benchmark_report_artifact_id  TEXT REFERENCES artifacts(artifact_id),
    -- Custom learning mode (section 32). Session-scoped, never global.
    learning_mode                 TEXT NOT NULL DEFAULT 'balanced',
    policy_overrides              TEXT,           -- JSON: Learning Configuration + Policy Overrides
    dag_version                   TEXT,           -- P1, nullable in P0
    created_at                    INTEGER NOT NULL,
    updated_at                    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_learner_topic
    ON learning_sessions (learner_id, topic);

-- ---------------------------------------------------------------------------
-- 23.3 learning_goals
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS learning_goals (
    goal_id                 TEXT PRIMARY KEY,
    session_id              TEXT NOT NULL REFERENCES learning_sessions(session_id) ON DELETE CASCADE,
    goal                    TEXT,
    target_domain           TEXT,
    target_outcome          TEXT,
    target_depth            TEXT,
    time_budget             INTEGER,
    prior_knowledge         TEXT,
    constraints             TEXT,
    materials               TEXT,
    assessment_requirements TEXT,
    created_at              INTEGER NOT NULL,
    updated_at              INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goals_session ON learning_goals (session_id);

-- ---------------------------------------------------------------------------
-- 23.4 knowledge_nodes
--   The single atomic entity of the data layer. `unit_tag` is a business-layer
--   aggregation label only - there is deliberately NO separate `units` table.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    node_id                 TEXT PRIMARY KEY,
    session_id              TEXT REFERENCES learning_sessions(session_id) ON DELETE CASCADE,
    title                   TEXT NOT NULL,
    description             TEXT,
    domain                  TEXT,
    learning_objective      TEXT,
    bloom_level             TEXT,
    difficulty              REAL,
    estimated_duration      INTEGER,
    required_evidence       TEXT,
    assessment_requirements TEXT,
    transfer_requirements   TEXT,
    unit_tag                TEXT,
    version                 TEXT NOT NULL DEFAULT '1',
    created_at              INTEGER NOT NULL,
    updated_at              INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_session   ON knowledge_nodes (session_id);
CREATE INDEX IF NOT EXISTS idx_nodes_unit_tag  ON knowledge_nodes (session_id, unit_tag);

-- ---------------------------------------------------------------------------
-- 23.5 knowledge_edges
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_edges (
    edge_id      TEXT PRIMARY KEY,
    session_id   TEXT REFERENCES learning_sessions(session_id) ON DELETE CASCADE,
    pre_node_id  TEXT NOT NULL,
    post_node_id TEXT NOT NULL,
    relation_type TEXT NOT NULL
                  CHECK (relation_type IN ('prerequisite', 'support', 'extension', 'related')),
    weight       REAL,
    created_at   INTEGER NOT NULL,
    FOREIGN KEY (pre_node_id)  REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
    FOREIGN KEY (post_node_id) REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
    UNIQUE (pre_node_id, post_node_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_edges_pre  ON knowledge_edges (pre_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_post ON knowledge_edges (post_node_id);

-- ---------------------------------------------------------------------------
-- 23.6 learner_knowledge_state  (core business table)
--   Cache columns (read-only, refreshed by Runtime):
--     misconception_state  <- authoritative source: misconceptions
--     next_review_at       <- authoritative source: review_items
--   evidence_stage here is the CURRENT authoritative stage for the node,
--   while assessment_results.evidence_stage is an immutable per-attempt snapshot.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS learner_knowledge_state (
    learner_id              TEXT NOT NULL REFERENCES learners(learner_id),
    node_id                 TEXT NOT NULL REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
    mastery_probability     REAL NOT NULL DEFAULT 0.0,
    misconception_state     TEXT,        -- CACHE (JSON array of active misconception ids)
    reasoning_quality       REAL,
    application_level       REAL,
    transfer_level          REAL,
    hint_dependency         REAL NOT NULL DEFAULT 0.0,
    confidence              REAL,
    confidence_calibration  REAL,
    retention_state         REAL,
    evidence_stage          TEXT NOT NULL DEFAULT 'estimated'
                            CHECK (evidence_stage IN ('estimated', 'practiced', 'demonstrated', 'retained', 'transferred')),
    last_assessed_at        INTEGER,
    next_review_at          INTEGER,     -- CACHE (authoritative source: review_items)
    updated_at              INTEGER NOT NULL,
    PRIMARY KEY (learner_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_lks_learner      ON learner_knowledge_state (learner_id);
CREATE INDEX IF NOT EXISTS idx_lks_next_review  ON learner_knowledge_state (learner_id, next_review_at);

-- ---------------------------------------------------------------------------
-- 23.7 misconceptions  (AUTHORITATIVE source for misconception state)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS misconceptions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id   TEXT NOT NULL REFERENCES learners(learner_id),
    node_id      TEXT NOT NULL REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
    misconception TEXT NOT NULL,
    severity     REAL NOT NULL DEFAULT 0.5,
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'resolved')),
    last_seen_at INTEGER NOT NULL,
    resolved_at  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_misc_learner_node ON misconceptions (learner_id, node_id, status);

-- ---------------------------------------------------------------------------
-- 23.8 assessment_items
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessment_items (
    item_id       TEXT PRIMARY KEY,
    session_id    TEXT REFERENCES learning_sessions(session_id) ON DELETE CASCADE,
    node_id       TEXT REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
    question      TEXT NOT NULL,
    question_type TEXT,
    bloom_level   TEXT,
    difficulty    REAL,
    rubric        TEXT,
    source        TEXT,
    version       TEXT NOT NULL DEFAULT '1',
    created_at    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_node ON assessment_items (node_id);

-- ---------------------------------------------------------------------------
-- 23.9 learning_attempts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS learning_attempts (
    attempt_id            TEXT PRIMARY KEY,
    session_id            TEXT NOT NULL REFERENCES learning_sessions(session_id) ON DELETE CASCADE,
    item_id               TEXT REFERENCES assessment_items(item_id),
    node_id               TEXT,
    answer                TEXT,
    response_time         REAL,
    hint_level            INTEGER NOT NULL DEFAULT 0,
    attempt_index         INTEGER NOT NULL DEFAULT 1,
    predicted_performance REAL,   -- P1 collection; may be NULL in P0
    created_at            INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_session ON learning_attempts (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_attempts_node    ON learning_attempts (session_id, node_id);

-- ---------------------------------------------------------------------------
-- 23.10 assessment_results
--   `raw_answer` is MANDATORY for audit - it must never be dropped.
--   `evidence_stage` here is an immutable snapshot of this single assessment.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessment_results (
    result_id               TEXT PRIMARY KEY,
    attempt_id              TEXT NOT NULL REFERENCES learning_attempts(attempt_id) ON DELETE CASCADE,
    correctness             REAL,
    conceptual_understanding REAL,
    reasoning_quality       REAL,
    application             REAL,
    transfer                REAL,
    hint_dependency         REAL,
    confidence              REAL,
    overall_score           REAL,
    evidence_stage          TEXT,
    assessor_type           TEXT NOT NULL
                            CHECK (assessor_type IN ('human', 'model', 'rule', 'hybrid', 'external_estimator')),
    raw_answer              TEXT NOT NULL,
    created_at              INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_results_attempt ON assessment_results (attempt_id);

-- ---------------------------------------------------------------------------
-- 23.11 transfer_results
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transfer_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id    TEXT NOT NULL REFERENCES learners(learner_id),
    node_id       TEXT NOT NULL REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
    transfer_type TEXT NOT NULL
                  CHECK (transfer_type IN ('near', 'variation', 'far', 'integrated')),
    score         REAL,
    task_context  TEXT,
    result        TEXT,
    created_at    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transfer_learner_node ON transfer_results (learner_id, node_id);

-- ---------------------------------------------------------------------------
-- 23.12 pedagogical_strategies
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogical_strategies (
    strategy_id          TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    description          TEXT,
    applicable_scenarios TEXT,
    behavior_rules       TEXT,
    version              TEXT NOT NULL DEFAULT '1'
);

-- ---------------------------------------------------------------------------
-- 23.13 pedagogical_decisions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogical_decisions (
    decision_id       TEXT PRIMARY KEY,
    session_id        TEXT NOT NULL REFERENCES learning_sessions(session_id) ON DELETE CASCADE,
    node_id           TEXT,
    trigger_event     TEXT,
    current_state     TEXT,
    candidate_actions TEXT,
    selected_policy   TEXT,
    selected_action   TEXT,
    rationale         TEXT,
    expected_outcome  TEXT,
    actual_result     TEXT,
    created_at        INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decisions_session ON pedagogical_decisions (session_id, created_at);

-- ---------------------------------------------------------------------------
-- 23.14 review_items  (SOLE authoritative source for review scheduling)
--   learner_knowledge_state.next_review_at is only a cache.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS review_items (
    review_item_id   TEXT PRIMARY KEY,
    learner_id       TEXT NOT NULL REFERENCES learners(learner_id),
    node_id          TEXT NOT NULL REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
    item_ref         TEXT,
    stability        REAL,
    difficulty       REAL,
    retrievability   REAL,
    last_review_at   INTEGER,
    next_review_at   INTEGER,
    review_count     INTEGER NOT NULL DEFAULT 0,
    last_rating      INTEGER CHECK (last_rating BETWEEN 1 AND 4),
    scheduler_version TEXT,
    created_at       INTEGER NOT NULL,
    updated_at       INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_review_learner_due ON review_items (learner_id, next_review_at);

-- ---------------------------------------------------------------------------
-- 23.15 evidence_sources
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evidence_sources (
    source_id        TEXT PRIMARY KEY,
    session_id       TEXT REFERENCES learning_sessions(session_id) ON DELETE CASCADE,
    source           TEXT NOT NULL,
    source_type      TEXT,
    authority        TEXT,
    publication_date TEXT,
    retrieved_at     INTEGER,
    last_verified    INTEGER,
    metadata         TEXT
);

-- ---------------------------------------------------------------------------
-- 23.16 benchmark_claims
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS benchmark_claims (
    claim_id            TEXT PRIMARY KEY,
    session_id          TEXT REFERENCES learning_sessions(session_id) ON DELETE CASCADE,
    source_id           TEXT REFERENCES evidence_sources(source_id),
    claim               TEXT NOT NULL,
    confidence          REAL,
    knowledge_scope     TEXT,
    conflicting_sources TEXT,
    last_verified       INTEGER,
    created_at          INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_claims_session ON benchmark_claims (session_id);

-- ---------------------------------------------------------------------------
-- 23.17 event_log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_log (
    event_id   TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    session_id TEXT,
    learner_id TEXT,
    node_id    TEXT,
    payload    TEXT,
    request_id TEXT,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_session ON event_log (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_type    ON event_log (event_type, created_at);

-- ---------------------------------------------------------------------------
-- 23.18 artifacts
--   `artifact_type = 'agent_benchmark_report'` holds the Domain Grounding
--   report referenced by learning_sessions.benchmark_report_artifact_id.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id   TEXT PRIMARY KEY,
    learner_id    TEXT,
    session_id    TEXT,
    artifact_type TEXT NOT NULL,
    path_or_uri   TEXT,
    content       TEXT,
    metadata      TEXT,
    version       TEXT NOT NULL DEFAULT '1',
    created_at    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_session ON artifacts (session_id, artifact_type);

-- ---------------------------------------------------------------------------
-- Idempotency guard for write operations (section 19.4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS request_log (
    idempotency_key TEXT PRIMARY KEY,
    tool_name       TEXT NOT NULL,
    session_id      TEXT,
    response        TEXT,
    created_at      INTEGER NOT NULL
);

-- ---------------------------------------------------------------------------
-- Schema metadata
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
