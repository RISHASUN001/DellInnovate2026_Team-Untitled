import aiosqlite
from .config import settings

_db: aiosqlite.Connection | None = None

_AUDIT_CREATE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name           TEXT NOT NULL,
    actor_id            TEXT NOT NULL,
    actor_role          TEXT NOT NULL,
    payload             TEXT NOT NULL DEFAULT '{}',
    result              TEXT NOT NULL DEFAULT '{}',
    request_id          TEXT NOT NULL DEFAULT '',
    case_id             TEXT NOT NULL DEFAULT '',
    approved_plan_hash  TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL
)
"""

# Columns added in migration — each ALTER TABLE is idempotent via the try/except
_AUDIT_MIGRATIONS = [
    "ALTER TABLE audit_log ADD COLUMN request_id          TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE audit_log ADD COLUMN case_id             TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE audit_log ADD COLUMN approved_plan_hash  TEXT NOT NULL DEFAULT ''",
]

_PENDING_PLANS_CREATE = """
CREATE TABLE IF NOT EXISTS pending_plans (
    plan_hash   TEXT PRIMARY KEY,
    case_id     TEXT NOT NULL DEFAULT '',
    plan_json   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    consumed    INTEGER NOT NULL DEFAULT 0
)
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_audit_case     ON audit_log(case_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_hash     ON audit_log(approved_plan_hash)",
    "CREATE INDEX IF NOT EXISTS idx_audit_actor    ON audit_log(actor_id)",
    "CREATE INDEX IF NOT EXISTS idx_pending_hash   ON pending_plans(plan_hash)",
]


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(settings.case_db_path)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await _db.commit()

        # Create tables
        await _db.execute(_AUDIT_CREATE)
        await _db.execute(_PENDING_PLANS_CREATE)

        # Run migrations idempotently
        for sql in _AUDIT_MIGRATIONS:
            try:
                await _db.execute(sql)
            except Exception:
                pass  # column already exists

        # Indexes
        for sql in _INDEXES:
            await _db.execute(sql)

        await _db.commit()
    return _db


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None
