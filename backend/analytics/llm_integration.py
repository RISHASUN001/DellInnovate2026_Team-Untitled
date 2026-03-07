"""
LLM Integration for Case Summarization and Categorization
Generates empathetic, user-friendly explanations of risk metrics
Optimized for on-demand generation when viewing a profile
"""

import os
import httpx
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger
from pydantic import BaseModel

class CaseCategory:
    """Case categories for risk assessment"""
    CRITICAL = "Critical"
    HIGH_RISK = "High Risk"
    MODERATE_RISK = "Moderate Risk"
    LOW_RISK = "Low Risk"
    MONITORING = "Monitoring"
    BULLYING = "Bullying"
    SELF_HARM = "Self-Harm Ideation"
    ANXIETY = "Anxiety"
    DEPRESSION = "Depression"
    LONELINESS = "Loneliness/Isolation"
    GENERAL_CONCERN = "General Concern"

class LLMSummarizer:
    """
    Handles LLM-based summarization and categorization of risk profiles
    Generates empathetic, plain-language explanations on-demand
    """
    
    # Most reliable free models on OpenRouter (as of March 2026)
    WORKING_MODELS = [
        "meta-llama/llama-3.2-3b-instruct:free",  # Most reliable
    ]
    
    def __init__(self, use_llm: bool = True):
        """
        Initialize LLM Summarizer
        
        Args:
            use_llm: If False, always use fallback (skip API calls)
        """
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.model = os.getenv("OPENROUTER_MODEL", self.WORKING_MODELS[0])
        self.use_llm = use_llm
        
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not found. Using enhanced fallback.")
            self.use_llm = False
        
        logger.debug(f"LLM Summarizer initialized (model: {self.model}, use_llm: {self.use_llm})")
    
    async def summarize_risk_profile(self, risk_profile: Dict) -> Dict[str, Any]:
        """
        Generate LLM summary for a risk profile (optimized for single user)
        
        Args:
            risk_profile: Complete risk profile document
            
        Returns:
            Dict with explanation, category, and recommendations
        """
        # If LLM is disabled, use fallback immediately (fast)
        if not self.use_llm or not self.api_key:
            logger.info("Using enhanced fallback explanation (fast)")
            return self._generate_enhanced_fallback(risk_profile)
        
        # Build prompt
        prompt = self._build_enhanced_summary_prompt(risk_profile)
        
        # Try the model with reasonable delays for a single user
        model = self.WORKING_MODELS[0]
        logger.info(f"Attempting LLM generation with {model}...")
        
        # Try up to 2 times with increasing delays
        for attempt in range(2):
            try:
                if attempt == 1:
                    logger.info("First attempt rate limited, waiting 10 seconds...")
                    await asyncio.sleep(10)
                
                result = await self._try_model(model, prompt, risk_profile)
                if result:
                    logger.success("✅ AI explanation generated successfully")
                    return result
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
        
        # If LLM fails, use enhanced fallback (still good quality)
        logger.info("Using enhanced fallback explanation (still detailed)")
        return self._generate_enhanced_fallback(risk_profile)
    
    async def _try_model(self, model: str, prompt: str, risk_profile: Dict) -> Optional[Dict]:
        """Try a specific model once"""
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:8000",
                        "X-Title": "SCS Youth Helper Dashboard"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": """You are an empathetic youth mental health analyst for Singapore Children's Society. 
                                Your role is to help youth workers understand risk profiles in plain, compassionate language.
                                
                                Write ONE warm, empathetic paragraph that:
                                - Explains the situation in simple terms
                                - Mentions key concerning patterns naturally
                                - Uses percentages and numbers conversationally
                                - Sounds like a caring colleague explaining a case
                                
                                Then provide category and recommendations."""
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.4,
                        "max_tokens": 600
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    llm_output = result['choices'][0]['message']['content']
                    return self._parse_response(llm_output, risk_profile)
                
                elif response.status_code == 429:
                    logger.warning("Rate limited (free tier limit)")
                    return None
                
                else:
                    logger.warning(f"API error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.warning(f"Request failed: {e}")
            return None
    
    def _build_enhanced_summary_prompt(self, profile: Dict) -> str:
        """Build prompt for LLM"""
        
        # Extract key metrics
        case_user = profile.get('case_user', 'this young person')
        risk_score = profile.get('risk_score', 0)
        risk_level = profile.get('risk_level', 'Unknown')
        
        distress_rate = profile.get('distress_emotion_rate', 0)
        distress_count = profile.get('distress_emotion_count', 0)
        
        distortion_rate = profile.get('distortion_rate', 0)
        distortion_count = profile.get('distortion_count', 0)
        
        avg_sentiment = profile.get('avg_sentiment_score', 0)
        late_night_rate = profile.get('late_night_activity_rate', 0)
        total_units = profile.get('total_text_units', 0)
        
        # Emotion distribution
        emotion_dist = profile.get('emotion_distribution', {})
        emotion_text = ""
        for emotion, count in emotion_dist.items():
            if count > 0:
                emotion_text += f"- {emotion}: {count}\n"
        
        # Key signals
        key_signals = profile.get('key_signals', [])
        signals_text = "\n".join([f"- {s}" for s in key_signals[:3]]) if key_signals else ""
        
        prompt = f"""
Please write a warm, empathetic explanation for this youth case:

**CASE:** {case_user}
**RISK:** {risk_score:.1f}/100 ({risk_level})
**POSTS ANALYZED:** {total_units}

**EMOTIONS:** 
{emotion_text}

**KEY METRICS:**
- Distressed posts: {distress_rate:.1%} ({distress_count} instances)
- Negative thinking: {distortion_rate:.1%} ({distortion_count} instances)
- Overall mood: {avg_sentiment:.2f} (-1 to +1 scale)
- Late night: {late_night_rate:.1%}

**KEY PATTERNS:**
{signals_text}

Write ONE paragraph (4-6 sentences) that:
1. Starts with "Based on {case_user}'s recent Instagram activity..."
2. Explains what emotions they're showing
3. Mentions the distress level naturally
4. Notes any concerning patterns
5. Ends with the risk level

Then provide:
CATEGORY: [Critical/High Risk/Moderate Risk/Low Risk/Monitoring]
RECOMMENDATIONS: [action1 | action2 | action3]

Format:
EXPLANATION: [your paragraph]
CATEGORY: [category]
RECOMMENDATIONS: [rec1 | rec2 | rec3]
"""
        return prompt
    
    def _parse_response(self, response: str, original_profile: Dict) -> Dict[str, Any]:
        """Parse LLM response"""
        result = {
            'explanation': '',
            'llm_category': 'General Concern',
            'recommendations': [],
            'generated_at': datetime.utcnow().isoformat()
        }
        
        try:
            lines = response.strip().split('\n')
            explanation_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('EXPLANATION:'):
                    explanation_text = line.replace('EXPLANATION:', '', 1).strip()
                    if explanation_text:
                        explanation_lines.append(explanation_text)
                elif line.startswith('CATEGORY:'):
                    category = line.replace('CATEGORY:', '', 1).strip()
                    valid = ['Critical', 'High Risk', 'Moderate Risk', 'Low Risk', 'Monitoring']
                    for v in valid:
                        if v.lower() in category.lower():
                            result['llm_category'] = v
                            break
                elif line.startswith('RECOMMENDATIONS:'):
                    rec_text = line.replace('RECOMMENDATIONS:', '', 1).strip()
                    if '|' in rec_text:
                        result['recommendations'] = [r.strip() for r in rec_text.split('|') if r.strip()]
                    elif ',' in rec_text:
                        result['recommendations'] = [r.strip() for r in rec_text.split(',') if r.strip()]
                    else:
                        result['recommendations'] = [rec_text] if rec_text else []
                elif explanation_lines:
                    explanation_lines.append(line)
            
            if explanation_lines:
                result['explanation'] = ' '.join(explanation_lines)
            
            # If parsing failed or explanation too short, use fallback
            if not result['explanation'] or len(result['explanation']) < 50:
                return self._generate_enhanced_fallback(original_profile)
                
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return self._generate_enhanced_fallback(original_profile)
        
        return result
    
    def _generate_enhanced_fallback(self, profile: Dict) -> Dict[str, Any]:
        """Generate detailed explanation without LLM"""
        case_user = profile.get('case_user', 'This young person')
        risk_level = profile.get('risk_level', 'Unknown')
        risk_score = profile.get('risk_score', 0)
        distress_rate = profile.get('distress_emotion_rate', 0)
        distress_count = profile.get('distress_emotion_count', 0)
        distortion_rate = profile.get('distortion_rate', 0)
        distortion_count = profile.get('distortion_count', 0)
        avg_sentiment = profile.get('avg_sentiment_score', 0)
        late_night_rate = profile.get('late_night_activity_rate', 0)
        total_units = profile.get('total_text_units', 0)
        
        # Get emotion distribution
        emotion_dist = profile.get('emotion_distribution', {})
        
        # Build explanation
        explanation = f"Based on {case_user}'s recent Instagram activity ({total_units} posts and comments), "
        
        # Emotional state
        if emotion_dist:
            top_emotions = []
            for emotion, count in sorted(emotion_dist.items(), key=lambda x: x[1], reverse=True)[:2]:
                if count > 0:
                    top_emotions.append(emotion)
            if top_emotions:
                explanation += f"they're expressing {' and '.join(top_emotions)}. "
        
        # Distress level
        if distress_rate > 0.5:
            explanation += f"A concerning {distress_rate:.0%} of their posts ({distress_count} instances) show emotional distress. "
        elif distress_rate > 0.3:
            explanation += f"About {distress_rate:.0%} of their posts ({distress_count} instances) contain emotional distress. "
        elif distress_rate > 0.1:
            explanation += f"About {distress_rate:.0%} of their posts ({distress_count} instances) show some distress. "
        else:
            explanation += f"There are minimal signs of distress in their posts ({distress_rate:.0%}). "
        
        # Thinking patterns
        if distortion_rate > 0.3:
            explanation += f"They also show patterns of negative thinking in {distortion_rate:.0%} of comments ({distortion_count} instances). "
        elif distortion_rate > 0.1:
            explanation += f"Occasional negative thinking appears in {distortion_rate:.0%} of their language ({distortion_count} instances). "
        
        # Mood
        if avg_sentiment < -0.2:
            explanation += f"Overall, their tone leans negative. "
        elif avg_sentiment > 0.2:
            explanation += f"Despite challenges, their overall tone remains somewhat positive. "
        
        # Late night
        if late_night_rate > 0.3:
            explanation += f"They're often active late at night ({late_night_rate:.0%} of activity). "
        
        # Risk assessment
        if risk_level == 'High':
            if risk_score >= 80:
                explanation += f"This is a CRITICAL case (score: {risk_score:.1f}/100) needing immediate attention."
            else:
                explanation += f"This is a HIGH RISK case (score: {risk_score:.1f}/100) requiring timely intervention."
        elif risk_level == 'Medium':
            explanation += f"This is a MEDIUM RISK case (score: {risk_score:.1f}/100) that should be monitored."
        else:
            explanation += f"This is a LOW RISK case (score: {risk_score:.1f}/100), but continued monitoring is recommended."
        
        # Determine category
        if risk_level == 'High' and risk_score >= 80:
            category = "Critical"
        elif risk_level == 'High':
            category = "High Risk"
        elif risk_level == 'Medium':
            category = "Moderate Risk"
        elif risk_level == 'Low' and risk_score > 30:
            category = "Monitoring"
        else:
            category = "Low Risk"
        
        # Generate recommendations
        recommendations = []
        if risk_level == 'High':
            recommendations.append("Reach out within 2 hours - needs urgent attention")
            recommendations.append("Discuss with team lead about escalation")
        elif risk_level == 'Medium':
            recommendations.append("Plan to reach out within 24 hours")
            recommendations.append("Monitor for changes in posting patterns")
        else:
            recommendations.append("Check in within the next week")
        
        if distress_rate > 0.4:
            recommendations.append("When reaching out, acknowledge they seem to be struggling")
        
        if late_night_rate > 0.4:
            recommendations.append("Gently check in about sleep and late-night routines")
        
        if risk_level == 'High':
            recommendations.append("Schedule follow-up in 24 hours")
        elif risk_level == 'Medium':
            recommendations.append("Follow up in 3-4 days")
        else:
            recommendations.append("Weekly check-in would be appropriate")
        
        # Ensure we have at least 2 recommendations
        while len(recommendations) < 2:
            recommendations.append("Listen with empathy when you connect")
        
        return {
            'explanation': explanation,
            'llm_category': category,
            'recommendations': recommendations[:3],
            'generated_at': datetime.utcnow().isoformat()
        }


class EnrichedRiskProfile:
    """
    Combines risk profile with LLM-generated insights
    This class is exported for use in feature_engineering.py
    """
    
    def __init__(self, risk_profile: Dict, llm_insights: Dict):
        self.risk_profile = risk_profile
        self.llm_insights = llm_insights
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        return {
            **self.risk_profile,
            'llm_explanation': self.llm_insights.get('explanation', ''),
            'llm_category': self.llm_insights.get('llm_category', 'General Concern'),
            'llm_recommendations': self.llm_insights.get('recommendations', []),
            'llm_generated_at': self.llm_insights.get('generated_at'),
            'has_llm_analysis': self.llm_insights.get('raw_llm_response') is not None
        }


# Export all public classes
__all__ = ['LLMSummarizer', 'EnrichedRiskProfile', 'CaseCategory']