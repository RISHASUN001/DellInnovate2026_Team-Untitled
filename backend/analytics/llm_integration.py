"""
LLM Integration for Case Summarization and Categorization
Generates empathetic, user-friendly explanations of risk metrics
"""

import os
import httpx
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger
from pydantic import BaseModel

class CaseCategory(str):
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
    Generates empathetic, plain-language explanations
    """
    
    # List of working free models on OpenRouter (tried and tested)
    WORKING_MODELS = [
        "google/gemini-flash-1.5-8b-exp",  # Google's free model
        "mistralai/mistral-7b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "cohere/command-r7b-12-2024:free",
        "microsoft/phi-3-mini-128k-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "nousresearch/hermes-3-llama-3.1-405b:free"
    ]
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.model = os.getenv("OPENROUTER_MODEL", self.WORKING_MODELS[0])
        
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not found. LLM features will be disabled.")
        
        logger.info(f"LLM Summarizer initialized with primary model: {self.model}")
        logger.info(f"Will try {len(self.WORKING_MODELS)} fallback models if needed")
    
    async def summarize_risk_profile(self, risk_profile: Dict) -> Dict[str, Any]:
        """
        Generate LLM summary and category for a risk profile
        
        Args:
            risk_profile: Complete risk profile document
            
        Returns:
            Dict with summary, category, recommendations, and detailed explanation
        """
        if not self.api_key:
            logger.warning("No API key found, using enhanced fallback summary")
            return self._generate_enhanced_fallback(risk_profile)
        
        # Build prompt once
        prompt = self._build_enhanced_summary_prompt(risk_profile)
        
        # Try primary model with retries
        for attempt in range(3):  # Try primary model 3 times with backoff
            try:
                logger.info(f"Attempt {attempt + 1}/3 with primary model: {self.model}")
                result = await self._try_model_with_retry(self.model, prompt, risk_profile, attempt)
                if result:
                    logger.success(f"LLM analysis successful with model: {self.model}")
                    return result
            except Exception as e:
                wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                logger.warning(f"Primary model attempt {attempt + 1} failed: {e}. Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        # Try fallback models
        for model in self.WORKING_MODELS:
            if model == self.model:
                continue  # Skip if same as primary
            
            try:
                logger.info(f"Trying fallback model: {model}")
                result = await self._try_model_with_retry(model, prompt, risk_profile)
                if result:
                    logger.success(f"LLM analysis successful with fallback model: {model}")
                    # Update the instance model for future use
                    self.model = model
                    return result
            except Exception as e:
                logger.warning(f"Fallback model {model} failed: {e}")
                await asyncio.sleep(1)  # Wait 1 second before trying next model
                continue
        
        # If all models fail, use enhanced fallback
        logger.warning("All LLM models failed, using enhanced fallback summary")
        return self._generate_enhanced_fallback(risk_profile)
    
    async def _try_model_with_retry(self, model: str, prompt: str, risk_profile: Dict, attempt: int = 0) -> Optional[Dict]:
        """Try a specific model with retry logic for rate limits"""
        
        max_retries = 3
        base_delay = 2
        
        for retry in range(max_retries):
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
                                    
                                    Guidelines:
                                    1. Write a single, coherent paragraph that explains the situation
                                    2. Use warm, empathetic language - like you're explaining to a colleague
                                    3. Explain what the data means in simple terms
                                    4. Include specific numbers but frame them contextually
                                    5. Mention emotional patterns and concerning behaviors
                                    6. End with a clear category and 2-3 recommendations
                                    
                                    Remember: The goal is to give youth workers a complete picture they can act on."""
                                },
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ],
                            "temperature": 0.4,
                            "max_tokens": 800
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        llm_output = result['choices'][0]['message']['content']
                        return self._parse_enhanced_llm_response(llm_output, risk_profile)
                    
                    elif response.status_code == 429:  # Rate limit error
                        wait_time = base_delay * (2 ** retry)  # Exponential backoff: 2, 4, 8 seconds
                        logger.warning(f"Rate limited on {model}. Retry {retry + 1}/{max_retries} in {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    else:
                        logger.error(f"Model {model} returned error {response.status_code}: {response.text}")
                        return None
                        
            except Exception as e:
                if retry < max_retries - 1:
                    wait_time = base_delay * (2 ** retry)
                    logger.warning(f"Error with {model}: {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed after {max_retries} retries: {e}")
                    return None
        
        return None
    
    def _build_enhanced_summary_prompt(self, profile: Dict) -> str:
        """Build enhanced prompt for LLM with plain language focus"""
        
        # Extract metrics with clear labels
        case_user = profile.get('case_user', 'this young person')
        risk_score = profile.get('risk_score', 0)
        risk_level = profile.get('risk_level', 'Unknown')
        
        # Distress emotions (sadness, anger, fear)
        distress_count = profile.get('distress_emotion_count', 0)
        distress_rate = profile.get('distress_emotion_rate', 0)
        
        # Cognitive distortions (negative thinking patterns)
        distortion_count = profile.get('distortion_count', 0)
        distortion_rate = profile.get('distortion_rate', 0)
        
        # Sentiment analysis
        avg_sentiment = profile.get('avg_sentiment_score', 0)
        sentiment_std = profile.get('sentiment_std', 0)
        negative_rate = profile.get('negative_sentiment_rate', 0)
        
        # Emotion distribution
        emotion_dist = profile.get('emotion_distribution', {})
        
        # Format emotion distribution nicely
        emotion_text = ""
        for emotion, count in emotion_dist.items():
            if emotion == 'anger':
                emotion_text += f"- Anger: {count} comments (frustration, irritation)\n"
            elif emotion == 'sadness':
                emotion_text += f"- Sadness: {count} comments (sad, down, hurt)\n"
            elif emotion == 'fear':
                emotion_text += f"- Fear: {count} comments (anxious, worried, scared)\n"
            elif emotion == 'joy':
                emotion_text += f"- Joy: {count} comments (happy, positive)\n"
            elif emotion == 'neutral':
                emotion_text += f"- Neutral: {count} comments (factual, balanced)\n"
            else:
                emotion_text += f"- {emotion}: {count} comments\n"
        
        # Key signals
        key_signals = profile.get('key_signals', [])
        signals_text = "\n".join([f"- {s}" for s in key_signals]) if key_signals else "No specific patterns detected"
        
        # Top comments (sanitized)
        top_comments = profile.get('top_distress_comments', [])[:2]
        comments_text = ""
        for i, comment in enumerate(top_comments, 1):
            # Truncate long comments
            if len(comment) > 100:
                comment = comment[:97] + "..."
            comments_text += f"{i}. \"{comment}\"\n"
        
        # Activity patterns
        late_night_rate = profile.get('late_night_activity_rate', 0)
        total_comments = profile.get('total_comments_received', 0)
        total_captions = profile.get('total_captions', 0)
        total_units = profile.get('total_text_units', 0)
        
        # Build the prompt with plain language explanations
        prompt = f"""
Please analyze this youth case and provide a comprehensive explanation.

**Case Information:**
- Young Person: {case_user}
- Overall Risk Score: {risk_score:.1f}/100 ({risk_level} risk)

**Detailed Metrics:**

1. **Emotional State** (from analyzing {total_units} posts/comments):
   - Primary emotions detected: {', '.join([f"{k}: {v}" for k, v in emotion_dist.items()])}
   - Distress rate: {distress_rate:.1%} of communication ({distress_count} comments showing sadness, anger, or fear)
   - Average sentiment: {avg_sentiment:.2f} (on a scale from -1 to 1, where negative means unhappy)
   - Emotional stability: {'High volatility (emotions swing widely)' if sentiment_std > 0.5 else 'Moderate volatility' if sentiment_std > 0.3 else 'Relatively stable'}

2. **Thinking Patterns**:
   - Cognitive distortion rate: {distortion_rate:.1%} of comments ({distortion_count} instances)
   - This includes patterns like catastrophizing, overgeneralization, or hopelessness

3. **Behavioral Patterns**:
   - Late night activity: {late_night_rate:.1%} of posts between 11 PM - 2 AM
   - Engagement: Received {total_comments} comments from others

**Key Observations:**
{signals_text}

**Examples of concerning statements:**
{comments_text}

**Your Task:**
Write a SINGLE, comprehensive paragraph (5-8 sentences) that:

1. Opens with a warm, empathetic statement about the young person
2. Explains their emotional state in plain language (what emotions they're showing)
3. Describes any thinking patterns or cognitive distortions observed
4. Mentions concerning behaviors (like late night activity)
5. Connects the data to what it might mean for their wellbeing
6. Provides context about the risk level

Then, on new lines, provide:
- CATEGORY: [choose one: Critical, High Risk, Moderate Risk, Low Risk, Monitoring, Bullying, Self-Harm Ideation, Anxiety, Depression, Loneliness/Isolation, General Concern]
- RECOMMENDATIONS: [2-3 specific suggestions separated by |]

The explanation should flow naturally, like you're explaining the situation to a fellow youth worker. Avoid bullet points or lists in the explanation paragraph.

Format your response exactly as:

EXPLANATION: [Your comprehensive paragraph here]

CATEGORY: [chosen category]

RECOMMENDATIONS: [recommendation 1 | recommendation 2 | recommendation 3]
"""
        
        return prompt
    
    def _parse_enhanced_llm_response(self, response: str, original_profile: Dict) -> Dict[str, Any]:
        """Parse enhanced LLM response into structured format"""
        result = {
            'explanation': '',  # This will be the comprehensive paragraph
            'llm_category': 'General Concern',
            'recommendations': [],
            'raw_llm_response': response,
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
                    # Start collecting explanation
                    explanation_text = line.replace('EXPLANATION:', '', 1).strip()
                    if explanation_text:
                        explanation_lines.append(explanation_text)
                elif line.startswith('CATEGORY:'):
                    category = line.replace('CATEGORY:', '', 1).strip()
                    # Validate and map category
                    valid_categories = [
                        'Critical', 'High Risk', 'Moderate Risk', 'Low Risk', 
                        'Monitoring', 'Bullying', 'Self-Harm Ideation', 
                        'Anxiety', 'Depression', 'Loneliness/Isolation', 
                        'General Concern'
                    ]
                    # Try to find a close match if exact match fails
                    matched = False
                    for valid in valid_categories:
                        if valid.lower() in category.lower():
                            result['llm_category'] = valid
                            matched = True
                            break
                    if not matched:
                        result['llm_category'] = 'General Concern'
                        
                elif line.startswith('RECOMMENDATIONS:'):
                    rec_text = line.replace('RECOMMENDATIONS:', '', 1).strip()
                    if '|' in rec_text:
                        result['recommendations'] = [r.strip() for r in rec_text.split('|') if r.strip()]
                    else:
                        # Try to split by common delimiters
                        if ',' in rec_text:
                            result['recommendations'] = [r.strip() for r in rec_text.split(',') if r.strip()]
                        else:
                            result['recommendations'] = [rec_text] if rec_text else []
                elif explanation_lines and not any(line.startswith(prefix) for prefix in ['CATEGORY:', 'RECOMMENDATIONS:']):
                    # This is a continuation of the explanation
                    explanation_lines.append(line)
            
            # Join explanation lines into a single paragraph
            if explanation_lines:
                result['explanation'] = ' '.join(explanation_lines)
            
            # If parsing failed or explanation is too short, use enhanced fallback
            if not result['explanation'] or len(result['explanation']) < 50:
                result['explanation'] = self._generate_enhanced_explanation(original_profile)
                result['llm_category'] = self._determine_enhanced_category(original_profile)
                
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            result['explanation'] = self._generate_enhanced_explanation(original_profile)
            result['llm_category'] = self._determine_enhanced_category(original_profile)
        
        # Ensure we have recommendations
        if not result['recommendations']:
            result['recommendations'] = self._generate_enhanced_recommendations(original_profile)
        
        return result
    
    def _generate_enhanced_explanation(self, profile: Dict) -> str:
        """Generate a comprehensive explanation paragraph without LLM"""
        case_user = profile.get('case_user', 'This young person')
        risk_level = profile.get('risk_level', 'Unknown')
        risk_score = profile.get('risk_score', 0)
        distress_rate = profile.get('distress_emotion_rate', 0)
        distress_count = profile.get('distress_emotion_count', 0)
        distortion_rate = profile.get('distortion_rate', 0)
        distortion_count = profile.get('distortion_count', 0)
        avg_sentiment = profile.get('avg_sentiment_score', 0)
        sentiment_std = profile.get('sentiment_std', 0)
        late_night_rate = profile.get('late_night_activity_rate', 0)
        total_units = profile.get('total_text_units', 0)
        
        # Get emotion distribution
        emotion_dist = profile.get('emotion_distribution', {})
        
        # Build a detailed, empathetic explanation
        if case_user != 'Unknown':
            explanation = f"Based on an analysis of {case_user}'s recent Instagram activity ({total_units} posts and comments), "
        else:
            explanation = f"Based on an analysis of {total_units} Instagram posts and comments, "
        
        # Emotional state section
        if emotion_dist:
            # Get dominant emotions
            top_emotions = sorted(emotion_dist.items(), key=lambda x: x[1], reverse=True)[:2]
            emotion_desc = []
            for emotion, count in top_emotions:
                if emotion == 'anger':
                    emotion_desc.append(f"anger (appearing {count} times)")
                elif emotion == 'sadness':
                    emotion_desc.append(f"sadness (appearing {count} times)")
                elif emotion == 'fear':
                    emotion_desc.append(f"anxiety or fear (appearing {count} times)")
                elif emotion == 'joy':
                    emotion_desc.append(f"happiness (appearing {count} times)")
                elif emotion == 'neutral':
                    emotion_desc.append(f"neutral content (appearing {count} times)")
                else:
                    emotion_desc.append(f"{emotion} (appearing {count} times)")
            
            if emotion_desc:
                explanation += f"we can see they're expressing {' and '.join(emotion_desc)}. "
        
        # Distress level
        if distress_rate > 0.5:
            explanation += f"This is concerning because a high proportion ({distress_rate:.0%}) of their communication shows signs of emotional distress - that's {distress_count} out of {total_units} posts containing sadness, anger, or anxiety. "
        elif distress_rate > 0.3:
            explanation += f"There are noticeable signs of emotional distress, with about {distress_rate:.0%} of their posts ({distress_count} instances) expressing difficult emotions like sadness, anger, or worry. "
        elif distress_rate > 0.1:
            explanation += f"There are some mild signs of distress in about {distress_rate:.0%} of their communication ({distress_count} instances). "
        else:
            explanation += f"There are minimal signs of emotional distress in their posts ({distress_rate:.0%}). "
        
        # Thinking patterns
        if distortion_rate > 0.3:
            explanation += f"They also show patterns of negative thinking in {distortion_rate:.0%} of their comments ({distortion_count} instances) - this includes things like catastrophizing (expecting the worst), overgeneralizing (using words like 'always' or 'never'), or expressing hopelessness. "
        elif distortion_rate > 0.1:
            explanation += f"Occasional negative thinking patterns appear in about {distortion_rate:.0%} of their language ({distortion_count} instances). "
        
        # Mood and volatility
        if avg_sentiment < -0.3:
            explanation += f"Overall, their emotional tone leans negative (sentiment score: {avg_sentiment:.2f} on a scale from -1 to 1), "
        elif avg_sentiment > 0.3:
            explanation += f"Despite some concerns, their overall tone remains fairly positive (sentiment score: {avg_sentiment:.2f}), "
        else:
            explanation += f"Their emotional tone is generally neutral (sentiment score: {avg_sentiment:.2f}), "
        
        if sentiment_std > 0.5:
            explanation += f"but their emotions show high volatility (swinging significantly between positive and negative), which could indicate emotional instability. "
        elif sentiment_std > 0.3:
            explanation += f"with some variability in their emotional expression. "
        else:
            explanation += f"and their emotions appear relatively stable. "
        
        # Activity patterns
        if late_night_rate > 0.4:
            explanation += f"A pattern worth noting is that {late_night_rate:.0%} of their activity happens late at night (between 11 PM and 2 AM), which might be affecting their sleep and emotional wellbeing. "
        
        # Risk assessment with clear action guidance
        if risk_level == 'High':
            if risk_score >= 80:
                explanation += f"This case is assessed as **CRITICAL** (risk score: {risk_score:.1f}/100) and requires immediate attention. The combination of high distress, negative thinking patterns, and concerning behaviors suggests the young person may be in significant emotional pain and would benefit from urgent outreach."
            else:
                explanation += f"This is a **HIGH RISK** case (score: {risk_score:.1f}/100) that needs timely intervention. The patterns we're seeing warrant a compassionate check-in within the next 24 hours."
        elif risk_level == 'Medium':
            explanation += f"This is a **MEDIUM RISK** case (score: {risk_score:.1f}/100). While not immediately critical, there are enough concerns to merit proactive outreach and monitoring over the coming days."
        else:
            explanation += f"This is a **LOW RISK** case (score: {risk_score:.1f}/100), but continued gentle monitoring is recommended to ensure the young person's wellbeing."
        
        return explanation
    
    def _determine_enhanced_category(self, profile: Dict) -> str:
        """Determine category with more nuance"""
        risk_level = profile.get('risk_level', 'Low')
        risk_score = profile.get('risk_score', 0)
        distress_rate = profile.get('distress_emotion_rate', 0)
        
        # Check for specific patterns
        emotion_dist = profile.get('emotion_distribution', {})
        
        # If anger is dominant
        if emotion_dist.get('anger', 0) > emotion_dist.get('joy', 0) * 2 and emotion_dist.get('anger', 0) > 3:
            if risk_level == 'High':
                return "High Risk"
            elif risk_level == 'Medium':
                return "Anxiety"
        
        # If sadness is dominant
        if emotion_dist.get('sadness', 0) > 3 and distress_rate > 0.4:
            if risk_score > 70:
                return "Depression"
            else:
                return "Loneliness/Isolation"
        
        # Default by risk level
        if risk_level == 'High' and risk_score >= 80:
            return "Critical"
        elif risk_level == 'High':
            return "High Risk"
        elif risk_level == 'Medium' and distress_rate > 0.4:
            return "Moderate Risk"
        elif risk_level == 'Medium':
            return "Monitoring"
        else:
            return "Low Risk"
    
    def _generate_enhanced_recommendations(self, profile: Dict) -> List[str]:
        """Generate more specific, actionable recommendations"""
        recommendations = []
        risk_level = profile.get('risk_level', 'Low')
        distress_rate = profile.get('distress_emotion_rate', 0)
        distortion_rate = profile.get('distortion_rate', 0)
        late_night_rate = profile.get('late_night_activity_rate', 0)
        
        # Timing-based recommendations
        if risk_level == 'High':
            recommendations.append("Reach out within the next 2 hours if possible")
            recommendations.append("Consider discussing with your team lead - this case may need escalation")
        elif risk_level == 'Medium':
            recommendations.append("Plan to reach out within 24 hours")
            recommendations.append("Keep notes on any changes in their posting patterns")
        else:
            recommendations.append("Check in within the next week - no urgent action needed")
        
        # Content-based recommendations
        if distress_rate > 0.4:
            recommendations.append("When you reach out, acknowledge that they seem to be going through a difficult time. Use phrases like 'I noticed things seem tough right now' rather than directly mentioning the data.")
        
        if distortion_rate > 0.3:
            recommendations.append("They may benefit from gentle reality-checking conversations - help them see that not everything is as negative as it seems.")
        
        if late_night_rate > 0.4:
            recommendations.append("Gently check in about sleep and late-night routines - this might be affecting their mood.")
        
        # Follow-up recommendations
        if risk_level == 'High':
            recommendations.append("Schedule a follow-up in 24-48 hours after initial contact")
        elif risk_level == 'Medium':
            recommendations.append("Check back in 3-4 days after reaching out")
        else:
            recommendations.append("A weekly check-in would be appropriate")
        
        # Ensure we have at least 2 recommendations
        while len(recommendations) < 2:
            recommendations.append("Listen with empathy and without judgment when you connect")
        
        return recommendations[:3]
    
    def _generate_enhanced_fallback(self, profile: Dict) -> Dict[str, Any]:
        """Generate enhanced fallback summary without LLM"""
        return {
            'explanation': self._generate_enhanced_explanation(profile),
            'llm_category': self._determine_enhanced_category(profile),
            'recommendations': self._generate_enhanced_recommendations(profile),
            'raw_llm_response': None,
            'generated_at': datetime.utcnow().isoformat()
        }


class EnrichedRiskProfile:
    """
    Combines risk profile with LLM-generated insights
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