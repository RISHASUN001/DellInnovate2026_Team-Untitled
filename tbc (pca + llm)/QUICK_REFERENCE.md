# PCA + LLM Scoring - Quick Reference Card

## 🎯 What is it?
New risk scoring system using **PCA-learned weights** + **LLM calibration** instead of hand-coded rules.

## 🚀 Quick Commands

### Test the system
```bash
cd backend
python test_pca_scoring.py
```

### Run via API
```bash
# Without LLM (fast)
curl -X POST http://localhost:8000/api/analytics/compute-risk-profiles-pca \
  -H "Content-Type: application/json" \
  -d '{"window_days": 30, "use_llm": false}'

# With LLM (requires Ollama)
curl -X POST http://localhost:8000/api/analytics/compute-risk-profiles-pca \
  -H "Content-Type: application/json" \
  -d '{"window_days": 30, "use_llm": true, "llm_model": "llama2"}'
```

### Run via Python
```python
from analytics.stage2_pca_llm import run_case_scoring
from config.database import MongoDB

db = MongoDB.get_db()
result = await run_case_scoring(
    db=db,
    window_days=30,
    use_llm=False  # Set True if Ollama running
)
```

## 📊 Scoring Pipeline (5 Steps)

```
Stage 1 NLP → Aggregation → PCA → Guardrail → LLM → final_score
                   ↓         ↓        ↓        ↓        ↓
               emotion   learned  prevent   ±0.10   0-1 scale
               sentiment weights  low harm  adjust  + priority
               harm                weight
```

### Step 1: Aggregation (per user)
```python
emotion_score = 0.7 * mean + 0.3 * p90  # distress_emotion
sentiment_score = 0.7 * mean + 0.3 * p90  # is_negative
harm_score = 0.7 * mean + 0.3 * p90  # distortion_flag

# Apply low-data damping
damp = sigmoid((n_units - 8) / 3)
scores *= damp
```

### Step 2: PCA Weight Learning
```python
# Across all users
X = [[emotion, sentiment, harm], ...]
pca = PCA(n_components=1)
risk_score_math = normalize(pca.fit_transform(X))  # → [0,1]
```

### Step 3: Guardrail
```python
base_score = max(risk_score_math, 0.40 * harm_score)
```

### Step 4: LLM Calibration
```python
llm_delta = avg([LLM(prompt), LLM(prompt)])  # Run twice
llm_delta = clamp(llm_delta, -0.10, 0.10)
```

### Step 5: Final Score
```python
final_score = clamp(base_score + llm_delta, 0, 1)

if final_score >= 0.75: priority = 'critical'
elif final_score >= 0.50: priority = 'high'
elif final_score >= 0.30: priority = 'medium'
else: priority = 'low'
```

## 📁 Key Files

| File | Purpose |
|------|---------|
| `analytics/stage2_pca_llm.py` | Main Stage 2 pipeline |
| `analytics/llm_calibration.py` | Ollama LLM integration |
| `models/instagram_models.py` | MongoDB schemas (updated) |
| `routes/analytics_routes.py` | API endpoints (new /pca) |
| `test_pca_scoring.py` | Validation test script |
| `PCA_LLM_SCORING_README.md` | Full documentation |
| `IMPLEMENTATION_SUMMARY.md` | Implementation details |

## 🗄️ Database Fields

### NEW in `text_units_signals`
```javascript
{
  "distress_emotion": 0.45,  // max(fear, anger, sadness)
  "is_negative": 1,          // 1 if negative sentiment
  "distortion_flag": 0,      // 1 if distortion detected
  "created_at": ISODate      // for time windowing
}
```

### NEW in `case_risk_profiles`
```javascript
{
  // Component scores (0-1)
  "emotion_score": 0.45,
  "sentiment_score": 0.62,
  "harm_score": 0.38,
  "n_units": 15,
  "damp": 0.89,
  
  // PCA scoring
  "risk_score_math": 0.58,
  "pc1_loadings": {"emotion": 0.61, "sentiment": 0.53, "harm": 0.58},
  "pca_run_id": "a3b2c1d4",
  
  // Calibration
  "base_score": 0.58,
  "llm_delta": 0.03,
  "final_score": 0.61,
  
  // Result
  "priority_level": "high",  // low, medium, high, critical
  "evidence_unit_ids": ["id1", "id2", ...]
}
```

## 🔌 API Endpoints

### NEW: PCA Scoring
```
POST /api/analytics/compute-risk-profiles-pca
```
**Body:**
```json
{
  "window_days": 30,
  "limit_users": null,
  "use_llm": true,
  "llm_model": "llama2"
}
```

### UPDATED: Full Pipeline
```
POST /api/analytics/run-full-pipeline
```
**New parameters:**
- `use_pca: true` → Use PCA scoring
- `use_llm: true` → Enable LLM calibration

### UPDATED: Query Profiles
```
GET /api/analytics/risk-profiles?priority_level=high
```
**New filter:** `priority_level` (low/medium/high/critical)

## 🐍 Python Examples

### Basic Usage
```python
from analytics.stage2_pca_llm import run_case_scoring

result = await run_case_scoring(
    db=db,
    window_days=30,
    use_llm=False
)

for profile in result['profiles']:
    print(f"{profile['username']}: {profile['final_score']:.3f}")
```

### With LLM Calibration
```python
result = await run_case_scoring(
    db=db,
    window_days=30,
    use_llm=True,
    llm_model="llama2",
    ollama_url="http://localhost:11434"
)
```

### Query MongoDB
```python
# Get high-risk users
profiles = await db.case_risk_profiles.find({
    'priority_level': 'high'
}).sort('final_score', -1).to_list(10)

for p in profiles:
    print(f"{p['case_user']}: {p['final_score']:.3f}")
```

## ⚙️ Configuration

### Hyperparameters (in code)
```python
# Aggregation weights
MEAN_WEIGHT = 0.7
P90_WEIGHT = 0.3

# Damping
DAMPING_THRESHOLD = 8  # text units
DAMPING_STEEPNESS = 3.0

# Guardrail
HARM_MIN_WEIGHT = 0.40

# LLM
LLM_NUM_RUNS = 2
LLM_DELTA_MAX = 0.10
```

### Priority Thresholds
```python
CRITICAL = 0.75  # ≥75%
HIGH = 0.50      # 50-75%
MEDIUM = 0.30    # 30-50%
LOW = 0.0        # <30%
```

## 🔧 Troubleshooting

### Issue: "No signals found"
**Fix:** Run Stage 1 first: `run_nlp_extraction(limit=50)`

### Issue: "Ollama connection refused"
**Fix:** Start Ollama: `ollama serve` (or set `use_llm=false`)

### Issue: "Not enough users for PCA"
**Fix:** PCA needs ≥2 users. System auto-falls back to simple average.

### Issue: All scores are zero
**Fix:** Check Stage 1 outputs: `db.text_units_signals.find_one()`
       Should have `distress_emotion`, `is_negative`, `distortion_flag` > 0

### Issue: PCA weights look weird
**Explanation:** PCA learns from data. Weights vary based on your data distribution. This is normal.

## 📦 Dependencies

```toml
# pyproject.toml
[tool.poetry.dependencies]
scikit-learn = "^1.3.0"  # For PCA
httpx = "^0.28.1"         # For Ollama API (already installed)
```

Install: `poetry install` or `pip install scikit-learn httpx`

## 🧪 Testing

### Quick validation
```bash
python backend/test_pca_scoring.py
```

**Expected output:**
```
✓ TEST 1: PCA Scoring (No LLM) - PASS
✓ TEST 2: PCA with LLM - PASS (if Ollama running)
✓ TEST 3: MongoDB Verification - PASS
```

### Manual checks
```python
# Check Stage 1 fields
signal = await db.text_units_signals.find_one({})
assert 'distress_emotion' in signal
assert 'is_negative' in signal
assert 'distortion_flag' in signal

# Check PCA profile
profile = await db.case_risk_profiles.find_one({}, sort=[('timestamp', -1)])
assert 'final_score' in profile
assert 0.0 <= profile['final_score'] <= 1.0
assert profile['priority_level'] in ['low', 'medium', 'high', 'critical']
```

## 📖 Documentation

1. **Full details:** [PCA_LLM_SCORING_README.md](PCA_LLM_SCORING_README.md)
2. **Implementation:** [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
3. **Original system:** [ANALYTICS_README.md](ANALYTICS_README.md)

## 🎓 Key Concepts

**PCA (Principal Component Analysis):**
- Learns optimal weights from data
- Reduces 3 features to 1 risk score
- More objective than hand-coded weights

**LLM Calibration:**
- Adds human-like judgment
- Bounded (±0.10) to prevent wild swings
- Runs twice for stability
- Optional (can disable)

**Guardrail:**
- Prevents harm_score from being ignored
- If distortions are severe, score can't be too low
- Formula: `base_score ≥ 0.40 * harm_score`

**Damping:**
- Reduces confidence when few text units
- Sigmoid function: smooth transition
- Prevents overconfidence on small samples

## 🔄 Legacy vs PCA

| Feature | Legacy | PCA |
|---------|--------|-----|
| **Weights** | Hand-coded | Learned |
| **Scale** | 0-100 | 0-1 |
| **Calibration** | None | LLM |
| **Guardrails** | None | Yes |
| **Damping** | None | Yes |
| **Evidence** | Samples | IDs |

**Both systems coexist!** Use `use_pca` flag to choose.

## ⚡ Performance

| Operation | Time | Users |
|-----------|------|-------|
| PCA (no LLM) | ~1 sec | 10 |
| PCA + LLM | ~1-2 min | 10 |
| Stage 1 NLP | ~2-3 min | 100 posts |

**Tip:** Use `use_llm=false` for faster testing.

## 🎯 Best Practices

1. **Start without LLM** → Validate PCA first
2. **Test on subset** → Use `limit_users=5` initially
3. **Check outputs** → Verify `final_score`, `priority_level`, `evidence_unit_ids`
4. **Compare systems** → Run both legacy and PCA, compare results
5. **Monitor weights** → PCA loadings should be reasonable (0.2-0.8)

---

**Need more details?** See [PCA_LLM_SCORING_README.md](PCA_LLM_SCORING_README.md)
