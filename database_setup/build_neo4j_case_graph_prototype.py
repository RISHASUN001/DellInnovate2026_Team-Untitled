#!/usr/bin/env python3
"""
Build a richer Neo4j prototype graph for SCS case intelligence.

This script can optionally seed MongoDB with demo-only prototype cases and then
load both real and prototype data into Neo4j Aura.

Design goals:
- Preserve existing OAuth assignee emails on existing cases.
- Create relational, queryable timelines for each case using scs_case_history.
- Cluster similar cases across shared stressors such as academic stress and war.
- Reuse ai_explanation_signals and recommended_actions when available.

Example:
python database_setup/build_neo4j_case_graph_prototype.py \
  --seed-prototype-data \
  --reset \
  --insecure-skip-verify
"""

from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import combinations
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from dotenv import load_dotenv
from neo4j import GraphDatabase
from pymongo import MongoClient, ReturnDocument


SYMPTOM_KEYWORD_MAP: Dict[str, List[str]] = {
    "depression": ["sad", "hopeless", "depress", "empty", "worthless", "numb"],
    "self_harm": ["self-harm", "self harm", "cut", "hurt myself", "suicid", "bleeding"],
    "anxiety": ["anx", "panic", "overwhelm", "fear", "spiral", "tension"],
    "isolation": ["isolat", "alone", "withdraw", "no friends", "lonely", "left out"],
    "stress": ["stress", "burnout", "pressure", "exhaust", "overloaded"],
    "substance": ["substance", "drug", "alcohol", "addict", "smoke", "drinking"],
    "trauma": ["trauma", "abuse", "flashback", "trigger", "unsafe"],
    "sleep_issues": ["sleep", "insomnia", "nightmare", "awake", "restless"],
}

STRESSOR_KEYWORD_MAP: Dict[str, List[str]] = {
    "academic_stress": ["academic", "exam", "grades", "school", "college", "university", "study", "scholarship"],
    "war_conflict": ["war", "conflict", "bomb", "missile", "military", "gaza", "ukraine", "airstrike", "displacement"],
    "family_pressure": ["family", "parents", "mother", "father", "home pressure", "household", "expectation"],
    "financial_stress": ["money", "rent", "fees", "debt", "financial", "job", "income", "bills"],
    "relationship_distress": ["breakup", "relationship", "partner", "friendship", "rejected"],
    "identity_pressure": ["identity", "belonging", "body image", "gender", "sexuality", "fit in"],
    "grief_loss": ["grief", "loss", "died", "funeral", "mourning", "miss them"],
    "social_isolation": ["isolat", "lonely", "alone", "withdraw", "no one", "left out"],
    "safety_trauma": ["unsafe", "abuse", "violence", "trauma", "fear at home", "threat"],
}

POSITIVE_MARKERS = ["improv", "support", "stable", "positive", "connected", "engaging", "better", "calmer"]
NEGATIVE_MARKERS = ["panic", "hopeless", "unsafe", "war", "self-harm", "alone", "overwhelmed", "burnout", "fear"]

PROTOTYPE_CASE_PREFIX = "CASE_PROTO_2026_"


@dataclass
class CaseRecord:
    case_id: str
    user_id: str
    assigned_to: Optional[str]
    case_status: Optional[str]
    work_status: Optional[str]
    priority: Optional[str]
    category: Optional[str]
    current_risk_score: float
    current_risk_signals: str
    ai_explanation: str
    ai_explanation_paragraph: str
    ai_explanation_signals: List[str]
    recommended_actions_paragraph: str
    recommended_actions: List[str]
    platform: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@dataclass
class PrototypeCase:
    case_doc: Dict[str, Any]
    history_docs: List[Dict[str, Any]]
    custom_checklist: List[Dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build rich SCS Neo4j prototype graph")
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", ""))
    parser.add_argument("--neo4j-username", default=os.getenv("NEO4J_USERNAME", ""))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", ""))
    parser.add_argument("--neo4j-database", default=os.getenv("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--mongo-uri", default=os.getenv("MONGODB_URI", ""))
    parser.add_argument("--mongo-db", default=os.getenv("SCS_DB_NAME", "dellinnovate"))
    parser.add_argument("--limit-cases", type=int, default=500)
    parser.add_argument("--similarity-threshold", type=float, default=0.28)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--seed-prototype-data", action="store_true")
    parser.add_argument("--prototype-case-count", type=int, default=8)
    parser.add_argument("--fake-if-empty", action="store_true")
    parser.add_argument(
        "--insecure-skip-verify",
        action="store_true",
        help="Use neo4j+ssc or bolt+ssc to bypass local TLS chain issues for prototype runs",
    )
    return parser.parse_args()


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_text(value)).strip("_") or "unknown"


def listify(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [part.strip(" -\u2022") for part in re.split(r"[\n;,]", value) if part.strip()]
    return [str(value).strip()]


def text_contains_any(text: str, patterns: Sequence[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def extract_topics(texts: Iterable[str], keyword_map: Dict[str, List[str]], fallback: str) -> List[str]:
    joined = normalize_text(" ".join([text for text in texts if text]))
    found = [name for name, patterns in keyword_map.items() if text_contains_any(joined, patterns)]
    if not found:
        return [fallback]
    return sorted(set(found))


def extract_symptoms(texts: Iterable[str]) -> List[str]:
    return extract_topics(texts, SYMPTOM_KEYWORD_MAP, "general_distress")


def extract_stressors(texts: Iterable[str]) -> List[str]:
    return extract_topics(texts, STRESSOR_KEYWORD_MAP, "general_distress")


def infer_sentiment_label(text: str, risk_score: float, delta_from_prev: float) -> str:
    normalized = normalize_text(text)
    positive_hits = sum(1 for marker in POSITIVE_MARKERS if marker in normalized)
    negative_hits = sum(1 for marker in NEGATIVE_MARKERS if marker in normalized)

    if risk_score >= 85 or negative_hits >= 2 or delta_from_prev >= 10:
        return "critical_negative"
    if risk_score >= 60 or negative_hits > positive_hits:
        return "negative"
    if positive_hits >= 2 or risk_score <= 25 or delta_from_prev <= -10:
        return "positive"
    return "mixed"


def period_bucket(dt_value: Optional[datetime]) -> str:
    if not dt_value:
        return "unknown_period"
    iso_year, iso_week, _ = dt_value.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def category_group(category: Optional[str]) -> str:
    lower = normalize_text(category or "")
    if "critical" in lower:
        return "critical"
    if "high" in lower:
        return "high"
    if "moderate" in lower:
        return "moderate"
    if "low" in lower:
        return "low"
    return "unknown"


def get_next_id(db: Any, collection_name: str, field_name: str) -> int:
    result = db["counters"].find_one_and_update(
        {"_id": f"{collection_name}_{field_name}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(result["seq"])


def ensure_default_templates(db: Any) -> None:
    templates_col = db["scs_checklist_templates"]
    if templates_col.count_documents({}) > 0:
        return
    templates_col.insert_many(
        [
            {"template_id": 1, "label": "Case Analysis Completed", "is_mandatory": True, "display_order": 1, "is_active": True, "created_at": datetime.now(timezone.utc)},
            {"template_id": 2, "label": "Outreach Attempted", "is_mandatory": True, "display_order": 2, "is_active": True, "created_at": datetime.now(timezone.utc)},
            {"template_id": 3, "label": "Response Received", "is_mandatory": True, "display_order": 3, "is_active": True, "created_at": datetime.now(timezone.utc)},
            {"template_id": 4, "label": "Follow-up Scheduled", "is_mandatory": True, "display_order": 4, "is_active": True, "created_at": datetime.now(timezone.utc)},
        ]
    )


def build_prototype_cases(limit_cases: int) -> List[PrototypeCase]:
    now = datetime.now(timezone.utc)
    catalog: List[PrototypeCase] = [
        PrototypeCase(
            case_doc={
                "case_id": f"{PROTOTYPE_CASE_PREFIX}001",
                "user_id": "@proto_exam_burnout",
                "current_risk_score": 81.0,
                "current_category": "High Risk - Academic Stress",
                "current_risk_signals": "Exam pressure, insomnia, fear of failing scholarship review, panic before classes.",
                "ai_explanation": "The case shows escalating academic stress with insomnia, panic responses before exams, and identity attachment to grades. Distress increased over the last three snapshots as deadlines accumulated and sleep quality dropped.",
                "ai_explanation_paragraph": "Escalating academic stress is the main driver, with insomnia and panic intensifying around deadlines and scholarship pressure.",
                "ai_explanation_signals": [
                    "Frequent references to exams and scholarship pressure",
                    "Sleep disruption before classes and assessments",
                    "Panic-like responses linked to performance expectations",
                ],
                "recommended_actions_paragraph": "A structured school-support response is appropriate, including counselor referral, workload planning, and short-interval follow-up.",
                "recommended_actions": [
                    "Refer to school counselor",
                    "Create exam-week coping checklist",
                    "Schedule follow-up in 72 hours",
                ],
                "priority": "high",
                "platform": "Instagram",
            },
            history_docs=[
                {"offset_days": 18, "risk_score": 56.0, "category": "Moderate Risk - Academic Stress", "risk_signals": "Late-night study posts, mild worry about grades, reduced sleep."},
                {"offset_days": 10, "risk_score": 71.0, "category": "High Risk - Academic Stress", "risk_signals": "Panic before exams, fear of losing scholarship, skipping meals to study."},
                {"offset_days": 2, "risk_score": 81.0, "category": "High Risk - Academic Stress", "risk_signals": "Exam pressure causing insomnia and shaking before class presentations."},
            ],
            custom_checklist=[
                {"label": "School counselor referral prepared", "completed": True, "is_mandatory": False},
                {"label": "Exam-week safety and coping plan drafted", "completed": False, "is_mandatory": False},
            ],
        ),
        PrototypeCase(
            case_doc={
                "case_id": f"{PROTOTYPE_CASE_PREFIX}002",
                "user_id": "@proto_war_anxiety",
                "current_risk_score": 76.0,
                "current_category": "High Risk - War-Related Anxiety",
                "current_risk_signals": "Compulsive doomscrolling about war updates, fear for family abroad, nightmares after watching conflict videos.",
                "ai_explanation": "The dominant pattern is war-related anxiety. The youth is repeatedly consuming conflict media, expressing fear for relatives in the region, and showing sleep deterioration after exposure to violent updates.",
                "ai_explanation_paragraph": "War and conflict exposure appear to be the central pain point, amplified by family ties abroad and repeated exposure to distressing news.",
                "ai_explanation_signals": [
                    "Repeated mention of war updates and bombings",
                    "Nightmares and sleep disruption after conflict content",
                    "Fear for family safety abroad",
                ],
                "recommended_actions_paragraph": "Interventions should focus on media-boundary planning, grounding, and documenting escalation risk if sleep disruption worsens.",
                "recommended_actions": [
                    "Create media-boundary plan",
                    "Document family-safety concerns",
                    "Schedule grounding and sleep hygiene follow-up",
                ],
                "priority": "high",
                "platform": "Instagram",
            },
            history_docs=[
                {"offset_days": 20, "risk_score": 48.0, "category": "Moderate Risk - General Distress", "risk_signals": "Concerned about conflict news and checking updates late at night."},
                {"offset_days": 9, "risk_score": 66.0, "category": "Moderate Risk - War-Related Anxiety", "risk_signals": "Frequent war updates, fear for cousins abroad, difficulty sleeping."},
                {"offset_days": 1, "risk_score": 76.0, "category": "High Risk - War-Related Anxiety", "risk_signals": "Nightmares after war footage, fear for family safety, persistent doomscrolling."},
            ],
            custom_checklist=[
                {"label": "Conflict-media intake boundaries discussed", "completed": True, "is_mandatory": False},
                {"label": "Family-safety support resources documented", "completed": False, "is_mandatory": False},
            ],
        ),
        PrototypeCase(
            case_doc={
                "case_id": f"{PROTOTYPE_CASE_PREFIX}003",
                "user_id": "@proto_family_grades",
                "current_risk_score": 69.0,
                "current_category": "Moderate Risk - Family Pressure",
                "current_risk_signals": "Parental pressure around grades, shame after comparing with siblings, feeling trapped between family expectations and burnout.",
                "ai_explanation": "Family expectation and academic comparison are reinforcing each other. The user links self-worth to grades and reports shame after repeated comparisons with siblings.",
                "ai_explanation_paragraph": "This case sits at the intersection of family pressure and academic stress, with self-worth tied to performance at home.",
                "ai_explanation_signals": [
                    "Direct references to parental expectations",
                    "Sibling comparison linked to shame",
                    "Performance pressure reducing emotional resilience",
                ],
                "recommended_actions_paragraph": "The most credible next steps are supportive documentation, guided conversation planning, and burnout monitoring.",
                "recommended_actions": [
                    "Prepare guided family-conversation notes",
                    "Track burnout indicators weekly",
                    "Offer self-worth reframing resources",
                ],
                "priority": "medium",
                "platform": "Instagram",
            },
            history_docs=[
                {"offset_days": 17, "risk_score": 51.0, "category": "Moderate Risk - Academic Stress", "risk_signals": "Stressed by grades and upcoming report cards."},
                {"offset_days": 7, "risk_score": 62.0, "category": "Moderate Risk - Family Pressure", "risk_signals": "Parents comparing with siblings and pushing higher scores."},
                {"offset_days": 1, "risk_score": 69.0, "category": "Moderate Risk - Family Pressure", "risk_signals": "Feeling trapped between family expectations and school burnout."},
            ],
            custom_checklist=[
                {"label": "Family-pressure coping plan drafted", "completed": False, "is_mandatory": False},
            ],
        ),
        PrototypeCase(
            case_doc={
                "case_id": f"{PROTOTYPE_CASE_PREFIX}004",
                "user_id": "@proto_displacement_fear",
                "current_risk_score": 73.0,
                "current_category": "Moderate Risk - Conflict Stress",
                "current_risk_signals": "Fear after displacement stories, guilt about being safe while relatives are in conflict, withdrawal from friends.",
                "ai_explanation": "The case reflects conflict-driven distress with survivor guilt, social withdrawal, and persistent exposure to traumatic war narratives.",
                "ai_explanation_paragraph": "War-related stress is combining with isolation and guilt, creating a pattern of sustained emotional overload.",
                "ai_explanation_signals": [
                    "Displacement stories triggering guilt",
                    "Withdrawal from normal social interaction",
                    "Repeated exposure to traumatic conflict content",
                ],
                "recommended_actions_paragraph": "Recommended steps include documenting trauma triggers and building safe-contact routines.",
                "recommended_actions": [
                    "Document trauma triggers tied to conflict content",
                    "Create trusted-contact outreach plan",
                    "Schedule wellness follow-up within one week",
                ],
                "priority": "high",
                "platform": "Instagram",
            },
            history_docs=[
                {"offset_days": 14, "risk_score": 57.0, "category": "Moderate Risk - General Distress", "risk_signals": "Watching war clips and feeling heavy afterward."},
                {"offset_days": 6, "risk_score": 68.0, "category": "Moderate Risk - Conflict Stress", "risk_signals": "Guilt about being safe while relatives face war and displacement."},
                {"offset_days": 2, "risk_score": 73.0, "category": "Moderate Risk - Conflict Stress", "risk_signals": "Withdrawing from friends after war-related guilt and fear spikes."},
            ],
            custom_checklist=[
                {"label": "Trusted-contact outreach list created", "completed": True, "is_mandatory": False},
            ],
        ),
        PrototypeCase(
            case_doc={
                "case_id": f"{PROTOTYPE_CASE_PREFIX}005",
                "user_id": "@proto_work_study_money",
                "current_risk_score": 64.0,
                "current_category": "Moderate Risk - Financial Stress",
                "current_risk_signals": "Working extra shifts to pay fees, missing classes, exhaustion from juggling income and coursework.",
                "ai_explanation": "Financial strain is the main pain point. The youth is balancing work and study, missing classes, and showing signs of exhaustion tied to unpaid fees and job insecurity.",
                "ai_explanation_paragraph": "Money stress is driving missed classes and fatigue, and the case overlaps with academic pressure due to unstable work-study balance.",
                "ai_explanation_signals": [
                    "Direct concern over tuition and fees",
                    "Missed classes due to work shifts",
                    "Exhaustion from work-study overload",
                ],
                "recommended_actions_paragraph": "A practical support path should include resource referral, class catch-up planning, and exhaustion monitoring.",
                "recommended_actions": [
                    "Provide fee-support resource list",
                    "Create work-study catch-up plan",
                    "Monitor exhaustion and attendance drop",
                ],
                "priority": "medium",
                "platform": "Instagram",
            },
            history_docs=[
                {"offset_days": 16, "risk_score": 43.0, "category": "Low Risk - Financial Stress", "risk_signals": "Posting about extra shifts and being tired after work."},
                {"offset_days": 8, "risk_score": 55.0, "category": "Moderate Risk - Financial Stress", "risk_signals": "Worrying about fees and missing lectures because of work."},
                {"offset_days": 1, "risk_score": 64.0, "category": "Moderate Risk - Financial Stress", "risk_signals": "Exhausted from juggling fees, work shifts, and coursework deadlines."},
            ],
            custom_checklist=[
                {"label": "Resource referral list for financial support prepared", "completed": False, "is_mandatory": False},
            ],
        ),
        PrototypeCase(
            case_doc={
                "case_id": f"{PROTOTYPE_CASE_PREFIX}006",
                "user_id": "@proto_isolation_identity",
                "current_risk_score": 67.0,
                "current_category": "Moderate Risk - Social Isolation",
                "current_risk_signals": "Feeling out of place, avoiding friends, identity-based comments causing shame and loneliness.",
                "ai_explanation": "The case combines identity pressure and social isolation. Shame responses follow negative peer interactions, and the user has reduced social contact over time.",
                "ai_explanation_paragraph": "Identity-related stress is feeding isolation and low belonging, which may increase future vulnerability if support remains low.",
                "ai_explanation_signals": [
                    "Repeated statements about not fitting in",
                    "Withdrawal after identity-based peer comments",
                    "Loneliness increasing over time",
                ],
                "recommended_actions_paragraph": "Support should focus on belonging, safe-peer mapping, and steady check-ins.",
                "recommended_actions": [
                    "Map safe-peer support options",
                    "Document identity-based triggers",
                    "Schedule weekly belonging check-in",
                ],
                "priority": "medium",
                "platform": "Instagram",
            },
            history_docs=[
                {"offset_days": 19, "risk_score": 46.0, "category": "Low Risk - General Distress", "risk_signals": "Feeling left out occasionally and keeping distance from group chats."},
                {"offset_days": 9, "risk_score": 58.0, "category": "Moderate Risk - Social Isolation", "risk_signals": "Avoiding friends after identity-based comments and feeling ashamed."},
                {"offset_days": 2, "risk_score": 67.0, "category": "Moderate Risk - Social Isolation", "risk_signals": "Loneliness and not fitting in are leading to sustained withdrawal."},
            ],
            custom_checklist=[
                {"label": "Safe-peer support mapping started", "completed": True, "is_mandatory": False},
            ],
        ),
        PrototypeCase(
            case_doc={
                "case_id": f"{PROTOTYPE_CASE_PREFIX}007",
                "user_id": "@proto_grief_relationship",
                "current_risk_score": 61.0,
                "current_category": "Moderate Risk - Grief and Loss",
                "current_risk_signals": "Breakup triggered grief spiral, missing routine, trouble sleeping, loss language in captions.",
                "ai_explanation": "The case shows relationship distress that shifted into grief-like rumination and sleep disruption. The language indicates loss processing rather than acute self-harm risk, but sustained monitoring is warranted.",
                "ai_explanation_paragraph": "The core stressor is grief and relationship loss, with sleep issues and isolation as secondary effects.",
                "ai_explanation_signals": [
                    "Loss language appearing repeatedly in captions",
                    "Sleep disruption after breakup",
                    "Withdrawal from normal routines",
                ],
                "recommended_actions_paragraph": "The best fit is structured grief check-ins, routine rebuilding, and sleep monitoring.",
                "recommended_actions": [
                    "Start grief-focused check-in notes",
                    "Plan routine rebuilding steps",
                    "Monitor sleep deterioration",
                ],
                "priority": "medium",
                "platform": "Instagram",
            },
            history_docs=[
                {"offset_days": 15, "risk_score": 39.0, "category": "Low Risk - Relationship Distress", "risk_signals": "Upset after breakup but still attending normal routines."},
                {"offset_days": 5, "risk_score": 54.0, "category": "Moderate Risk - Grief and Loss", "risk_signals": "Loss language increasing and difficulty sleeping after breakup."},
                {"offset_days": 1, "risk_score": 61.0, "category": "Moderate Risk - Grief and Loss", "risk_signals": "Breakup grief spiral causing poor sleep and withdrawal from routines."},
            ],
            custom_checklist=[
                {"label": "Sleep and grief check-in planned", "completed": False, "is_mandatory": False},
            ],
        ),
        PrototypeCase(
            case_doc={
                "case_id": f"{PROTOTYPE_CASE_PREFIX}008",
                "user_id": "@proto_academic_war_overlap",
                "current_risk_score": 79.0,
                "current_category": "High Risk - Overlapping Stressors",
                "current_risk_signals": "Can not focus on school because of war news, fear for relatives, falling grades, and panic during lectures.",
                "ai_explanation": "This case overlaps academic stress and war-related anxiety. Fear for relatives abroad is disrupting concentration, which then worsens school pressure and panic in academic settings.",
                "ai_explanation_paragraph": "The strongest pattern is overlap between war anxiety and academic decline, making this a useful bridge case for cross-cluster analysis.",
                "ai_explanation_signals": [
                    "War-related fear disrupting academic focus",
                    "Falling grades after conflict escalation",
                    "Panic symptoms during lectures",
                ],
                "recommended_actions_paragraph": "This case benefits from a blended intervention path covering media boundaries, school support, and panic management.",
                "recommended_actions": [
                    "Coordinate school support for missed focus periods",
                    "Limit distressing conflict content before class",
                    "Track panic episodes in academic settings",
                ],
                "priority": "high",
                "platform": "Instagram",
            },
            history_docs=[
                {"offset_days": 21, "risk_score": 52.0, "category": "Moderate Risk - General Distress", "risk_signals": "War news making it hard to focus some nights."},
                {"offset_days": 11, "risk_score": 68.0, "category": "Moderate Risk - Overlapping Stressors", "risk_signals": "Fear for relatives abroad is affecting study sessions and grades."},
                {"offset_days": 2, "risk_score": 79.0, "category": "High Risk - Overlapping Stressors", "risk_signals": "War anxiety and falling grades now causing panic during lectures."},
            ],
            custom_checklist=[
                {"label": "School support request drafted", "completed": True, "is_mandatory": False},
                {"label": "Conflict-content boundary plan added", "completed": False, "is_mandatory": False},
            ],
        ),
    ]
    return catalog[: max(0, min(limit_cases, len(catalog)))]


def seed_prototype_data(mongo_uri: str, mongo_db: str, prototype_case_count: int) -> List[str]:
    if not mongo_uri:
        raise ValueError("MongoDB connection is required to seed prototype data")

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
    db = client[mongo_db]
    ensure_default_templates(db)

    templates = list(db["scs_checklist_templates"].find({"is_active": True}, {"_id": 0}).sort("display_order", 1))
    prototype_cases = build_prototype_cases(prototype_case_count)
    prototype_case_ids = [item.case_doc["case_id"] for item in prototype_cases]

    db["scs_case_history"].delete_many({"case_id": {"$in": prototype_case_ids}})
    db["scs_checklist"].delete_many({"case_id": {"$in": prototype_case_ids}})

    for item in prototype_cases:
        case_doc = dict(item.case_doc)
        now = datetime.now(timezone.utc)
        case_doc["updated_at"] = now

        db["scs_cases"].update_one(
            {"case_id": case_doc["case_id"]},
            {
                "$setOnInsert": {
                    "case_id": case_doc["case_id"],
                    "user_id": case_doc["user_id"],
                    "assigned_to": None,
                    "case_status": "unassigned",
                    "work_status": "not_started",
                    "priority": case_doc.get("priority", "medium"),
                    "platform": case_doc.get("platform", "Instagram"),
                    "created_at": now,
                },
                "$set": {
                    "current_risk_score": case_doc["current_risk_score"],
                    "current_category": case_doc["current_category"],
                    "current_risk_signals": case_doc["current_risk_signals"],
                    "ai_explanation": case_doc["ai_explanation"],
                    "ai_explanation_paragraph": case_doc["ai_explanation_paragraph"],
                    "ai_explanation_signals": case_doc["ai_explanation_signals"],
                    "recommended_actions_paragraph": case_doc["recommended_actions_paragraph"],
                    "recommended_actions": case_doc["recommended_actions"],
                    "updated_at": now,
                },
            },
            upsert=True,
        )

        for history in item.history_docs:
            ingestion_date = now - timedelta(days=int(history["offset_days"]))
            db["scs_case_history"].insert_one(
                {
                    "history_id": get_next_id(db, "scs_case_history", "history_id"),
                    "case_id": case_doc["case_id"],
                    "risk_score": float(history["risk_score"]),
                    "category": history["category"],
                    "risk_signals": history["risk_signals"],
                    "ingestion_date": ingestion_date,
                }
            )

        display_order = 1
        for template in templates:
            completed = display_order <= 2
            db["scs_checklist"].insert_one(
                {
                    "checklist_item_id": get_next_id(db, "scs_checklist", "checklist_item_id"),
                    "case_id": case_doc["case_id"],
                    "template_id": template.get("template_id"),
                    "label": template.get("label", "Checklist Item"),
                    "is_mandatory": bool(template.get("is_mandatory", True)),
                    "completed": completed,
                    "comments": [],
                    "completed_at": now if completed else None,
                    "completed_by": None,
                    "display_order": display_order,
                    "created_at": now,
                }
            )
            display_order += 1

        for custom_item in item.custom_checklist:
            db["scs_checklist"].insert_one(
                {
                    "checklist_item_id": get_next_id(db, "scs_checklist", "checklist_item_id"),
                    "case_id": case_doc["case_id"],
                    "template_id": None,
                    "label": custom_item["label"],
                    "is_mandatory": bool(custom_item.get("is_mandatory", False)),
                    "completed": bool(custom_item.get("completed", False)),
                    "comments": [],
                    "completed_at": now if custom_item.get("completed") else None,
                    "completed_by": None,
                    "display_order": display_order,
                    "created_at": now,
                }
            )
            display_order += 1

    return prototype_case_ids


def to_case_record(doc: Dict[str, Any]) -> CaseRecord:
    return CaseRecord(
        case_id=str(doc.get("case_id", "")).strip(),
        user_id=str(doc.get("user_id", "unknown")).strip(),
        assigned_to=(str(doc.get("assigned_to")).strip() if doc.get("assigned_to") else None),
        case_status=doc.get("case_status"),
        work_status=doc.get("work_status"),
        priority=doc.get("priority"),
        category=doc.get("current_category") or doc.get("category"),
        current_risk_score=float(doc.get("current_risk_score", 0) or 0),
        current_risk_signals=str(doc.get("current_risk_signals", "") or ""),
        ai_explanation=str(doc.get("ai_explanation", "") or ""),
        ai_explanation_paragraph=str(doc.get("ai_explanation_paragraph", "") or ""),
        ai_explanation_signals=listify(doc.get("ai_explanation_signals")),
        recommended_actions_paragraph=str(doc.get("recommended_actions_paragraph", "") or ""),
        recommended_actions=listify(doc.get("recommended_actions")),
        platform=doc.get("platform"),
        created_at=parse_dt(doc.get("created_at")),
        updated_at=parse_dt(doc.get("updated_at")),
    )


def fake_dataset() -> Dict[str, List[Dict[str, Any]]]:
    prototypes = build_prototype_cases(4)
    cases = []
    history = []
    checklist = []
    now = datetime.now(timezone.utc)
    checklist_id = 1
    history_id = 1
    for item in prototypes:
        doc = dict(item.case_doc)
        doc["assigned_to"] = None
        doc["case_status"] = "unassigned"
        doc["work_status"] = "not_started"
        doc["created_at"] = now
        doc["updated_at"] = now
        cases.append(doc)
        for hist in item.history_docs:
            history.append(
                {
                    "history_id": history_id,
                    "case_id": item.case_doc["case_id"],
                    "risk_score": hist["risk_score"],
                    "category": hist["category"],
                    "risk_signals": hist["risk_signals"],
                    "ingestion_date": now - timedelta(days=int(hist["offset_days"])),
                }
            )
            history_id += 1
        for label in ["Case Analysis Completed", "Outreach Attempted"]:
            checklist.append(
                {
                    "checklist_item_id": checklist_id,
                    "case_id": item.case_doc["case_id"],
                    "label": label,
                    "is_mandatory": True,
                    "completed": label == "Case Analysis Completed",
                    "display_order": checklist_id,
                }
            )
            checklist_id += 1
    return {"cases": cases, "history": history, "checklist": checklist, "reviews": [], "reassignments": []}


def load_mongo_data(mongo_uri: str, mongo_db: str, limit_cases: int, fake_if_empty: bool) -> Dict[str, List[Dict[str, Any]]]:
    if not mongo_uri:
        if fake_if_empty:
            return fake_dataset()
        raise ValueError("MONGODB_URI is required unless --fake-if-empty is used")

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
    db = client[mongo_db]
    cases = list(db["scs_cases"].find({}, {"_id": 0}).sort("created_at", -1).limit(limit_cases))
    if not cases:
        if fake_if_empty:
            return fake_dataset()
        raise ValueError("No cases found in MongoDB")

    case_ids = [case.get("case_id") for case in cases if case.get("case_id")]
    return {
        "cases": cases,
        "checklist": list(db["scs_checklist"].find({"case_id": {"$in": case_ids}}, {"_id": 0})),
        "history": list(db["scs_case_history"].find({"case_id": {"$in": case_ids}}, {"_id": 0})),
        "reviews": list(db["scs_review_requests"].find({"case_id": {"$in": case_ids}}, {"_id": 0})),
        "reassignments": list(db["scs_reassignment_requests"].find({"case_id": {"$in": case_ids}}, {"_id": 0})),
    }


def score_outcome(history_docs: List[Dict[str, Any]], checklist_docs: List[Dict[str, Any]]) -> Tuple[str, float, float]:
    if history_docs:
        sorted_hist = sorted(history_docs, key=lambda item: parse_dt(item.get("ingestion_date")) or datetime.min.replace(tzinfo=timezone.utc))
        first_score = float(sorted_hist[0].get("risk_score", 0) or 0)
        last_score = float(sorted_hist[-1].get("risk_score", 0) or 0)
        risk_delta = round(last_score - first_score, 2)
    else:
        risk_delta = 0.0

    completion_ratio = 0.0
    if checklist_docs:
        completion_ratio = round(sum(1 for item in checklist_docs if item.get("completed") is True) / len(checklist_docs), 3)

    if risk_delta <= -8 and completion_ratio >= 0.4:
        return "improving", risk_delta, completion_ratio
    if risk_delta >= 8:
        return "worsening", risk_delta, completion_ratio
    if completion_ratio >= 0.75:
        return "managed", risk_delta, completion_ratio
    return "active", risk_delta, completion_ratio


def build_signature(case: CaseRecord, stressors: List[str], symptoms: List[str], actions: List[str], signals: List[str]) -> Set[str]:
    signature: Set[str] = set()
    if case.priority:
        signature.add(f"priority:{normalize_text(case.priority)}")
    if case.category:
        signature.add(f"category:{normalize_text(case.category)}")
    signature.update(f"stressor:{item}" for item in stressors)
    signature.update(f"symptom:{item}" for item in symptoms)
    signature.update(f"action:{slugify(item)}" for item in actions)
    signature.update(f"signal:{slugify(item)}" for item in signals[:6])
    return signature


def jaccard(a: Set[str], b: Set[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def ensure_constraints(driver: Any, database: str) -> None:
    statements = [
        "CREATE CONSTRAINT case_id_unique IF NOT EXISTS FOR (c:Case) REQUIRE c.case_id IS UNIQUE",
        "CREATE CONSTRAINT category_name_unique IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT symptom_name_unique IF NOT EXISTS FOR (s:Symptom) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT stressor_name_unique IF NOT EXISTS FOR (s:Stressor) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT signal_name_unique IF NOT EXISTS FOR (s:ExplanationSignal) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT action_name_unique IF NOT EXISTS FOR (a:Action) REQUIRE a.name IS UNIQUE",
        "CREATE CONSTRAINT outcome_name_unique IF NOT EXISTS FOR (o:Outcome) REQUIRE o.name IS UNIQUE",
        "CREATE CONSTRAINT period_name_unique IF NOT EXISTS FOR (p:Period) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT sentiment_name_unique IF NOT EXISTS FOR (s:SentimentBand) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT cluster_name_unique IF NOT EXISTS FOR (g:CaseCluster) REQUIRE g.name IS UNIQUE",
        "CREATE CONSTRAINT timeline_event_unique IF NOT EXISTS FOR (e:TimelineEvent) REQUIRE e.event_key IS UNIQUE",
        "CREATE CONSTRAINT review_key_unique IF NOT EXISTS FOR (r:ReviewRequest) REQUIRE r.review_key IS UNIQUE",
        "CREATE CONSTRAINT reassignment_key_unique IF NOT EXISTS FOR (r:ReassignmentRequest) REQUIRE r.request_key IS UNIQUE",
    ]
    with driver.session(database=database) as session:
        for statement in statements:
            session.run(statement)


def reset_graph(driver: Any, database: str) -> None:
    with driver.session(database=database) as session:
        session.run("MATCH (n) DETACH DELETE n")


def write_graph(driver: Any, database: str, payload: Dict[str, List[Dict[str, Any]]]) -> None:
    with driver.session(database=database) as session:
        session.run(
            """
            UNWIND $rows AS row
            MERGE (c:Case {case_id: row.case_id})
            SET c += row
            """,
            rows=payload["case_nodes"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (cat:Category {name: row.category})
            WITH row, cat
            MATCH (c:Case {case_id: row.case_id})
            MERGE (c)-[:IN_CATEGORY]->(cat)
            """,
            rows=payload["case_categories"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (s:Stressor {name: row.stressor})
            WITH row, s
            MATCH (c:Case {case_id: row.case_id})
            MERGE (c)-[r:HAS_STRESSOR]->(s)
            SET r.is_primary = row.is_primary,
                r.source = row.source
            """,
            rows=payload["case_stressors"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (s:Symptom {name: row.symptom})
            WITH row, s
            MATCH (c:Case {case_id: row.case_id})
            MERGE (c)-[:HAS_SYMPTOM]->(s)
            """,
            rows=payload["case_symptoms"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (sig:ExplanationSignal {name: row.signal})
            WITH row, sig
            MATCH (c:Case {case_id: row.case_id})
            MERGE (c)-[:HAS_SIGNAL]->(sig)
            """,
            rows=payload["case_signals"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (a:Action {name: row.action_name})
            WITH row, a
            MATCH (c:Case {case_id: row.case_id})
            MERGE (c)-[r:HAS_ACTION]->(a)
            SET r.completed = row.completed,
                r.is_mandatory = row.is_mandatory,
                r.display_order = row.display_order,
                r.action_type = row.action_type
            """,
            rows=payload["case_actions"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (p:Period {name: row.period})
            WITH row, p
            MATCH (c:Case {case_id: row.case_id})
            MERGE (c)-[:OCCURRED_IN]->(p)
            """,
            rows=payload["case_periods"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (o:Outcome {name: row.outcome})
            WITH row, o
            MATCH (c:Case {case_id: row.case_id})
            MERGE (c)-[r:HAS_OUTCOME]->(o)
            SET r.risk_delta = row.risk_delta,
                r.checklist_completion = row.checklist_completion
            """,
            rows=payload["case_outcomes"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (g:CaseCluster {name: row.cluster_name})
            SET g.label = row.cluster_label,
                g.cluster_type = row.cluster_type
            WITH row, g
            MATCH (c:Case {case_id: row.case_id})
            MERGE (c)-[:IN_CLUSTER]->(g)
            """,
            rows=payload["case_clusters"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MATCH (c:Case {case_id: row.case_id})
            MERGE (e:TimelineEvent {event_key: row.event_key})
            SET e += row
            MERGE (c)-[:HAS_TIMELINE_EVENT]->(e)
            """,
            rows=payload["timeline_nodes"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MATCH (prev:TimelineEvent {event_key: row.prev_event_key})
            MATCH (next:TimelineEvent {event_key: row.next_event_key})
            MERGE (prev)-[r:NEXT_EVENT]->(next)
            SET r.risk_delta = row.risk_delta
            """,
            rows=payload["timeline_edges"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (cat:Category {name: row.category})
            WITH row, cat
            MATCH (e:TimelineEvent {event_key: row.event_key})
            MERGE (e)-[:HAS_CATEGORY_STATE]->(cat)
            """,
            rows=payload["timeline_categories"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (s:Stressor {name: row.stressor})
            WITH row, s
            MATCH (e:TimelineEvent {event_key: row.event_key})
            MERGE (e)-[:REFLECTS_STRESSOR]->(s)
            """,
            rows=payload["timeline_stressors"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (s:Symptom {name: row.symptom})
            WITH row, s
            MATCH (e:TimelineEvent {event_key: row.event_key})
            MERGE (e)-[:SHOWS_SYMPTOM]->(s)
            """,
            rows=payload["timeline_symptoms"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (s:SentimentBand {name: row.sentiment})
            WITH row, s
            MATCH (e:TimelineEvent {event_key: row.event_key})
            MERGE (e)-[:HAS_SENTIMENT]->(s)
            """,
            rows=payload["timeline_sentiments"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (p:Period {name: row.period})
            WITH row, p
            MATCH (e:TimelineEvent {event_key: row.event_key})
            MERGE (e)-[:IN_PERIOD]->(p)
            """,
            rows=payload["timeline_periods"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MATCH (c:Case {case_id: row.case_id})
            MERGE (rev:ReviewRequest {review_key: row.review_key})
            SET rev.reason = row.reason,
                rev.request_status = row.request_status,
                rev.requested_by = row.requested_by,
                rev.resolution_notes = row.resolution_notes
            MERGE (c)-[:HAS_REVIEW_REQUEST]->(rev)
            """,
            rows=payload["case_reviews"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MATCH (c:Case {case_id: row.case_id})
            MERGE (rr:ReassignmentRequest {request_key: row.request_key})
            SET rr.reason = row.reason,
                rr.request_status = row.request_status,
                rr.requested_by = row.requested_by,
                rr.suggested_helper = row.suggested_helper,
                rr.new_assigned_to = row.new_assigned_to
            MERGE (c)-[:HAS_REASSIGNMENT_REQUEST]->(rr)
            """,
            rows=payload["case_reassignments"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MATCH (c1:Case {case_id: row.case_a})
            MATCH (c2:Case {case_id: row.case_b})
            MERGE (c1)-[r:SIMILAR_TO]-(c2)
            SET r.score = row.score,
                r.shared_features = row.shared_features
            """,
            rows=payload["case_similarity"],
        )


def build_payload(data: Dict[str, List[Dict[str, Any]]], similarity_threshold: float) -> Dict[str, List[Dict[str, Any]]]:
    checklist_by_case: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    history_by_case: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    reviews_by_case: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    reassign_by_case: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in data["checklist"]:
        checklist_by_case[str(row.get("case_id", ""))].append(row)
    for row in data["history"]:
        history_by_case[str(row.get("case_id", ""))].append(row)
    for row in data["reviews"]:
        reviews_by_case[str(row.get("case_id", ""))].append(row)
    for row in data["reassignments"]:
        reassign_by_case[str(row.get("case_id", ""))].append(row)

    payload: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    signatures: Dict[str, Set[str]] = {}

    for raw_case in data["cases"]:
        case = to_case_record(raw_case)
        if not case.case_id:
            continue

        case_history = sorted(
            history_by_case.get(case.case_id, []),
            key=lambda item: parse_dt(item.get("ingestion_date")) or datetime.min.replace(tzinfo=timezone.utc),
        )
        case_checklist = checklist_by_case.get(case.case_id, [])

        text_pool = [
            case.current_risk_signals,
            case.ai_explanation,
            case.ai_explanation_paragraph,
            *case.ai_explanation_signals,
            *[str(item.get("risk_signals", "")) for item in case_history],
        ]
        symptoms = extract_symptoms(text_pool)
        stressors = extract_stressors(text_pool)
        signals = case.ai_explanation_signals or listify(case.current_risk_signals)
        actions = sorted(
            set(case.recommended_actions)
            | {str(item.get("label", "")).strip() for item in case_checklist if str(item.get("label", "")).strip()}
        )
        outcome_name, risk_delta, completion_ratio = score_outcome(case_history, case_checklist)
        primary_stressor = stressors[0] if stressors else "general_distress"

        payload["case_nodes"].append(
            {
                "case_id": case.case_id,
                "user_id": case.user_id,
                "assigned_to": case.assigned_to,
                "case_status": case.case_status,
                "work_status": case.work_status,
                "priority": case.priority,
                "category": case.category,
                "risk_score": case.current_risk_score,
                "risk_signals": case.current_risk_signals,
                "ai_explanation_paragraph": case.ai_explanation_paragraph,
                "recommended_actions_paragraph": case.recommended_actions_paragraph,
                "platform": case.platform,
                "primary_stressor": primary_stressor,
                "created_at": case.created_at.isoformat() if case.created_at else None,
                "updated_at": case.updated_at.isoformat() if case.updated_at else None,
            }
        )

        if case.category:
            payload["case_categories"].append({"case_id": case.case_id, "category": case.category})

        for index, stressor in enumerate(stressors):
            payload["case_stressors"].append(
                {
                    "case_id": case.case_id,
                    "stressor": stressor,
                    "is_primary": index == 0,
                    "source": "ai_explanation_and_history",
                }
            )
            payload["case_clusters"].append(
                {
                    "case_id": case.case_id,
                    "cluster_name": f"cluster::stressor::{stressor}",
                    "cluster_label": stressor.replace("_", " ").title(),
                    "cluster_type": "stressor",
                }
            )

        payload["case_clusters"].append(
            {
                "case_id": case.case_id,
                "cluster_name": f"cluster::severity::{category_group(case.category)}",
                "cluster_label": f"{category_group(case.category).title()} Severity",
                "cluster_type": "severity",
            }
        )

        for symptom in symptoms:
            payload["case_symptoms"].append({"case_id": case.case_id, "symptom": symptom})

        for signal in signals[:8]:
            payload["case_signals"].append({"case_id": case.case_id, "signal": signal})

        for action in case.recommended_actions:
            payload["case_actions"].append(
                {
                    "case_id": case.case_id,
                    "action_name": action,
                    "completed": False,
                    "is_mandatory": False,
                    "display_order": 100,
                    "action_type": "recommended_action",
                }
            )

        for checklist_item in case_checklist:
            payload["case_actions"].append(
                {
                    "case_id": case.case_id,
                    "action_name": str(checklist_item.get("label", "Checklist Item")).strip() or "Checklist Item",
                    "completed": bool(checklist_item.get("completed", False)),
                    "is_mandatory": bool(checklist_item.get("is_mandatory", False)),
                    "display_order": int(checklist_item.get("display_order", 0) or 0),
                    "action_type": "checklist_item",
                }
            )

        payload["case_periods"].append({"case_id": case.case_id, "period": period_bucket(case.created_at)})
        payload["case_outcomes"].append(
            {
                "case_id": case.case_id,
                "outcome": outcome_name,
                "risk_delta": risk_delta,
                "checklist_completion": completion_ratio,
            }
        )

        previous_event_key: Optional[str] = None
        previous_score: Optional[float] = None
        for index, history in enumerate(case_history, start=1):
            event_dt = parse_dt(history.get("ingestion_date")) or case.created_at or datetime.now(timezone.utc)
            event_text = str(history.get("risk_signals", "") or "")
            event_stressors = extract_stressors([event_text, str(history.get("category", ""))])
            event_symptoms = extract_symptoms([event_text, str(history.get("category", ""))])
            score = float(history.get("risk_score", 0) or 0)
            delta_from_prev = round(score - previous_score, 2) if previous_score is not None else 0.0
            sentiment = infer_sentiment_label(event_text, score, delta_from_prev)
            event_key = f"{case.case_id}::timeline::{history.get('history_id', index)}"

            payload["timeline_nodes"].append(
                {
                    "event_key": event_key,
                    "case_id": case.case_id,
                    "history_id": history.get("history_id", index),
                    "sequence_index": index,
                    "risk_score": score,
                    "risk_signals": event_text,
                    "ingestion_date": event_dt.isoformat(),
                    "category": str(history.get("category", "") or case.category or "Unknown"),
                    "trend": "up" if delta_from_prev > 0 else "down" if delta_from_prev < 0 else "flat",
                }
            )
            payload["timeline_categories"].append({"event_key": event_key, "category": str(history.get("category", "") or case.category or "Unknown")})
            payload["timeline_periods"].append({"event_key": event_key, "period": period_bucket(event_dt)})
            payload["timeline_sentiments"].append({"event_key": event_key, "sentiment": sentiment})
            for stressor in event_stressors:
                payload["timeline_stressors"].append({"event_key": event_key, "stressor": stressor})
            for symptom in event_symptoms:
                payload["timeline_symptoms"].append({"event_key": event_key, "symptom": symptom})

            if previous_event_key is not None:
                payload["timeline_edges"].append(
                    {
                        "prev_event_key": previous_event_key,
                        "next_event_key": event_key,
                        "risk_delta": round(score - (previous_score or 0.0), 2),
                    }
                )

            previous_event_key = event_key
            previous_score = score

        for idx, review in enumerate(reviews_by_case.get(case.case_id, []), start=1):
            payload["case_reviews"].append(
                {
                    "case_id": case.case_id,
                    "review_key": f"{case.case_id}::review::{review.get('review_id', idx)}",
                    "reason": str(review.get("reason", "")),
                    "request_status": str(review.get("request_status", "unknown")),
                    "requested_by": str(review.get("requested_by", "unknown")),
                    "resolution_notes": str(review.get("resolution_notes", "")),
                }
            )

        for idx, req in enumerate(reassign_by_case.get(case.case_id, []), start=1):
            payload["case_reassignments"].append(
                {
                    "case_id": case.case_id,
                    "request_key": f"{case.case_id}::reassign::{req.get('request_id', idx)}",
                    "reason": str(req.get("reason", "")),
                    "request_status": str(req.get("request_status", "unknown")),
                    "requested_by": str(req.get("requested_by", "unknown")),
                    "suggested_helper": str(req.get("suggested_helper", "")),
                    "new_assigned_to": str(req.get("new_assigned_to", "")),
                }
            )

        signatures[case.case_id] = build_signature(case, stressors, symptoms, actions, signals)

    for case_a, case_b in combinations(signatures.keys(), 2):
        score = jaccard(signatures[case_a], signatures[case_b])
        if score >= similarity_threshold:
            payload["case_similarity"].append(
                {
                    "case_a": case_a,
                    "case_b": case_b,
                    "score": round(score, 4),
                    "shared_features": sorted(signatures[case_a] & signatures[case_b])[:16],
                }
            )

    return payload


def create_driver(uri: str, username: str, password: str, insecure_skip_verify: bool) -> Any:
    if insecure_skip_verify:
        insecure_uri = uri.replace("neo4j+s://", "neo4j+ssc://").replace("bolt+s://", "bolt+ssc://")
        return GraphDatabase.driver(insecure_uri, auth=(username, password))
    return GraphDatabase.driver(uri, auth=(username, password))


def main() -> None:
    load_dotenv()
    load_dotenv(os.path.join("backend", ".env"))

    args = parse_args()
    if not all([args.neo4j_uri, args.neo4j_username, args.neo4j_password]):
        raise ValueError("Neo4j credentials missing. Set NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD")

    seeded_case_ids: List[str] = []
    if args.seed_prototype_data:
        seeded_case_ids = seed_prototype_data(args.mongo_uri, args.mongo_db, args.prototype_case_count)
        print(f"[info] Seeded or refreshed prototype Mongo cases: {len(seeded_case_ids)}")

    data = load_mongo_data(args.mongo_uri, args.mongo_db, args.limit_cases, args.fake_if_empty)
    payload = build_payload(data, args.similarity_threshold)

    driver = create_driver(args.neo4j_uri, args.neo4j_username, args.neo4j_password, args.insecure_skip_verify)
    try:
        ensure_constraints(driver, args.neo4j_database)
        if args.reset:
            print("[info] Resetting graph...")
            reset_graph(driver, args.neo4j_database)
            ensure_constraints(driver, args.neo4j_database)
        write_graph(driver, args.neo4j_database, payload)
    finally:
        driver.close()

    print("\n=== Rich Neo4j Prototype Build Complete ===")
    print(f"Cases written: {len(payload['case_nodes'])}")
    print(f"Seeded prototype cases in Mongo: {len(seeded_case_ids)}")
    print(f"Timeline events: {len(payload['timeline_nodes'])}")
    print(f"Timeline transitions: {len(payload['timeline_edges'])}")
    print(f"Case stressor relations: {len(payload['case_stressors'])}")
    print(f"Case symptom relations: {len(payload['case_symptoms'])}")
    print(f"Explanation signal relations: {len(payload['case_signals'])}")
    print(f"Cluster memberships: {len(payload['case_clusters'])}")
    print(f"Similarity edges: {len(payload['case_similarity'])}")
    print("\nUseful Cypher:")
    print("1) MATCH (c:Case)-[:HAS_TIMELINE_EVENT]->(e:TimelineEvent)-[:NEXT_EVENT]->(e2) RETURN c.case_id, e.ingestion_date, e.risk_score, e2.risk_score LIMIT 25")
    print("2) MATCH (c:Case)-[:HAS_STRESSOR]->(s:Stressor) RETURN s.name, count(*) AS cases ORDER BY cases DESC")
    print("3) MATCH (c:Case)-[:IN_CLUSTER]->(g:CaseCluster {cluster_type: 'stressor'}) RETURN g.label, count(*) ORDER BY count(*) DESC")
    print("4) MATCH (c:Case)-[:SIMILAR_TO]-(other:Case) RETURN c.case_id, other.case_id, labels(c), labels(other) LIMIT 25")


if __name__ == "__main__":
    main()
