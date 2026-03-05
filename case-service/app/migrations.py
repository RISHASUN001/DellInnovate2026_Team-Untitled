"""
Safe incremental schema migrations for the case-service SQLite database.

Each migration is a (version_int, description, sql_statement) tuple.
run_migrations() checks which migrations have already been applied via the
schema_migrations table and runs only the new ones.

All ALTER TABLE statements are wrapped in try/except so that re-running the
migrations on an already-migrated database is a safe no-op.
"""
import json
from loguru import logger
import aiosqlite


MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "Add case_status column to cases (administrative routing)",
        "ALTER TABLE cases ADD COLUMN case_status TEXT NOT NULL DEFAULT 'unassigned'",
    ),
    (
        2,
        "Add work_status column to cases (operational progress)",
        "ALTER TABLE cases ADD COLUMN work_status TEXT NOT NULL DEFAULT 'not_started'",
    ),
    (
        3,
        "Backfill case_status: assigned when assigned_to IS NOT NULL",
        "UPDATE cases SET case_status = 'assigned' WHERE assigned_to IS NOT NULL AND case_status = 'unassigned'",
    ),
    (
        4,
        "Backfill work_status: in_progress when status IN (in_progress, in_review, outreach, followup)",
        """UPDATE cases SET work_status = 'in_progress'
           WHERE status IN ('in_progress','in_review','outreach','followup')
             AND work_status = 'not_started'""",
    ),
    (
        5,
        "Backfill work_status: completed when status = completed/closed",
        """UPDATE cases SET work_status = 'completed'
           WHERE status IN ('completed','closed')
             AND work_status IN ('not_started','in_progress')""",
    ),
    (
        6,
        "Backfill work_status: to_review when needs_review = 1",
        "UPDATE cases SET work_status = 'to_review' WHERE needs_review = 1 AND work_status = 'in_progress'",
    ),
    (
        7,
        "Create status_history table",
        """CREATE TABLE IF NOT EXISTS status_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id     TEXT NOT NULL,
            field       TEXT NOT NULL,
            old_value   TEXT,
            new_value   TEXT NOT NULL,
            reason      TEXT,
            actor_id    TEXT NOT NULL,
            actor_role  TEXT NOT NULL,
            created_at  TEXT NOT NULL
        )""",
    ),
    (
        8,
        "Create audit_log table",
        """CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id    TEXT NOT NULL,
            actor_role  TEXT NOT NULL,
            action      TEXT NOT NULL,
            resource    TEXT NOT NULL,
            detail      TEXT,
            created_at  TEXT NOT NULL
        )""",
    ),
    (
        9,
        "Add item_type and sub_state to checklist_items",
        "ALTER TABLE checklist_items ADD COLUMN item_type TEXT NOT NULL DEFAULT 'task'",
    ),
    (
        10,
        "Add sub_state column to checklist_items",
        "ALTER TABLE checklist_items ADD COLUMN sub_state TEXT",
    ),
    (
        11,
        "Add author_name to case_notes",
        "ALTER TABLE case_notes ADD COLUMN author_name TEXT NOT NULL DEFAULT ''",
    ),
    (
        12,
        "Create status_history index",
        "CREATE INDEX IF NOT EXISTS idx_status_history_case ON status_history(case_id, created_at DESC)",
    ),
    (
        13,
        "Create audit_log actor index",
        "CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor_id, created_at DESC)",
    ),
    (
        14,
        "Add resource column to audit_log if missing",
        "ALTER TABLE audit_log ADD COLUMN resource TEXT NOT NULL DEFAULT ''",
    ),
    (
        15,
        "Create audit_log resource index",
        "CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource, created_at DESC)",
    ),
]


async def run_migrations(db: aiosqlite.Connection) -> None:
    """Apply all pending migrations in version order."""
    # Create migration tracking table
    await db.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version    INTEGER PRIMARY KEY,
               description TEXT NOT NULL,
               applied_at  TEXT NOT NULL
           )"""
    )
    await db.commit()

    # Find already-applied versions
    async with db.execute("SELECT version FROM schema_migrations") as cur:
        applied = {row[0] for row in await cur.fetchall()}

    from datetime import datetime, timezone
    now = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for version, description, sql in sorted(MIGRATIONS, key=lambda m: m[0]):
        if version in applied:
            continue
        try:
            await db.execute(sql)
            await db.execute(
                "INSERT INTO schema_migrations (version, description, applied_at) VALUES (?,?,?)",
                (version, description, now()),
            )
            await db.commit()
            logger.info(f"Migration {version} applied: {description}")
        except Exception as exc:
            err = str(exc)
            # "duplicate column name" → column already exists; safe to mark as applied
            if "duplicate column name" in err.lower() or "already exists" in err.lower():
                await db.execute(
                    "INSERT OR IGNORE INTO schema_migrations (version, description, applied_at) VALUES (?,?,?)",
                    (version, description, now()),
                )
                await db.commit()
                logger.debug(f"Migration {version} skipped (already applied): {description}")
            else:
                logger.error(f"Migration {version} FAILED: {err}")
                raise
