"""backend/decision_layer.py

Bounded LLM refinement layer.
- LLM NEVER replaces math score.
- LLM can only output a small delta in [-0.10, +0.10].
- Final score is clamped to [0,1].
- Stability rule: run twice; if disagreement too large, choose conservative delta.

Designed for Ollama (local).
"""

from __future__ import annotations

import json
from typing import Callable, Dict, Tuple

import requests


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def make_ollama_caller(
    *,
    model: str = "llama3.2:3b",
    host: str = "http://localhost:11434",
    timeout_s: int = 25,
    temperature: float = 0.0,
    num_predict: int = 160,
) -> Callable[[str], str]:
    """Returns a function(prompt)->text that calls Ollama chat API."""

    def _call(prompt: str) -> str:
        r = requests.post(
            f"{host}/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [{"role": "user", "content": prompt}],
                "options": {
                    "temperature": temperature,
                    "num_predict": num_predict,
                },
            },
            timeout=timeout_s,
        )
        r.raise_for_status()
        return r.json()["message"]["content"]

    return _call


def bounded_llm_refinement(
    *,
    base_score: float,
    emotion_score: float,
    sentiment_score: float,
    harm_score: float,
    evidence_text: str,
    call_llm: Callable[[str], str],
    max_delta: float = 0.10,
) -> Tuple[float, Dict]:
    """Single pass bounded refinement. Returns (final_score, info)."""
    prompt = f"""Return STRICT JSON only: {{"delta": <number>}}.

Rules:
- delta must be between -{max_delta} and +{max_delta}
- prefer delta close to 0 unless evidence is strong
- do not invent facts
- be conservative

Inputs:
emotion_score={emotion_score:.4f}
sentiment_score={sentiment_score:.4f}
harm_score={harm_score:.4f}
base_score={base_score:.4f}

Evidence (may be empty):
{evidence_text}
"""

    raw = call_llm(prompt).strip()

    try:
        obj = json.loads(raw)
        delta = float(obj.get("delta", 0.0))
    except Exception as e:
        # Safe fallback: no adjustment
        return clamp01(base_score), {"delta": 0.0, "raw": raw, "error": f"non_json_output: {e}"}

    # Clamp delta
    if delta > max_delta:
        delta = max_delta
    if delta < -max_delta:
        delta = -max_delta

    final = clamp01(base_score + delta)
    return final, {"delta": float(delta), "raw": obj}


def stable_llm_refinement(
    *,
    base_score: float,
    emotion_score: float,
    sentiment_score: float,
    harm_score: float,
    evidence_text: str,
    call_llm: Callable[[str], str],
    max_delta: float = 0.10,
    disagreement_tol: float = 0.05,
) -> Tuple[float, Dict]:
    """Two-pass stability rule."""
    s1, info1 = bounded_llm_refinement(
        base_score=base_score,
        emotion_score=emotion_score,
        sentiment_score=sentiment_score,
        harm_score=harm_score,
        evidence_text=evidence_text,
        call_llm=call_llm,
        max_delta=max_delta,
    )
    s2, info2 = bounded_llm_refinement(
        base_score=base_score,
        emotion_score=emotion_score,
        sentiment_score=sentiment_score,
        harm_score=harm_score,
        evidence_text=evidence_text,
        call_llm=call_llm,
        max_delta=max_delta,
    )

    diff = abs(s1 - s2)
    if diff <= disagreement_tol:
        final = (s1 + s2) / 2.0
        return clamp01(final), {"mode": "avg", "diff": diff, "delta": (info1.get("delta", 0.0) + info2.get("delta", 0.0)) / 2.0, "pass1": info1, "pass2": info2}

    # Conservative: choose smaller |delta|
    d1 = float(info1.get("delta", 0.0))
    d2 = float(info2.get("delta", 0.0))
    chosen = d1 if abs(d1) <= abs(d2) else d2
    final = clamp01(base_score + chosen)
    return final, {"mode": "conservative", "diff": diff, "chosen_delta": chosen, "pass1": info1, "pass2": info2}
