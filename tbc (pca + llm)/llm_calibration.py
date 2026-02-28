"""
LLM-based Risk Score Calibration using Ollama

Provides bounded delta adjustment (±0.10) to mathematical risk scores
based on qualitative review of evidence comments.
"""

import json
import httpx
from typing import List, Dict, Optional, Tuple
from loguru import logger
import numpy as np


class LLMCalibrator:
    """
    LLM-based risk score calibration using Ollama
    """
    
    def __init__(self, 
                 model: str = "llama2",
                 ollama_url: str = "http://localhost:11434",
                 timeout: int = 30):
        """
        Initialize LLM calibrator
        
        Args:
            model: Ollama model name (e.g., "llama2", "mistral")
            ollama_url: Ollama API endpoint
            timeout: Request timeout in seconds
        """
        self.model = model
        self.ollama_url = ollama_url
        self.timeout = timeout
        
    def _build_prompt(self,
                     case_user: str,
                     emotion_score: float,
                     sentiment_score: float,
                     harm_score: float,
                     n_units: int,
                     evidence_texts: List[str]) -> str:
        """
        Build calibration prompt for LLM
        
        Args:
            case_user: Username being assessed
            emotion_score: Computed emotion score (0-1)
            sentiment_score: Computed sentiment score (0-1)
            harm_score: Computed harm/distortion score (0-1)
            n_units: Number of text units analyzed
            evidence_texts: Sample concerning comments
            
        Returns:
            Formatted prompt string
        """
        evidence_block = "\n".join([f"{i+1}. \"{text}\"" 
                                   for i, text in enumerate(evidence_texts[:8])])
        
        prompt = f"""You are a youth mental health risk assessment specialist. Review this case summary and provide a small numerical adjustment to refine the algorithmic risk score.

**Case: {case_user}**

**Algorithmic Scores (0-1 scale):**
- Emotion Score (distress): {emotion_score:.3f}
- Sentiment Score (negativity): {sentiment_score:.3f}
- Harm Score (distortions): {harm_score:.3f}
- Text Units Analyzed: {n_units}

**Evidence Comments:**
{evidence_block}

**Task:**
Based on the evidence, determine if the mathematical scores need a small adjustment.

Consider:
- Do the comments show genuine distress or just casual language?
- Is context missing that would increase/decrease concern?
- Are distortions severe or mild?
- Does the overall pattern suggest underestimation or overestimation?

**Output Format (JSON only):**
Return ONLY a JSON object with a single "delta" field.

Rules:
- delta must be between -0.10 and +0.10
- Positive delta = increase risk (more concerning than scores suggest)
- Negative delta = decrease risk (less concerning than scores suggest)
- Zero delta = scores are appropriate

Example outputs:
{{"delta": 0.05}}
{{"delta": -0.03}}
{{"delta": 0.0}}

Your JSON response:"""

        return prompt
    
    async def _call_ollama(self, prompt: str) -> Optional[float]:
        """
        Call Ollama API and extract delta
        
        Args:
            prompt: Prompt to send to LLM
            
        Returns:
            Delta value or None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json"  # Request JSON format
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Ollama API error: {response.status_code}")
                    return None
                
                result = response.json()
                response_text = result.get('response', '').strip()
                
                # Parse JSON response
                try:
                    parsed = json.loads(response_text)
                    delta = float(parsed.get('delta', 0.0))
                    
                    # Clamp to ±0.10
                    delta = max(-0.10, min(0.10, delta))
                    
                    return delta
                    
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.warning(f"Failed to parse LLM response: {e}")
                    logger.debug(f"Response was: {response_text[:200]}")
                    return None
                    
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None
    
    async def calibrate_score(self,
                            case_user: str,
                            emotion_score: float,
                            sentiment_score: float,
                            harm_score: float,
                            n_units: int,
                            evidence_texts: List[str],
                            num_runs: int = 2) -> Dict:
        """
        Run LLM calibration with multiple attempts
        
        Args:
            case_user: Username
            emotion_score: Emotion score
            sentiment_score: Sentiment score
            harm_score: Harm score
            n_units: Number of text units
            evidence_texts: Evidence comments
            num_runs: Number of LLM runs to average (default: 2)
            
        Returns:
            Dict with delta1, delta2, llm_delta (averaged)
        """
        logger.info(f"Running LLM calibration for {case_user} ({num_runs} runs)...")
        
        prompt = self._build_prompt(
            case_user, emotion_score, sentiment_score, 
            harm_score, n_units, evidence_texts
        )
        
        deltas = []
        
        for i in range(num_runs):
            delta = await self._call_ollama(prompt)
            if delta is not None:
                deltas.append(delta)
                logger.info(f"  Run {i+1}: delta = {delta:+.3f}")
            else:
                logger.warning(f"  Run {i+1}: failed (using 0.0)")
                deltas.append(0.0)
        
        # Compute average delta
        if len(deltas) >= 2:
            # Use median if we have 2+ runs (more robust)
            llm_delta = float(np.median(deltas))
        elif len(deltas) == 1:
            llm_delta = deltas[0]
        else:
            llm_delta = 0.0
        
        result = {
            'delta1': deltas[0] if len(deltas) > 0 else 0.0,
            'delta2': deltas[1] if len(deltas) > 1 else 0.0,
            'llm_delta': llm_delta,
            'num_runs': len(deltas)
        }
        
        logger.info(f"  Final LLM delta: {llm_delta:+.3f}")
        
        return result


async def calibrate_with_llm(
    case_user: str,
    emotion_score: float,
    sentiment_score: float,
    harm_score: float,
    n_units: int,
    evidence_texts: List[str],
    model: str = "llama2",
    ollama_url: str = "http://localhost:11434"
) -> Dict:
    """
    Convenience function for LLM calibration
    
    Args:
        case_user: Username
        emotion_score: Emotion score (0-1)
        sentiment_score: Sentiment score (0-1)
        harm_score: Harm score (0-1)
        n_units: Number of text units
        evidence_texts: Evidence comments
        model: Ollama model name
        ollama_url: Ollama endpoint
        
    Returns:
        Dict with delta1, delta2, llm_delta
    """
    calibrator = LLMCalibrator(model=model, ollama_url=ollama_url)
    return await calibrator.calibrate_score(
        case_user, emotion_score, sentiment_score, 
        harm_score, n_units, evidence_texts
    )
