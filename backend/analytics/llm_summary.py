"""
LLM Summary Generation Module

Uses OpenRouter API to generate comprehensive, empathetic summaries
for high-risk cases with behavioral analysis insights.
"""

import os
import json
import asyncio
import httpx
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger

from config.database import MongoDB


# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-chat-v3-0324:free"

# Rate limiting for free tier
RATE_LIMIT_DELAY = 2.0  # seconds between requests


class LLMSummaryGenerator:
    """
    Generates LLM summaries for case risk profiles using OpenRouter API.
    
    Produces structured summaries with:
    - Executive summary
    - Key risk factors
    - Behavioral patterns
    - Cognitive patterns
    - Recommended actions
    - Supporting evidence
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model
        self.base_url = OPENROUTER_BASE_URL
        
    def _build_prompt(self, profile: Dict[str, Any], signals: List[Dict[str, Any]]) -> str:
        """Build the prompt for LLM summary generation."""
        
        # Extract key metrics from profile
        risk_score = profile.get('risk_score', 0)
        risk_level = profile.get('risk_level', 'Unknown')
        distress_rate = profile.get('distress_rate', 0)
        distortion_rate = profile.get('distortion_rate', 0)
        sentiment_volatility = profile.get('sentiment_volatility', 0)
        avg_sentiment = profile.get('avg_sentiment', 0)
        emotion_distribution = profile.get('emotion_distribution', {})
        distortion_categories = profile.get('distortion_categories', {})
        
        # Get sample distress signals
        distress_signals = [s for s in signals if s.get('is_distress', False)][:5]
        distress_texts = [s.get('text', '')[:200] for s in distress_signals]
        
        # Get sample distortion signals
        distortion_signals = [s for s in signals if s.get('distortion_indicator', 0) == 1][:5]
        distortion_texts = [f"{s.get('text', '')[:150]} (Category: {s.get('distortion_category', 'Unknown')})" 
                           for s in distortion_signals]
        
        prompt = f"""You are a mental health assessment assistant helping youth social workers at Singapore Children's Society. Generate a comprehensive, empathetic summary for this case.

## Case Risk Profile
- **Risk Score**: {risk_score:.2f} ({risk_level})
- **Distress Rate**: {distress_rate*100:.1f}% of content shows distress indicators
- **Cognitive Distortion Rate**: {distortion_rate*100:.1f}% of content shows cognitive distortions
- **Sentiment Volatility**: {sentiment_volatility:.3f}
- **Average Sentiment**: {avg_sentiment:.3f}

## Emotion Distribution
{json.dumps(emotion_distribution, indent=2)}

## Cognitive Distortion Categories Detected
{json.dumps(distortion_categories, indent=2)}

## Sample Distress Signals
{chr(10).join(f'- "{text}"' for text in distress_texts) if distress_texts else '- No distress signals detected'}

## Sample Cognitive Distortion Signals
{chr(10).join(f'- {text}' for text in distortion_texts) if distortion_texts else '- No cognitive distortions detected'}

---

Please provide a structured summary with the following sections:

1. **Executive Summary** (2-3 sentences overview of the case)
2. **Key Risk Factors** (bullet points of main concerns)
3. **Behavioral Patterns** (observed patterns in online behavior)
4. **Cognitive Patterns** (identified cognitive distortions and thinking patterns)
5. **Recommended Actions** (numbered steps for the youth helper to take)
6. **Supporting Evidence** (brief summary of the data supporting this assessment)

Be empathetic, professional, and focus on actionable insights. Remember that the youth helper will use this to guide their outreach decisions.

Format your response as JSON with these keys: executive_summary, key_risk_factors (array), behavioral_patterns, cognitive_patterns, recommended_actions (array), supporting_evidence.
"""
        
        return prompt
    
    async def _call_openrouter(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call OpenRouter API with the prompt."""
        
        if not self.api_key:
            logger.warning("OpenRouter API key not configured. Using fallback summary.")
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://youthcare.scs.org.sg",
            "X-Title": "YOUTH(TH)CARE Dashboard"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a mental health assessment assistant. Always respond with valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1500,
            "response_format": {"type": "json_object"}
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    # Parse JSON response
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse LLM response as JSON: {content[:200]}")
                        return None
                else:
                    logger.error(f"OpenRouter API error: {response.status_code} - {response.text[:200]}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error calling OpenRouter API: {e}")
            return None
    
    def _generate_fallback_summary(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a fallback summary when LLM is unavailable."""
        
        risk_score = profile.get('risk_score', 0)
        risk_level = profile.get('risk_level', 'Unknown')
        distress_rate = profile.get('distress_rate', 0)
        distortion_rate = profile.get('distortion_rate', 0)
        
        risk_factors = []
        if distress_rate > 0.3:
            risk_factors.append("High frequency of distress indicators in social media content")
        if distortion_rate > 0.2:
            risk_factors.append("Cognitive distortion patterns detected in language use")
        if risk_score > 0.7:
            risk_factors.append("Overall risk score indicates urgent attention needed")
        if not risk_factors:
            risk_factors.append("Monitoring recommended - some indicators present")
        
        actions = [
            "Review the case signals and timeline in detail",
            "Prepare empathetic outreach message following SCS protocols",
            "Document initial observations in case notes"
        ]
        if risk_score > 0.7:
            actions.insert(0, "Consider immediate outreach within 24 hours")
            actions.append("Discuss case with team lead if escalation is needed")
        
        return {
            "executive_summary": f"This case shows a {risk_level.lower()} risk profile with a score of {risk_score:.2f}. "
                                f"Analysis of social media content reveals {distress_rate*100:.0f}% distress indicators "
                                f"and {distortion_rate*100:.0f}% cognitive distortion patterns.",
            "key_risk_factors": risk_factors,
            "behavioral_patterns": "Content analysis shows patterns that warrant attention. "
                                  "Review the timeline view for detailed signal progression.",
            "cognitive_patterns": "Some cognitive distortion patterns have been identified. "
                                 "These may indicate negative thought patterns that could benefit from support.",
            "recommended_actions": actions,
            "supporting_evidence": f"Based on NLP analysis of social media content. "
                                  f"Risk score: {risk_score:.2f}, Priority: {profile.get('priority', 'N/A')}."
        }
    
    async def generate_summary(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Generate an LLM summary for a specific user.
        
        Args:
            username: The case_user identifier
            
        Returns:
            Summary document if successful, None otherwise
        """
        try:
            db = MongoDB.get_db()
            
            # Get risk profile
            profile = await db.case_risk_profiles.find_one({"case_user": username})
            if not profile:
                logger.warning(f"No risk profile found for {username}")
                return None
            
            # Get recent signals
            signals = await db.text_units_signals.find(
                {"case_user": username}
            ).sort("processed_at", -1).limit(50).to_list(length=50)
            
            # Build prompt and call LLM
            prompt = self._build_prompt(profile, signals)
            llm_response = await self._call_openrouter(prompt)
            
            # Use fallback if LLM call failed
            if llm_response is None:
                llm_response = self._generate_fallback_summary(profile)
            
            # Build summary document
            summary_doc = {
                "case_user": username,
                "generated_at": datetime.utcnow(),
                "model": self.model if llm_response else "fallback",
                "risk_score": profile.get('risk_score'),
                "risk_level": profile.get('risk_level'),
                "priority": profile.get('priority'),
                **llm_response
            }
            
            # Store in database
            await db.case_llm_summaries.insert_one(summary_doc)
            logger.info(f"Generated LLM summary for {username}")
            
            return summary_doc
            
        except Exception as e:
            logger.error(f"Error generating summary for {username}: {e}")
            return None
    
    async def generate_summaries_for_high_risk(
        self, 
        limit: int = 10, 
        priority: Optional[int] = None
    ) -> Dict[str, List[str]]:
        """
        Generate summaries for high-risk cases.
        
        Args:
            limit: Maximum number of summaries to generate
            priority: Optional priority filter (1=High, 2=Medium, 3=Low)
            
        Returns:
            Dict with lists of generated, failed, and skipped usernames
        """
        try:
            db = MongoDB.get_db()
            
            # Build query for high-risk profiles
            query = {}
            if priority:
                query['priority'] = priority
            
            # Get profiles sorted by priority and risk score
            profiles = await db.case_risk_profiles.find(
                query
            ).sort([
                ('priority', 1),
                ('risk_score', -1)
            ]).limit(limit).to_list(length=limit)
            
            results = {
                "generated": [],
                "failed": [],
                "skipped": []
            }
            
            for profile in profiles:
                username = profile.get('case_user')
                
                # Check if summary already exists (within last 24 hours)
                existing = await db.case_llm_summaries.find_one({
                    "case_user": username,
                    "generated_at": {"$gte": datetime.utcnow() - timedelta(hours=24)}
                })
                
                if existing:
                    results["skipped"].append(username)
                    continue
                
                # Generate summary with rate limiting
                summary = await self.generate_summary(username)
                
                if summary:
                    results["generated"].append(username)
                else:
                    results["failed"].append(username)
                
                # Rate limit for free tier
                await asyncio.sleep(RATE_LIMIT_DELAY)
            
            logger.info(f"LLM summary generation complete: {len(results['generated'])} generated, "
                       f"{len(results['failed'])} failed, {len(results['skipped'])} skipped")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in batch summary generation: {e}")
            return {"generated": [], "failed": [], "skipped": []}


async def generate_llm_summaries(
    limit: int = 5, 
    priority: Optional[int] = None
) -> Dict[str, List[str]]:
    """
    Convenience function to generate LLM summaries.
    
    Args:
        limit: Maximum number of summaries to generate
        priority: Optional priority filter
        
    Returns:
        Results dict with generated, failed, skipped lists
    """
    generator = LLMSummaryGenerator()
    return await generator.generate_summaries_for_high_risk(limit=limit, priority=priority)
