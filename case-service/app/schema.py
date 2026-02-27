SCHEMA_SQL = """
-- ─── Core cases table ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cases (
    case_id         TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,          -- Instagram handle (ig_handle)
    assigned_to     TEXT,                   -- helper user_id or NULL
    risk_score      INTEGER NOT NULL CHECK(risk_score BETWEEN 1 AND 5),
    category        TEXT NOT NULL,
    explanation_signals TEXT NOT NULL DEFAULT '{}',  -- JSON: risk summary + indicators
    status          TEXT NOT NULL DEFAULT 'new'
                    CHECK(status IN ('new','in_progress','in_review','outreach','followup','completed','closed')),
    priority        TEXT NOT NULL DEFAULT 'medium'
                    CHECK(priority IN ('low','medium','high','critical')),
    needs_review    INTEGER NOT NULL DEFAULT 0,  -- 1 when any checklist item = Needs Review
    created_at      TEXT NOT NULL,          -- ISO8601 — updated on each new ingestion
    last_signal_at  TEXT                    -- ISO8601 — prior ingestion timestamp
);

-- ─── Append-only ingestion history ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS case_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id             TEXT NOT NULL REFERENCES cases(case_id),
    risk_score          INTEGER NOT NULL,
    category            TEXT NOT NULL,
    explanation_snapshot TEXT NOT NULL DEFAULT '{}',  -- full JSON snapshot at ingestion
    frequency_metrics   TEXT NOT NULL DEFAULT '{}',   -- JSON: post_rate, dm_rate, sentiment_score, etc.
    action_taken        TEXT,
    escalation_flag     INTEGER NOT NULL DEFAULT 0,
    timestamp           TEXT NOT NULL                 -- ISO8601 ingestion time
);
CREATE INDEX IF NOT EXISTS idx_history_case ON case_history(case_id, timestamp DESC);

-- ─── Enhanced checklist ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS checklist_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     TEXT NOT NULL REFERENCES cases(case_id),
    parent_id   INTEGER REFERENCES checklist_items(id),  -- NULL = top-level
    label       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Not Started'
                CHECK(status IN ('Not Started','In Progress','Completed','Needs Review')),
    mandatory   INTEGER NOT NULL DEFAULT 0,
    created_by  TEXT NOT NULL DEFAULT 'human',  -- 'agent' | 'human'
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checklist_case ON checklist_items(case_id);

-- ─── Case notes / comments ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS case_notes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id          TEXT NOT NULL REFERENCES cases(case_id),
    checklist_item_id INTEGER REFERENCES checklist_items(id),  -- optional: attached to checklist item
    author_id        TEXT NOT NULL,
    content          TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_case ON case_notes(case_id);

-- ─── Reassignment requests ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reassignment_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id      TEXT NOT NULL REFERENCES cases(case_id),
    requested_by TEXT NOT NULL,
    requested_to TEXT,          -- target helper, or NULL if "any available"
    reason       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK(status IN ('pending','approved','rejected')),
    reviewed_by  TEXT,
    created_at   TEXT NOT NULL,
    reviewed_at  TEXT
);

-- ─── follow-ups ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS followups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     TEXT NOT NULL REFERENCES cases(case_id),
    scheduled_at TEXT NOT NULL,  -- ISO8601
    note        TEXT,
    created_by  TEXT NOT NULL,
    completed   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
"""
