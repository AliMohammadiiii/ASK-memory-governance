PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS memory_items (
    id               INTEGER PRIMARY KEY,
    type             TEXT    NOT NULL CHECK(type IN ('stable_pref','transient_pref','episodic_fact')),
    text             TEXT    NOT NULL,
    normalized_value TEXT,
    status           TEXT    NOT NULL DEFAULT 'active'
                             CHECK(status IN ('active','superseded')),
    confidence       REAL    NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    valid_from       TEXT,
    supersedes_id    INTEGER REFERENCES memory_items(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_memory_items_status ON memory_items(status);
CREATE INDEX IF NOT EXISTS ix_memory_items_type ON memory_items(type);
CREATE INDEX IF NOT EXISTS ix_memory_items_supersedes ON memory_items(supersedes_id);

CREATE TABLE IF NOT EXISTS evidence_spans (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT    NOT NULL,
    turn_index  INTEGER NOT NULL,
    start_char  INTEGER,
    end_char    INTEGER,
    text        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS memory_evidence (
    memory_id   INTEGER NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
    evidence_id INTEGER NOT NULL REFERENCES evidence_spans(id) ON DELETE CASCADE,
    PRIMARY KEY (memory_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS memory_relations (
    id             INTEGER PRIMARY KEY,
    from_memory_id INTEGER NOT NULL REFERENCES memory_items(id),
    to_memory_id   INTEGER NOT NULL REFERENCES memory_items(id),
    relation       TEXT    NOT NULL CHECK(relation IN ('supports','contradicts','supersedes')),
    created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(from_memory_id, to_memory_id, relation)
);

CREATE TABLE IF NOT EXISTS action_log (
    id                  INTEGER PRIMARY KEY,
    timestamp           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    action              TEXT NOT NULL CHECK(action IN ('Keep','Supersede','Abstain')),
    candidate_text      TEXT NOT NULL,
    candidate_id        INTEGER,
    prior_memory_id     INTEGER REFERENCES memory_items(id),
    resulting_memory_id INTEGER REFERENCES memory_items(id),
    feature_c           REAL CHECK(feature_c IS NULL OR (feature_c >= 0.0 AND feature_c <= 1.0)),
    feature_e           REAL CHECK(feature_e IS NULL OR (feature_e >= 0.0 AND feature_e <= 1.0)),
    feature_f           REAL CHECK(feature_f IS NULL OR (feature_f >= 0.0 AND feature_f <= 1.0)),
    feature_r           REAL CHECK(feature_r IS NULL OR (feature_r >= -1.0 AND feature_r <= 1.0)),
    feature_rho         REAL CHECK(feature_rho IS NULL OR (feature_rho >= 0.0 AND feature_rho <= 1.0)),
    s_rev               REAL,
    s_abs               REAL,
    theta_sup           REAL,
    theta_abs           REAL,
    rationale           TEXT NOT NULL
);
