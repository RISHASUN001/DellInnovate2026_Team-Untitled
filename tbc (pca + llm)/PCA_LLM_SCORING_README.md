# PCA + LLM Risk Scoring System

## Overview

This document describes the new **PCA-based risk profiling with LLM calibration** scoring system, which replaces the legacy hand-coded feature engineering approach.

## Architecture

### Stage 1: NLP Signal Extraction (Unchanged)
- Extracts text units (captions + comments) from Instagram posts
- Runs 3 NLP models: sentiment analysis, emotion detection, cognitive distortion detection
- Stores per-text-unit signals in `text_units_signals` collection
- **New fields added:**
  - `distress_emotion`: max(p_anger, p_sadness, p_fear) from emotion probabilities
  - `is_negative`: 1 if sentiment is negative, 0 otherwise
  - `distortion_flag`: alias for distortion_indicator (0 or 1)
  - `created_at`: timestamp for time windowing

### Stage 2: PCA-based Risk Profiling (NEW)
Replaces hand-coded weights with data-driven approach:

#### Step 1: Per-User Aggregation
For each user, aggregate signals over time window (default: 30 days):

```python
emotion_score = 0.7 * mean(distress_emotion) + 0.3 * p90(distress_emotion)
sentiment_score = 0.7 * mean(is_negative) + 0.3 * p90(is_negative)
harm_score = 0.7 * mean(distortion_flag) + 0.3 * p90(distortion_flag)
```

**Low-data damping:** Apply sigmoid function to reduce confidence for small samples:
```python
damp = sigmoid((n_units - 8) / 3)
emotion_score *= damp
sentiment_score *= damp
harm_score *= damp
```

#### Step 2: PCA Weight Learning
Run PCA across all users to learn weights:
- Standardize the 3 feature scores
- Extract first principal component (PC1)
- PC1 loadings become the learned weights
- Normalize PC1 scores to [0, 1] → **risk_score_math**

#### Step 3: Guardrail
Prevent underweighting of severe distortions:
```python
base_score = max(risk_score_math, 0.40 * harm_score)
```

#### Step 4: LLM Calibration
Use Ollama LLM to provide bounded delta adjustment:
- Build prompt with user scores + evidence comments
- Run LLM twice and average for stability
- LLM returns JSON: `{"delta": <float>}`
- Clamp delta to [-0.10, +0.10]
- **final_score** = clamp(base_score + llm_delta, 0, 1)

#### Step 5: Priority Assignment
```python
if final_score >= 0.75: priority_level = 'critical'
elif final_score >= 0.50: priority_level = 'high'
elif final_score >= 0.30: priority_level = 'medium'
else: priority_level = 'low'
```

## Key Differences from Legacy System

| Aspect | Legacy | PCA + LLM |
|--------|--------|-----------|
| **Weights** | Hand-coded (distortion 25%, volatility 20%, etc.) | Learned via PCA |
| **Score Scale** | 0-100 | 0-1 |
| **Aggregation** | Simple average | Mean + p90 weighted |
| **Low-data Handling** | None | Sigmoid damping |
| **Calibration** | None | LLM-based (±0.10) |
| **Guardrails** | None | Minimum harm weight |
| **Evidence Tracking** | Sample comments | Unit IDs + texts |

## MongoDB Schema

### New Fields in `case_risk_profiles`

```javascript
{
  // New PCA fields
  "emotion_score": 0.45,        // 0-1, damped emotion distress
  "sentiment_score": 0.62,       // 0-1, damped negativity
  "harm_score": 0.38,            // 0-1, damped distortion rate
  "n_units": 15,                 // Number of text units analyzed
  "damp": 0.89,                  // Low-data damping factor
  
  "risk_score_math": 0.58,       // PCA-derived score [0,1]
  "pc1_loadings": {              // PCA weights learned
    "emotion": 0.61,
    "sentiment": 0.53,
    "harm": 0.58
  },
  "pca_run_id": "a3b2c1d4",     // PCA batch identifier
  
  "base_score": 0.58,            // Guardrailed score
  "llm_delta": 0.03,             // LLM adjustment
  "llm_delta1": 0.02,            // First LLM run
  "llm_delta2": 0.04,            // Second LLM run
  "final_score": 0.61,           // Final calibrated score [0,1]
  
  "priority_level": "high",      // low/medium/high/critical
  "evidence_unit_ids": [         // Key text units for explainability
    "507f1f77bcf86cd799439011",
    "507f1f77bcf86cd799439012"
  ],
  
  // Legacy fields still present for backward compatibility
  "risk_score": 61.0,            // Converted to 0-100 scale
  "risk_level": "High",
  "priority": 1,
  ...
}
```

## API Endpoints

### New Endpoint: PCA-based Scoring

```
POST /api/analytics/compute-risk-profiles-pca
```

**Request:**
```json
{
  "window_days": 30,
  "limit_users": null,
  "use_llm": true,
  "llm_model": "llama2",
  "ollama_url": "http://localhost:11434"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "PCA-based risk profiling completed",
  "results": {
    "success": true,
    "n_profiles": 5,
    "pca_run_id": "a3b2c1d4",
    "profiles": [...]
  },
  "started_at": "2024-01-15T10:30:00Z"
}
```

### Updated Endpoint: Full Pipeline

```
POST /api/analytics/run-full-pipeline
```

**Request (with PCA):**
```json
{
  "case_users": null,
  "window_days": 30,
  "limit_posts": null,
  "use_pca": true,
  "use_llm": true,
  "llm_model": "llama2"
}
```

### Legacy Endpoint (Still Available)

```
POST /api/analytics/compute-risk-profiles
```

Uses hand-coded feature engineering (backward compatible).

## Usage Examples

### 1. Run PCA Scoring Only

```python
import httpx

response = await httpx.post(
    "http://localhost:8000/api/analytics/compute-risk-profiles-pca",
    json={
        "window_days": 30,
        "use_llm": True,
        "llm_model": "llama2"
    }
)

print(response.json())
```

### 2. Run Full Pipeline with PCA

```python
response = await httpx.post(
    "http://localhost:8000/api/analytics/run-full-pipeline",
    json={
        "use_pca": True,
        "window_days": 30,
        "use_llm": True
    }
)
```

### 3. Test Without LLM (Faster)

```python
response = await httpx.post(
    "http://localhost:8000/api/analytics/compute-risk-profiles-pca",
    json={
        "window_days": 30,
        "use_llm": False  # Skip LLM calibration
    }
)
```

## Notebook Example

```python
# In analytics_demo.ipynb

# Ensure Stage 1 signals exist
stage1_result = await run_nlp_extraction(limit=50)

# Run PCA scoring
from analytics.stage2_pca_llm import run_case_scoring
from config.database import MongoDB

db = MongoDB.get_db()

result = await run_case_scoring(
    db=db,
    window_days=30,
    limit_users=5,  # Test on 5 users first
    use_llm=True,
    llm_model="llama2"
)

print(f"Processed {result['n_profiles']} users")
print(f"PCA run ID: {result['pca_run_id']}")

# View a profile
for profile in result['profiles']:
    print(f"\nUser: {profile['username']}")
    print(f"  Emotion: {profile['emotion_score']:.3f}")
    print(f"  Sentiment: {profile['sentiment_score']:.3f}")
    print(f"  Harm: {profile['harm_score']:.3f}")
    print(f"  Risk (math): {profile['risk_score_math']:.3f}")
    print(f"  Base score: {profile['base_score']:.3f}")
    print(f"  LLM delta: {profile['llm_delta']:+.3f}")
    print(f"  Final score: {profile['final_score']:.3f}")
    print(f"  Priority: {profile['priority_level']}")
```

## LLM Requirements

### Setup Ollama

1. Install Ollama: https://ollama.ai/
2. Pull a model:
   ```bash
   ollama pull llama2
   # or
   ollama pull mistral
   ```
3. Ensure Ollama is running:
   ```bash
   ollama serve  # Usually runs on port 11434
   ```

### LLM Prompt Design

The system sends this information to the LLM:
- Username
- Emotion, sentiment, harm scores (0-1)
- Number of text units analyzed
- Top 8 evidence comments

LLM must return:
```json
{"delta": <float between -0.10 and 0.10>}
```

### LLM Calibration Benefits

- **Context awareness:** LLM can detect sarcasm, casual language, cultural nuances
- **Bounded influence:** Delta clamped to ±0.10 prevents wild adjustments
- **Stability:** Runs twice and uses median to reduce variance
- **Fallback:** If LLM fails or returns invalid JSON, delta = 0 (no calibration)

## Validation and Sanity Checks

Before deploying to production, verify:

1. **Stage 1 fields populated:**
   ```python
   # Check that distress_emotion, is_negative, distortion_flag exist
   sample = await db.text_units_signals.find_one({})
   assert 'distress_emotion' in sample
   assert 'is_negative' in sample
   assert 'distortion_flag' in sample
   ```

2. **PCA weights not degenerate:**
   ```python
   # Check that loadings are reasonable
   assert 0.2 <= abs(pc1_loadings['emotion']) <= 0.8
   assert 0.2 <= abs(pc1_loadings['sentiment']) <= 0.8
   assert 0.2 <= abs(pc1_loadings['harm']) <= 0.8
   ```

3. **Guardrail active:**
   ```python
   # For high harm_score, base_score should be elevated
   if harm_score > 0.7:
       assert base_score >= 0.4 * harm_score
   ```

4. **Final score bounded:**
   ```python
   # All final scores must be in [0, 1]
   assert 0.0 <= final_score <= 1.0
   ```

5. **LLM delta bounded:**
   ```python
   # Delta must be within ±0.10
   assert -0.10 <= llm_delta <= 0.10
   ```

## Performance Considerations

- **Stage 1 (NLP):** ~1-2 seconds per post (3 models)
- **Stage 2 (PCA):** ~0.1 seconds per user (without LLM)
- **LLM calibration:** ~5-10 seconds per user (2 runs)

**Time estimate for 100 posts, 10 users:**
- Stage 1: ~2-3 minutes
- Stage 2 (no LLM): ~1 second
- Stage 2 (with LLM): ~1-2 minutes

**Optimization tips:**
1. Run Stage 1 once, then iterate on Stage 2 scoring
2. Use `use_llm=False` during testing/development
3. Use `limit_users` parameter to test on subset
4. Consider caching LLM responses for identical prompts

## Troubleshooting

### Issue: LLM calibration fails
**Solution:** Set `use_llm=False` to skip LLM and use base_score only

### Issue: Not enough users for PCA
**Solution:** PCA requires at least 2 users. System falls back to simple average if n_users < 2

### Issue: All scores are zero
**Solution:** Check that Stage 1 signals exist and have non-zero distress_emotion, is_negative, distortion_flag

### Issue: Ollama connection refused
**Solution:** Ensure Ollama is running: `ollama serve`

### Issue: PCA weights seem wrong
**Solution:** This is normal variance. PCA learns from data. Check that input features have sufficient variance.

## Migration from Legacy System

If you have existing risk profiles from legacy system:

1. **Both systems coexist:** Old profiles have `risk_score` (0-100), new ones have `final_score` (0-1)
2. **Convert legacy to new scale:** `final_score ≈ risk_score / 100`
3. **Query endpoints support both:** `/risk-profiles` sorts by `final_score` if available, falls back to `risk_score`
4. **Gradual migration:** Run PCA scoring for new cases, keep legacy profiles for old ones

## References

- **PCA:** sklearn.decomposition.PCA
- **Ollama:** https://ollama.ai/
- **Damping function:** Sigmoid with threshold=8, steepness=3
- **Aggregation:** 70% mean + 30% p90 (empirically tuned)
- **Guardrail weight:** 0.40 for harm_score (prevents underweighting severe cases)
- **LLM delta bounds:** ±0.10 (10% of score range)

## Future Enhancements

Potential improvements:
1. **Dynamic thresholds:** Learn damping threshold and aggregation weights from data
2. **Multi-model LLM:** Ensemble of different LLMs for more robust calibration
3. **Temporal PCA:** Separate PCA models for different time windows
4. **Explanations:** Generate natural language explanations for risk scores
5. **Active learning:** Use youth worker feedback to retrain PCA weights
