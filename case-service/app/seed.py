"""
Seed data: mirrors what the risk-assessment pipeline would produce.
  - 22 cases across 6 categories
  - 5 helpers (sarah_l, michael_t, rachel_w, james_k, priya_s) with uneven load
  - 3 recurring high-risk users (appear in multiple cases over time via history)
  - 8 cases get 3 ingestion snapshots each; 14 cases get 1 snapshot
  - cases.created_at  = latest ingestion timestamp
  - cases.last_signal_at = prior ingestion timestamp (NULL when only 1 snapshot)
"""
import json
from loguru import logger
from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 2, 27, 6, 0, 0, tzinfo=timezone.utc)


def ts(offset_hours: float = 0) -> str:
    return (NOW - timedelta(hours=offset_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── 22 cases ────────────────────────────────────────────────────────────────
CASES_RAW = [
    # ── Self-Harm Ideation ────────────────────────────────────────────────────
    {
        "case_id": "YD-2026-0415",
        "user_id": "daniel_lee_sg",
        "assigned_to": "sarah_l",
        "risk_score": 5,
        "category": "Self-Harm Ideation",
        "explanation_signals": {
            "risk_summary": "Critical: explicit self-harm references with farewell messages",
            "risk_indicators": [
                "Direct mentions of self-harm methods in captions",
                "Farewell messages detected in comment replies to close contacts",
                "Profile bio changed to distress-coded content within 48 h",
                "Night-time posting cluster (1 AM – 4 AM) over 5 consecutive days",
            ],
        },
        "status": "in_progress",
        "priority": "critical",
        "snapshots": 3,
    },
    {
        "case_id": "YD-2026-0411",
        "user_id": "aiden_tan_ig",
        "assigned_to": "sarah_l",
        "risk_score": 5,
        "category": "Self-Harm Ideation",
        "explanation_signals": {
            "risk_summary": "Multiple distress signals across platforms with late-night clustering",
            "risk_indicators": [
                "High-frequency distress keywords in posts and stories",
                "Cross-platform correlation with secondary Reddit account activity",
                "Temporal pattern: 11 PM – 2 AM posting cluster over 7 days",
                "DM sentiment: negative affect score 0.91/1.0",
            ],
        },
        "status": "in_review",
        "priority": "critical",
        "snapshots": 3,
    },
    {
        "case_id": "YD-2026-0388",
        "user_id": "jess_wonggg",
        "assigned_to": "rachel_w",
        "risk_score": 4,
        "category": "Self-Harm Ideation",
        "explanation_signals": {
            "risk_summary": "Escalating distress language with social withdrawal",
            "risk_indicators": [
                "Keyword cluster: burden, tired, pointless — increasing frequency",
                "Unfollowing close contacts detected over 10-day window",
                "Story engagement dropped 85% from baseline",
            ],
        },
        "status": "outreach",
        "priority": "high",
        "snapshots": 3,
    },
    # ── Cyberbullying ─────────────────────────────────────────────────────────
    {
        "case_id": "YD-2026-0413",
        "user_id": "priya_k_14",
        "assigned_to": "michael_t",
        "risk_score": 4,
        "category": "Cyberbullying",
        "explanation_signals": {
            "risk_summary": "Coordinated multi-account harassment campaign identified",
            "risk_indicators": [
                "Targeted harassment from 7 distinct accounts over 5-day period",
                "Doxxing attempt: partial address info in comments (removed by platform)",
                "Coordinated negative comments — timing gap < 2 min between accounts",
                "Youth account posting frequency dropped 100% post-incident",
            ],
        },
        "status": "in_progress",
        "priority": "high",
        "snapshots": 3,
    },
    {
        "case_id": "YD-2026-0398",
        "user_id": "chloe_teo_ig",
        "assigned_to": "michael_t",
        "risk_score": 3,
        "category": "Cyberbullying",
        "explanation_signals": {
            "risk_summary": "Toxic comment targeting across multiple posts",
            "risk_indicators": [
                "Comment toxicity score: 0.84 across 12 posts",
                "Target engagement dip 62% following incident cluster",
                "Cross-video attack pattern detected by AI classifier",
            ],
        },
        "status": "followup",
        "priority": "medium",
        "snapshots": 1,
    },
    {
        "case_id": "YD-2026-0392",
        "user_id": "kai_ng_2026",
        "assigned_to": "james_k",
        "risk_score": 3,
        "category": "Cyberbullying",
        "explanation_signals": {
            "risk_summary": "Impersonation account and reputation attack",
            "risk_indicators": [
                "Fake account using youth's photos detected (reported to platform)",
                "Screenshots of manipulated private messages being shared",
                "Fear-coded language in recent comments: 'scared', 'stop please'",
            ],
        },
        "status": "outreach",
        "priority": "medium",
        "snapshots": 1,
    },
    # ── Bullying ──────────────────────────────────────────────────────────────
    {
        "case_id": "YD-2026-0412",
        "user_id": "emma_chen_15",
        "assigned_to": "sarah_l",
        "risk_score": 3,
        "category": "Bullying",
        "explanation_signals": {
            "risk_summary": "Peer-directed harassment with sentiment shift",
            "risk_indicators": [
                "Repeated negative comments in DMs detected via metadata pattern",
                "Sentiment shift: positive → negative over 72-hour window",
                "Keyword cluster: isolation, worthless, alone — 18 occurrences",
            ],
        },
        "status": "followup",
        "priority": "medium",
        "snapshots": 1,
    },
    {
        "case_id": "YD-2026-0404",
        "user_id": "zara_ahmed_ig",
        "assigned_to": "michael_t",
        "risk_score": 4,
        "category": "Bullying",
        "explanation_signals": {
            "risk_summary": "Physical threat language requiring school coordination",
            "risk_indicators": [
                "Physical threat language in public comments: 'watch out at school'",
                "Screenshots of threatening DMs shared to story (since deleted)",
                "Fear and anxiety language frequency: 2.4× baseline",
                "Youth posting suspended after threat incident",
            ],
        },
        "status": "in_review",
        "priority": "high",
        "snapshots": 3,
    },
    {
        "case_id": "YD-2026-0401",
        "user_id": "lucas_w_ig",
        "assigned_to": None,
        "risk_score": 2,
        "category": "Bullying",
        "explanation_signals": {
            "risk_summary": "Early-stage peer exclusion signals, unassigned",
            "risk_indicators": [
                "Repetitive negative peer interaction patterns flagged by classifier",
                "Keyword cluster: excluded, mocked, why me — 9 occurrences",
            ],
        },
        "status": "new",
        "priority": "medium",
        "snapshots": 1,
    },
    {
        "case_id": "YD-2026-0377",
        "user_id": "noah_lim_sg",
        "assigned_to": "priya_s",
        "risk_score": 3,
        "category": "Bullying",
        "explanation_signals": {
            "risk_summary": "Persistent group exclusion with declining self-worth signals",
            "risk_indicators": [
                "Tagged out of group event posts repeatedly over 3 weeks",
                "Self-worth language declining: 'not good enough' mentions tripled",
                "DM reply rate to peers dropped from 78% to 12%",
            ],
        },
        "status": "in_progress",
        "priority": "medium",
        "snapshots": 1,
    },
    # ── Family Conflict ───────────────────────────────────────────────────────
    {
        "case_id": "YD-2026-0405",
        "user_id": "maya_patel_ig",
        "assigned_to": "sarah_l",
        "risk_score": 4,
        "category": "Family Conflict",
        "explanation_signals": {
            "risk_summary": "Escalating domestic instability with safety concerns",
            "risk_indicators": [
                "Escalation in emotional distress language over 48-hour window",
                "Explicit mentions of feeling unsafe at home (3 separate posts)",
                "Repeated mentions of 'leaving home' — runaway ideation risk",
                "Profile location removed — possible attempt to hide movements",
            ],
        },
        "status": "in_progress",
        "priority": "high",
        "snapshots": 3,
    },
    {
        "case_id": "YD-2026-0410",
        "user_id": "ethan_goh_ig",
        "assigned_to": "rachel_w",
        "risk_score": 3,
        "category": "Family Conflict",
        "explanation_signals": {
            "risk_summary": "Frequent family conflict mentions with runaway ideation",
            "risk_indicators": [
                "Frequent mentions of family arguments across 14 posts",
                "Posts about 'wanting to run away' — 5 instances in 2 weeks",
                "Late-night emotional venting posts (after 11 PM) — 9 occurrences",
            ],
        },
        "status": "followup",
        "priority": "medium",
        "snapshots": 1,
    },
    {
        "case_id": "YD-2026-0383",
        "user_id": "sophie_tay_99",
        "assigned_to": "james_k",
        "risk_score": 2,
        "category": "Family Conflict",
        "explanation_signals": {
            "risk_summary": "Mild family tension signals, monitoring warranted",
            "risk_indicators": [
                "Occasional frustration language referencing home situation",
                "Slight posting frequency decrease coinciding with school holidays",
            ],
        },
        "status": "new",
        "priority": "low",
        "snapshots": 1,
    },
    # ── Loneliness / Isolation ────────────────────────────────────────────────
    {
        "case_id": "YD-2026-0409",
        "user_id": "sophie_lim_ig",
        "assigned_to": "michael_t",
        "risk_score": 2,
        "category": "Loneliness / Isolation",
        "explanation_signals": {
            "risk_summary": "Gradual disengagement from social activity on platform",
            "risk_indicators": [
                "Decreased posting frequency 73% over 30-day window",
                "Shift to passive consumption behaviour (views, no engagement)",
                "Withdrawal from group interaction threads",
            ],
        },
        "status": "in_progress",
        "priority": "medium",
        "snapshots": 1,
    },
    {
        "case_id": "YD-2026-0406",
        "user_id": "marcus_loh_ig",
        "assigned_to": None,
        "risk_score": 3,
        "category": "Loneliness / Isolation",
        "explanation_signals": {
            "risk_summary": "Complete peer disengagement, invisible-feeling narrative",
            "risk_indicators": [
                "Zero peer interactions in 14-day window",
                "Story themes: 'feeling invisible', 'nobody notices me'",
                "Not tagged in any group activity posts for 3 weeks",
            ],
        },
        "status": "new",
        "priority": "medium",
        "snapshots": 1,
    },
    {
        "case_id": "YD-2026-0402",
        "user_id": "amelia_koh_ig",
        "assigned_to": None,
        "risk_score": 2,
        "category": "Loneliness / Isolation",
        "explanation_signals": {
            "risk_summary": "Early social withdrawal pattern, low urgency",
            "risk_indicators": [
                "Reduced friend-list interaction frequency — bottom 5% of cohort",
                "Posts about feeling left out of social events",
                "Declining likes and comments on own content",
            ],
        },
        "status": "new",
        "priority": "low",
        "snapshots": 1,
    },
    {
        "case_id": "YD-2026-0371",
        "user_id": "ryan_kwek_sg",
        "assigned_to": "priya_s",
        "risk_score": 3,
        "category": "Loneliness / Isolation",
        "explanation_signals": {
            "risk_summary": "Progressive isolation with identity-questioning signals",
            "risk_indicators": [
                "Follower interaction rate dropped to 3% from 21% baseline",
                "Identity-questioning posts: 'who even am I', 'does it matter'",
                "Post captions shift from social to solitary themes over 6 weeks",
            ],
        },
        "status": "outreach",
        "priority": "medium",
        "snapshots": 1,
    },
    # ── Academic Stress ───────────────────────────────────────────────────────
    {
        "case_id": "YD-2026-0408",
        "user_id": "ryan_ng_17",
        "assigned_to": "rachel_w",
        "risk_score": 1,
        "category": "Academic Stress",
        "explanation_signals": {
            "risk_summary": "Mild pre-exam stress, watch level only",
            "risk_indicators": [
                "Stress-related language uptick around examination dates",
                "Mentions of deadlines and performance pressure — 6 instances",
            ],
        },
        "status": "in_progress",
        "priority": "low",
        "snapshots": 1,
    },
    {
        "case_id": "YD-2026-0407",
        "user_id": "bella_chan_ig",
        "assigned_to": None,
        "risk_score": 2,
        "category": "Academic Stress",
        "explanation_signals": {
            "risk_summary": "Academic pressure mounting, monitoring for escalation",
            "risk_indicators": [
                "Increased stress vocabulary around examination period",
                "Sleep deprivation self-reports: 'haven't slept in 2 days'",
                "Performance anxiety indicators: 'going to fail'",
            ],
        },
        "status": "new",
        "priority": "low",
        "snapshots": 1,
    },
    {
        "case_id": "YD-2026-0403",
        "user_id": "oliver_tan_sg",
        "assigned_to": None,
        "risk_score": 1,
        "category": "Academic Stress",
        "explanation_signals": {
            "risk_summary": "Normal academic stress, no intervention needed",
            "risk_indicators": [
                "Mild complaints about homework load — age-normative",
                "Time management concerns without distress language",
            ],
        },
        "status": "completed",
        "priority": "low",
        "snapshots": 1,
    },
    {
        "case_id": "YD-2026-0396",
        "user_id": "aiden_tan_ig",  # recurring high-risk user
        "assigned_to": "sarah_l",
        "risk_score": 3,
        "category": "Academic Stress",
        "explanation_signals": {
            "risk_summary": "Previously known high-risk user showing academic stress overlay",
            "risk_indicators": [
                "Known distress-pattern user: academic pressure compounding existing risk",
                "Study-related posts increasingly hopeless in tone",
                "Mention of 'giving up on school' — 4 instances in 1 week",
            ],
        },
        "status": "in_progress",
        "priority": "high",
        "snapshots": 1,
    },
    {
        "case_id": "YD-2026-0395",
        "user_id": "daniel_lee_sg",  # recurring high-risk user
        "assigned_to": "sarah_l",
        "risk_score": 4,
        "category": "Self-Harm Ideation",
        "explanation_signals": {
            "risk_summary": "Follow-up case for previously closed high-risk file — re-escalation",
            "risk_indicators": [
                "Return of distress signals 6 weeks after prior case closure",
                "New keyword cluster: hopeless, nobody cares, last chance",
                "Bio updated with concerning imagery again",
                "Engagement with self-harm community content detected",
            ],
        },
        "status": "in_review",
        "priority": "critical",
        "snapshots": 3,
    },
]

# ─── Default checklist items per category ────────────────────────────────────
CHECKLIST_DEFAULTS = {
    "Self-Harm Ideation": [
        ("Review AI signals and verify escalation threshold", True, "human"),
        ("Attempt initial outreach via platform DM", True, "human"),
        ("Document response or non-response within 2 hours", True, "human"),
        ("Escalation considered and decision recorded", True, "human"),
        ("Refer to crisis support line if unresponsive", True, "human"),
        ("Case closed or transferred to clinical team", True, "human"),
    ],
    "Cyberbullying": [
        ("Identify perpetrator accounts for reporting", True, "human"),
        ("Draft outreach message (non-confrontational)", True, "human"),
        ("Outreach attempt logged", True, "human"),
        ("Report perpetrator accounts to platform", False, "human"),
        ("Coordinate with school liaison if school-based", False, "human"),
        ("Follow-up scheduled", True, "human"),
    ],
    "Bullying": [
        ("Review signals: frequency and severity", True, "human"),
        ("Outreach attempted", True, "human"),
        ("Response received from youth", True, "human"),
        ("School coordination required?", False, "human"),
        ("Follow-up scheduled", True, "human"),
        ("Escalation considered", True, "human"),
    ],
    "Family Conflict": [
        ("Assess immediate safety risk", True, "human"),
        ("Outreach attempted", True, "human"),
        ("Family systems referral considered", False, "human"),
        ("Safe housing options reviewed if needed", False, "human"),
        ("Follow-up scheduled", True, "human"),
        ("Case closed or escalated", True, "human"),
    ],
    "Loneliness / Isolation": [
        ("Assess degree of social withdrawal", True, "human"),
        ("Outreach attempted (warm, low-pressure)", True, "human"),
        ("Youth group or social activity referral considered", False, "human"),
        ("Response received", True, "human"),
        ("Follow-up scheduled", True, "human"),
    ],
    "Academic Stress": [
        ("Assess stress severity", True, "human"),
        ("Outreach attempted if risk ≥ 3", False, "human"),
        ("Resources shared (counselling, study support)", False, "human"),
        ("Follow-up if escalation observed", False, "human"),
        ("Case closed", True, "human"),
    ],
}


def build_history(case: dict, now: datetime) -> list[dict]:
    """Generate ingestion history rows for a case."""
    n = case["snapshots"]
    category = case["category"]
    rows = []

    base_risk = case["risk_score"]
    for i, offset_hours in enumerate([96, 48, 0][:n]):
        snap_ts = (now - timedelta(hours=offset_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        risk_at_snap = max(1, base_risk - (n - 1 - i))  # risk escalates over time
        escalation_flag = 1 if risk_at_snap >= 4 else 0
        rows.append(
            {
                "case_id": case["case_id"],
                "risk_score": risk_at_snap,
                "category": category,
                "explanation_snapshot": json.dumps(
                    {
                        **case["explanation_signals"],
                        "snapshot_index": i + 1,
                        "snapshot_total": n,
                        "risk_at_ingestion": risk_at_snap,
                    }
                ),
                "frequency_metrics": json.dumps(
                    {
                        "post_rate_per_day": round(1.8 - i * 0.3, 2),
                        "story_rate_per_day": round(0.9 + i * 0.2, 2),
                        "dm_send_rate": round(0.4 + i * 0.15, 2),
                        "sentiment_score": round(-0.3 - i * 0.15, 2),
                        "late_night_post_pct": round(0.1 + i * 0.12, 2),
                        "engagement_drop_pct": round(i * 0.22, 2),
                    }
                ),
                "action_taken": (
                    "Initial ingestion — case created"
                    if i == 0
                    else f"Re-ingestion {i+1}: risk score updated"
                ),
                "escalation_flag": escalation_flag,
                "timestamp": snap_ts,
            }
        )
    return rows


async def seed(db) -> None:
    from datetime import datetime
    import aiosqlite

    # Check if already seeded
    async with db.execute("SELECT COUNT(*) FROM cases") as cur:
        count = (await cur.fetchone())[0]
    if count > 0:
        return  # idempotent

    logger.info("Seeding mock risk-assessment data...")

    helper_users = {
        "sarah_l": "Youth Helper",
        "michael_t": "Youth Helper",
        "rachel_w": "Youth Helper",
        "james_k": "Youth Helper",
        "priya_s": "Youth Helper",
    }

    for case in CASES_RAW:
        history_rows = build_history(case, NOW)

        # created_at = latest ingestion, last_signal_at = prior ingestion
        created_at = history_rows[-1]["timestamp"]
        last_signal_at = history_rows[-2]["timestamp"] if len(history_rows) >= 2 else None

        # Derive case_status and work_status from legacy fields
        assigned = case.get("assigned_to")
        legacy_status = case["status"]
        case_status = "assigned" if assigned else "unassigned"
        if legacy_status == "new":
            work_status = "not_started"
        elif legacy_status in ("in_progress", "outreach", "followup"):
            work_status = "in_progress"
        elif legacy_status == "in_review":
            work_status = "to_review"
        elif legacy_status in ("completed", "closed"):
            work_status = "completed"
        else:
            work_status = "not_started"
        needs_review = 1 if work_status == "to_review" else 0

        await db.execute(
            """
            INSERT INTO cases
              (case_id, user_id, assigned_to, risk_score, category,
               explanation_signals, case_status, work_status,
               status, priority, needs_review,
               created_at, last_signal_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                case["case_id"],
                case["user_id"],
                assigned,
                case["risk_score"],
                case["category"],
                json.dumps(case["explanation_signals"]),
                case_status,
                work_status,
                legacy_status,
                case.get("priority", "medium"),
                needs_review,
                created_at,
                last_signal_at,
            ),
        )

        for row in history_rows:
            await db.execute(
                """
                INSERT INTO case_history
                  (case_id, risk_score, category, explanation_snapshot,
                   frequency_metrics, action_taken, escalation_flag, timestamp)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    row["case_id"],
                    row["risk_score"],
                    row["category"],
                    row["explanation_snapshot"],
                    row["frequency_metrics"],
                    row["action_taken"],
                    row["escalation_flag"],
                    row["timestamp"],
                ),
            )

        # Seed default checklist items for the category
        defaults = CHECKLIST_DEFAULTS.get(case["category"], [])
        for label, mandatory, created_by in defaults:
            # Mark outreach/escalation items with correct item_type
            if "outreach" in label.lower() or "reach out" in label.lower():
                item_type = "outreach_draft"
            elif "escalat" in label.lower() or "crisis" in label.lower() or "refer" in label.lower():
                item_type = "escalation_draft"
            else:
                item_type = "task"
            await db.execute(
                """
                INSERT INTO checklist_items
                  (case_id, parent_id, label, status, item_type, mandatory, created_by, created_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    case["case_id"],
                    None,
                    label,
                    "Not Started",
                    item_type,
                    1 if mandatory else 0,
                    created_by,
                    created_at,
                ),
            )

    await db.commit()
    logger.info(f"Seeded {len(CASES_RAW)} cases with history and checklists.")
    await seed_users(db)


# ─── Users seed ───────────────────────────────────────────────────────────────
# Mirrors src/auth/mockAuth.js MOCK_USERS so the Admin assignment dropdown
# always reflects the same staff roster as the fake-auth module.
# AUTH_SERVICE_CALL: In production, populate this table from the real identity
# provider (e.g. Azure AD / Entra sync) — remove this seed function entirely.

USERS_RAW = [
    {"employee_id": "AD-001", "user_id": "admin1",   "name": "Admin User",  "email": "admin@scs.org.sg",     "role": "Admin",        "department": "Operations",        "avatar_initials": "AU"},
    {"employee_id": "AD-002", "user_id": "admin2",   "name": "Admin Two",   "email": "admin2@scs.org.sg",    "role": "Admin",        "department": "Operations",        "avatar_initials": "AT"},
    {"employee_id": "YH-001", "user_id": "sarah_l",  "name": "Sarah Lim",   "email": "sarah@scs.org.sg",     "role": "Youth Helper", "department": "Youth Outreach",    "avatar_initials": "SL"},
    {"employee_id": "YH-002", "user_id": "michael_t","name": "Michael Tan", "email": "michael@scs.org.sg",   "role": "Youth Helper", "department": "Youth Outreach",    "avatar_initials": "MT"},
    {"employee_id": "YH-003", "user_id": "rachel_w", "name": "Rachel Wong", "email": "rachel@scs.org.sg",    "role": "Youth Helper", "department": "Community Care",    "avatar_initials": "RW"},
    {"employee_id": "YH-004", "user_id": "james_k",  "name": "James Koh",   "email": "james@scs.org.sg",     "role": "Youth Helper", "department": "Community Care",    "avatar_initials": "JK"},
    {"employee_id": "YH-005", "user_id": "priya_m",  "name": "Priya Menon", "email": "priya@scs.org.sg",     "role": "Youth Helper", "department": "Family Services",   "avatar_initials": "PM"},
]


async def seed_users(db) -> None:
    existing = await db.execute("SELECT COUNT(*) FROM users")
    row = await existing.fetchone()
    if row and row[0] > 0:
        logger.info("Users table already seeded, skipping.")
        return
    for u in USERS_RAW:
        await db.execute(
            """
            INSERT OR IGNORE INTO users
              (employee_id, user_id, name, email, role, department, avatar_initials, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (u["employee_id"], u["user_id"], u["name"], u["email"],
             u["role"], u["department"], u["avatar_initials"],
             "2026-01-01T00:00:00Z"),
        )
    await db.commit()
    logger.info(f"Seeded {len(USERS_RAW)} users.")
