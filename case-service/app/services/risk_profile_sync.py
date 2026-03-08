"""
Risk Profile Sync Service

Syncs risk profiles from instagram_scraper.case_risk_profiles to dellinnovate.scs_cases
and generates LLM summaries on demand.
"""

import os
import json
import httpx
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)

# Environment configuration
MONGODB_URI = os.getenv("MONGODB_URI", "")
INSTAGRAM_DB_NAME = os.getenv("MONGODB_DB_NAME", "instagram_scraper")
SCS_DB_NAME = os.getenv("SCS_DB_NAME", "dellinnovate")
SCS_COLLECTION_CASES = os.getenv("SCS_COLLECTION_CASES", "scs_cases")

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3.1")

# Risk level mapping
RISK_LEVEL_MAP = {
    "Low": "Low Risk",
    "Moderate": "Moderate Risk",
    "High": "High Risk",
    "Critical": "Critical Risk"
}

# Priority mapping (numeric to text)
PRIORITY_MAP = {
    1: "low",
    2: "low",
    3: "medium",
    4: "high",
    5: "high"
}

# Sensitive fields to exclude from frontend responses (but include in LLM)
SENSITIVE_FIELDS = [
    "top_distress_comments",
    "captions"
]

# LLM prompt template for case summaries (simple text summary)
LLM_PROMPT_TEMPLATE = """You are a mental health risk analysis assistant helping youth helpers triage cases.

Below is an aggregated risk profile generated from social media behavioural analysis.

The raw dataset may contain sensitive content. Do NOT reveal usernames, comments, or personally identifiable information.

Only produce a **short professional case summary** describing:

• overall risk level
• behavioural patterns
• emotional indicators
• recommended monitoring urgency

Risk Profile Data:
{risk_profile_json}

Respond with a concise paragraph suitable for a youth helper dashboard."""

# LLM prompt template for generating structured case analysis (category, signals, actions)
LLM_STRUCTURED_PROMPT_TEMPLATE = """You are a mental health risk analysis assistant helping youth helpers triage cases at Singapore Children's Society.

Below is a comprehensive risk profile generated from social media behavioural analysis. It includes all NLP sentiment scores, emotion distributions, cognitive distortion patterns, distress indicators, and sample comments.

IMPORTANT: Do NOT reveal usernames, raw comments, captions, or personally identifiable information in your response.

Analyze this data and provide a structured JSON response with the following fields:

1. **category**: A specific problem category label. Choose the MOST appropriate one from:
   - "Bullying" (if signs of being bullied or cyberbullying)
   - "Depression" (if signs of persistent sadness, hopelessness)
   - "Self-Harm" (if signs of self-harm ideation or behavior)
   - "Anxiety" (if signs of excessive worry, panic, fear)
   - "Social Isolation" (if signs of loneliness, withdrawal)
   - "Family Issues" (if signs of family conflict, domestic problems)
   - "Academic Stress" (if signs of school/study pressure)
   - "Eating Disorder" (if signs of disordered eating)
   - "Substance Use" (if signs of drug/alcohol issues)
   - "Identity Crisis" (if signs of identity struggles, LGBTQ+ issues)
   - "Grief" (if signs of loss, bereavement)
   - "General Distress" (if mixed or unclear signals)

2. **ai_explanation_paragraph**: A 2-3 sentence professional paragraph summarizing WHY this case was flagged and what behavioral patterns were observed. Write in third person, clinical but compassionate tone. Do not use bullet points here.

3. **ai_explanation_signals**: A JSON array of 3-5 specific behavioral signals detected. Each signal should be concise (5-10 words). Example: ["High negative sentiment rate: 45%", "Elevated distress emotion count: 12 instances", "Cognitive distortion: catastrophizing detected"]

4. **recommended_actions_paragraph**: A 2-3 sentence professional paragraph explaining the recommended intervention approach based on SCS protocols. Mention the urgency level and general strategy.

5. **recommended_actions**: A JSON array of 3-5 specific recommended actions for the youth helper. Each action should be actionable and protocol-based. Example: ["Review recent posts for escalation patterns", "Prepare empathetic outreach message", "Consult with team lead if risk score exceeds 70"]

Risk Profile Data:
{risk_profile_json}

Respond ONLY with valid JSON in this exact format:
{{
  "category": "Category Name",
  "ai_explanation_paragraph": "This youth has exhibited concerning behavioral patterns over the analysis period. The sentiment analysis reveals persistent negative emotional expression combined with elevated distress indicators, suggesting potential mental health struggles that warrant professional attention.",
  "ai_explanation_signals": ["Signal 1", "Signal 2", "Signal 3"],
  "recommended_actions_paragraph": "Based on SCS protocols, this case requires moderate-priority intervention within 24-48 hours. A warm, empathetic outreach approach is recommended, focusing on establishing trust before addressing underlying concerns.",
  "recommended_actions": ["Action 1", "Action 2", "Action 3"]
}}"""


class RiskProfileSyncService:
    """
    Service to sync risk profiles from instagram_scraper to scs_cases
    and generate LLM summaries on demand.
    """

    def __init__(self, mongo_uri: Optional[str] = None):
        self.mongo_uri = mongo_uri or MONGODB_URI
        self._client: Optional[AsyncIOMotorClient] = None

    async def _get_client(self) -> AsyncIOMotorClient:
        """Get or create MongoDB client."""
        if self._client is None:
            self._client = AsyncIOMotorClient(self.mongo_uri)
        return self._client

    async def close(self):
        """Close MongoDB client."""
        if self._client:
            self._client.close()
            self._client = None

    def _map_user_id(self, case_user: str) -> str:
        """Convert case_user to anonymized user_id format."""
        return f"@case_{case_user}"

    def _extract_case_user(self, user_id: str) -> str:
        """Extract original case_user from user_id."""
        if user_id.startswith("@case_"):
            return user_id[6:]  # Remove "@case_" prefix
        return user_id.lstrip("@")

    def _map_risk_level(self, risk_level: str) -> str:
        """Map risk_level to current_category."""
        return RISK_LEVEL_MAP.get(risk_level, "Unknown Risk")

    def _map_priority(self, priority: int) -> str:
        """Map numeric priority to text."""
        return PRIORITY_MAP.get(priority, "medium")

    def _format_key_signals(self, key_signals: List[str]) -> str:
        """Join key_signals into a comma-separated string."""
        if not key_signals:
            return ""
        return ", ".join(key_signals)

    async def _get_next_case_id(self, scs_db) -> str:
        """Generate the next sequential case_id."""
        cases_col = scs_db[SCS_COLLECTION_CASES]
        
        # Find the highest existing case number
        cursor = cases_col.find(
            {"case_id": {"$regex": "^CASE_2026_"}}
        ).sort("case_id", -1).limit(1)
        
        docs = await cursor.to_list(length=1)
        
        if docs:
            last_case_id = docs[0].get("case_id", "CASE_2026_000")
            try:
                last_num = int(last_case_id.split("_")[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1

        return f"CASE_2026_{next_num:03d}"

    async def sync_risk_profiles_to_cases(self) -> Dict[str, Any]:
        """
        Read risk profiles from case_risk_profiles collection in instagram_scraper
        and insert/update cases into scs_cases collection in dellinnovate.
        
        Returns:
            Dict with sync statistics (created, updated, errors)
        """
        client = await self._get_client()
        
        instagram_db = client[INSTAGRAM_DB_NAME]
        scs_db = client[SCS_DB_NAME]
        
        risk_profiles_col = instagram_db["case_risk_profiles"]
        cases_col = scs_db[SCS_COLLECTION_CASES]
        
        stats = {
            "created": 0,
            "updated": 0,
            "errors": 0,
            "processed": 0
        }
        
        # Fetch all risk profiles
        cursor = risk_profiles_col.find({})
        
        async for profile in cursor:
            stats["processed"] += 1
            case_user = profile.get("case_user", "")
            
            if not case_user:
                stats["errors"] += 1
                logger.warning("Skipping profile without case_user")
                continue
            
            try:
                # Map fields according to specification
                user_id = self._map_user_id(case_user)
                
                # Check if case already exists for this user
                existing_case = await cases_col.find_one({"user_id": user_id})
                
                now = datetime.now(timezone.utc)
                
                case_data = {
                    "user_id": user_id,
                    "current_risk_score": profile.get("risk_score", 0),
                    "current_category": self._map_risk_level(profile.get("risk_level", "Low")),
                    "current_risk_signals": self._format_key_signals(profile.get("key_signals", [])),
                    "priority": self._map_priority(profile.get("priority", 3)),
                    "updated_at": now
                }
                
                if existing_case:
                    # Update existing case
                    await cases_col.update_one(
                        {"_id": existing_case["_id"]},
                        {"$set": case_data}
                    )
                    stats["updated"] += 1
                    logger.info(f"Updated case for user: {user_id}")
                else:
                    # Create new case
                    case_id = await self._get_next_case_id(scs_db)
                    case_data["case_id"] = case_id
                    case_data["assigned_to"] = None
                    case_data["case_status"] = "unassigned"
                    case_data["work_status"] = "not_started"
                    case_data["created_at"] = now
                    
                    await cases_col.insert_one(case_data)
                    stats["created"] += 1
                    logger.info(f"Created case {case_id} for user: {user_id}")
                    
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Error syncing profile for {case_user}: {e}")
        
        logger.info(f"Sync completed: {stats}")
        return stats

    async def get_risk_profile_for_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the full risk profile for a case.
        
        Args:
            case_id: The SCS case ID
            
        Returns:
            The full risk profile document from instagram_scraper, or None if not found
        """
        client = await self._get_client()
        
        scs_db = client[SCS_DB_NAME]
        instagram_db = client[INSTAGRAM_DB_NAME]
        
        cases_col = scs_db[SCS_COLLECTION_CASES]
        risk_profiles_col = instagram_db["case_risk_profiles"]
        
        # Find the case
        case = await cases_col.find_one({"case_id": case_id})
        if not case:
            logger.warning(f"Case not found: {case_id}")
            return None
        
        # Extract case_user from user_id
        user_id = case.get("user_id", "")
        case_user = self._extract_case_user(user_id)
        
        # Query risk profile
        profile = await risk_profiles_col.find_one({"case_user": case_user})
        if not profile:
            logger.warning(f"Risk profile not found for case_user: {case_user}")
            return None
        
        # Remove MongoDB _id for serialization
        if "_id" in profile:
            del profile["_id"]
        
        return profile

    def _sanitize_profile_for_frontend(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive fields from profile for frontend display.
        
        The full profile is still passed to the LLM.
        """
        sanitized = profile.copy()
        
        # Remove sensitive fields
        for field in SENSITIVE_FIELDS:
            if field in sanitized:
                del sanitized[field]
        
        # Also remove actual usernames if present
        if "case_user" in sanitized:
            del sanitized["case_user"]
        
        return sanitized

    async def generate_case_summary(self, case_id: str) -> Dict[str, Any]:
        """
        Generate an LLM summary for a case by calling OpenRouter.
        
        This should only be called when a case is opened/viewed,
        NOT automatically for all cases.
        
        Args:
            case_id: The SCS case ID
            
        Returns:
            Dict with summary, status, and optionally error details
        """
        # Get the full risk profile
        profile = await self.get_risk_profile_for_case(case_id)
        
        if not profile:
            return {
                "status": "error",
                "error": "Risk profile not found for this case",
                "summary": None
            }
        
        # Build the prompt with full profile (LLM prompt instructs not to reveal sensitive info)
        # Prepare a clean JSON representation for the LLM
        profile_for_llm = json.dumps(profile, indent=2, default=str)
        prompt = LLM_PROMPT_TEMPLATE.format(risk_profile_json=profile_for_llm)
        
        # Call OpenRouter API
        summary = await self._call_openrouter(prompt)
        
        if summary:
            return {
                "status": "success",
                "summary": summary,
                "case_id": case_id
            }
        else:
            # Fallback summary if LLM fails
            fallback = self._generate_fallback_summary(profile)
            return {
                "status": "fallback",
                "summary": fallback,
                "case_id": case_id,
                "note": "LLM unavailable, using automated summary"
            }

    async def _call_openrouter(self, prompt: str) -> Optional[str]:
        """
        Call OpenRouter API to generate summary.
        
        Returns the summary text or None on failure.
        """
        if not OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY not configured. Using fallback.")
            return None
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://youthcare.scs.org.sg",
            "X-Title": "SCS Youth Helper Dashboard"
        }
        
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a mental health risk analysis assistant. Be concise, professional, and empathetic."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return content.strip() if content else None
                else:
                    logger.error(f"OpenRouter API error: {response.status_code} - {response.text[:200]}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error calling OpenRouter API: {e}")
            return None

    def _generate_fallback_summary(self, profile: Dict[str, Any]) -> str:
        """Generate a fallback summary when LLM is unavailable."""
        risk_score = profile.get("risk_score", 0)
        risk_level = profile.get("risk_level", "Unknown")
        key_signals = profile.get("key_signals", [])
        negative_rate = profile.get("negative_sentiment_rate", 0)
        avg_distress = profile.get("avg_distress_score", 0)
        
        signals_text = ", ".join(key_signals[:3]) if key_signals else "no specific signals detected"
        
        summary = (
            f"This case presents a {risk_level.lower()} risk profile with a score of {risk_score:.1f}. "
            f"Key indicators include: {signals_text}. "
        )
        
        if negative_rate > 0.3:
            summary += f"Elevated negative sentiment rate ({negative_rate*100:.0f}%) observed. "
        
        if avg_distress > 0.1:
            summary += f"Average distress indicators suggest monitoring is recommended. "
        
        if risk_level in ["High", "Critical"]:
            summary += "Prompt outreach is advised given the risk level."
        else:
            summary += "Standard monitoring protocols should be followed."
        
        return summary

    async def _call_openrouter_structured(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Call OpenRouter API to generate structured JSON response.
        
        Returns parsed JSON dict or None on failure.
        """
        if not OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY not configured. Using fallback.")
            return None
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://youthcare.scs.org.sg",
            "X-Title": "SCS Youth Helper Dashboard"
        }
        
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a mental health risk analysis assistant. Always respond with valid JSON only. No markdown, no explanations, just the JSON object."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"}
        }
        
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        # Try to parse JSON
                        try:
                            # Strip any markdown code blocks if present
                            content = content.strip()
                            if content.startswith("```"):
                                content = content.split("```")[1]
                                if content.startswith("json"):
                                    content = content[4:]
                            return json.loads(content)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse LLM JSON response: {e}")
                            logger.debug(f"Raw content: {content[:500]}")
                            return None
                    return None
                else:
                    logger.error(f"OpenRouter API error: {response.status_code} - {response.text[:200]}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error calling OpenRouter API: {e}")
            return None

    async def generate_structured_analysis(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate structured LLM analysis for a risk profile.
        
        Returns dict with category, ai_explanation, recommended_actions.
        """
        # Prepare profile JSON (include all data for LLM)
        profile_for_llm = json.dumps(profile, indent=2, default=str)
        prompt = LLM_STRUCTURED_PROMPT_TEMPLATE.format(risk_profile_json=profile_for_llm)
        
        # Call OpenRouter API
        result = await self._call_openrouter_structured(prompt)
        
        if result:
            # Combine paragraph and signals for ai_explanation
            paragraph = result.get("ai_explanation_paragraph", "")
            signals = result.get("ai_explanation_signals", [])
            ai_explanation = paragraph
            if signals:
                ai_explanation += "\n\nKey signals detected:\n" + "\n".join([f"• {s}" for s in signals])
            
            # Combine paragraph and actions for recommended_actions_text
            actions_paragraph = result.get("recommended_actions_paragraph", "")
            actions_list = result.get("recommended_actions", [])
            
            return {
                "category": result.get("category", "General Distress"),
                "ai_explanation": ai_explanation,
                "ai_explanation_paragraph": paragraph,
                "ai_explanation_signals": signals,
                "recommended_actions_paragraph": actions_paragraph,
                "recommended_actions": actions_list
            }
        else:
            # Generate fallback
            return self._generate_fallback_analysis(profile)

    def _generate_fallback_analysis(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback analysis when LLM is unavailable."""
        risk_score = profile.get("risk_score", 0)
        risk_level = profile.get("risk_level", "Low")
        key_signals = profile.get("key_signals", [])
        negative_rate = profile.get("negative_sentiment_rate", 0)
        distress_count = profile.get("distress_emotion_count", 0)
        distortion_count = profile.get("distortion_count", 0)
        emotion_dist = profile.get("emotion_distribution", {})
        
        # Determine category based on signals
        category = "General Distress"
        signals_lower = " ".join(key_signals).lower()
        if "bully" in signals_lower:
            category = "Bullying"
        elif "self" in signals_lower and "harm" in signals_lower:
            category = "Self-Harm"
        elif "depress" in signals_lower or "sad" in signals_lower:
            category = "Depression"
        elif "anxi" in signals_lower or "fear" in signals_lower or "panic" in signals_lower:
            category = "Anxiety"
        elif "isolat" in signals_lower or "alone" in signals_lower or "lonely" in signals_lower:
            category = "Social Isolation"
        elif emotion_dist.get("sadness", 0) > 3:
            category = "Depression"
        elif emotion_dist.get("fear", 0) > 3:
            category = "Anxiety"
        
        # Build AI explanation
        explanation_parts = ["This case was flagged due to:"]
        if negative_rate > 0.3:
            explanation_parts.append(f"• High negative sentiment rate ({negative_rate*100:.0f}%)")
        if distress_count > 0:
            explanation_parts.append(f"• Elevated distress indicators ({distress_count} instances)")
        if distortion_count > 0:
            explanation_parts.append(f"• Cognitive distortion patterns detected ({distortion_count} instances)")
        if risk_score > 50:
            explanation_parts.append(f"• Elevated overall risk score ({risk_score:.1f})")
        for signal in key_signals[:2]:
            explanation_parts.append(f"• {signal}")
        
        ai_explanation = " ".join(explanation_parts) if len(explanation_parts) > 1 else "This case was flagged due to: • Automated monitoring detected potential risk indicators"
        
        # Build recommended actions
        actions = [
            "Review the case timeline for recent changes in behavior",
            "Prepare empathetic outreach message following SCS protocols"
        ]
        if risk_score > 70:
            actions.insert(0, "URGENT: Consider immediate outreach within 24 hours")
            actions.append("Discuss escalation options with team lead")
        elif risk_score > 50:
            actions.append("Schedule follow-up check within 3 days")
        else:
            actions.append("Continue routine monitoring")
        
        # Build paragraph explanations
        ai_paragraph = f"This youth has exhibited concerning behavioral patterns warranting attention. The analysis reveals a {risk_level.lower()} risk level with overall score of {risk_score:.1f}."
        if distress_count > 0:
            ai_paragraph += f" Notably, {distress_count} distress indicators were detected."
        
        actions_paragraph = "Based on SCS protocols, a measured intervention approach is recommended."
        if risk_score > 70:
            actions_paragraph = "This case requires urgent attention within 24 hours based on SCS high-risk protocols. Immediate empathetic outreach is recommended."
        elif risk_score > 50:
            actions_paragraph = "Based on SCS protocols, moderate-priority intervention within 48 hours is recommended. Focus on establishing rapport before addressing concerns."
        else:
            actions_paragraph = "Routine monitoring is recommended per SCS protocols. Consider periodic check-ins to track behavioral patterns."
        
        return {
            "category": category,
            "ai_explanation": ai_explanation,
            "ai_explanation_paragraph": ai_paragraph,
            "ai_explanation_signals": key_signals[:5],
            "recommended_actions_paragraph": actions_paragraph,
            "recommended_actions": actions
        }

    async def sync_risk_profiles_to_cases_with_llm(self) -> Dict[str, Any]:
        """
        Sync risk profiles from instagram_scraper to scs_cases,
        generating LLM-based category, ai_explanation, and recommended_actions.
        
        Returns:
            Dict with sync statistics
        """
        client = await self._get_client()
        
        instagram_db = client[INSTAGRAM_DB_NAME]
        scs_db = client[SCS_DB_NAME]
        
        risk_profiles_col = instagram_db["case_risk_profiles"]
        cases_col = scs_db[SCS_COLLECTION_CASES]
        
        stats = {
            "created": 0,
            "updated": 0,
            "errors": 0,
            "processed": 0,
            "llm_generated": 0
        }
        
        # Fetch all risk profiles
        cursor = risk_profiles_col.find({})
        
        async for profile in cursor:
            stats["processed"] += 1
            case_user = profile.get("case_user", "")
            
            if not case_user:
                stats["errors"] += 1
                logger.warning("Skipping profile without case_user")
                continue
            
            try:
                # Map fields according to specification
                user_id = self._map_user_id(case_user)
                
                # Generate LLM analysis
                logger.info(f"Generating LLM analysis for {case_user}...")
                llm_analysis = await self.generate_structured_analysis(profile)
                stats["llm_generated"] += 1
                
                # Check if case already exists for this user
                existing_case = await cases_col.find_one({"user_id": user_id})
                
                now = datetime.now(timezone.utc)
                
                # Build case data with LLM-generated fields
                case_data = {
                    "user_id": user_id,
                    "current_risk_score": profile.get("risk_score", 0),
                    "current_category": llm_analysis.get("category", "General Distress"),
                    "current_risk_signals": self._format_key_signals(profile.get("key_signals", [])),
                    "ai_explanation": llm_analysis.get("ai_explanation", ""),
                    "ai_explanation_paragraph": llm_analysis.get("ai_explanation_paragraph", ""),
                    "ai_explanation_signals": llm_analysis.get("ai_explanation_signals", []),
                    "recommended_actions_paragraph": llm_analysis.get("recommended_actions_paragraph", ""),
                    "recommended_actions": llm_analysis.get("recommended_actions", []),
                    "priority": self._map_priority(profile.get("priority", 3)),
                    "platform": "Instagram",
                    "updated_at": now
                }
                
                if existing_case:
                    # Update existing case
                    await cases_col.update_one(
                        {"_id": existing_case["_id"]},
                        {"$set": case_data}
                    )
                    stats["updated"] += 1
                    logger.info(f"Updated case for user: {user_id} with category: {llm_analysis.get('category')}")
                else:
                    # Create new case
                    case_id = await self._get_next_case_id(scs_db)
                    case_data["case_id"] = case_id
                    case_data["assigned_to"] = None
                    case_data["case_status"] = "unassigned"
                    case_data["work_status"] = "not_started"
                    case_data["created_at"] = now
                    
                    await cases_col.insert_one(case_data)
                    stats["created"] += 1
                    logger.info(f"Created case {case_id} for user: {user_id} with category: {llm_analysis.get('category')}")
                
                # Rate limiting - small delay between LLM calls
                import asyncio
                await asyncio.sleep(1.0)
                    
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Error syncing profile for {case_user}: {e}")
        
        logger.info(f"Sync with LLM completed: {stats}")
        return stats


# Singleton instance for use across the application
_sync_service: Optional[RiskProfileSyncService] = None


def get_sync_service() -> RiskProfileSyncService:
    """Get or create the singleton sync service."""
    global _sync_service
    if _sync_service is None:
        _sync_service = RiskProfileSyncService()
    return _sync_service


async def sync_risk_profiles_to_cases() -> Dict[str, Any]:
    """
    Convenience function to sync risk profiles to cases.
    
    Reads from instagram_scraper.case_risk_profiles
    and inserts/updates dellinnovate.scs_cases.
    """
    service = get_sync_service()
    return await service.sync_risk_profiles_to_cases()


async def generate_case_summary(case_id: str) -> Dict[str, Any]:
    """
    Convenience function to generate an LLM summary for a case.
    
    Args:
        case_id: The SCS case ID
        
    Returns:
        Dict with summary and status
    """
    service = get_sync_service()
    return await service.generate_case_summary(case_id)


async def sync_risk_profiles_to_cases_with_llm() -> Dict[str, Any]:
    """
    Convenience function to sync risk profiles to cases with LLM analysis.
    
    Generates category, ai_explanation, and recommended_actions using LLM
    for each risk profile and populates them in scs_cases.
    """
    service = get_sync_service()
    return await service.sync_risk_profiles_to_cases_with_llm()
