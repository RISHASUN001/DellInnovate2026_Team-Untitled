# 🧠 Emotional Distress Detection Analytics System

A comprehensive NLP analytics pipeline that processes social media data to detect early warning signs of emotional distress in youth, enabling proactive intervention by social workers.

## 📋 Table of Contents

- [System Overview](#system-overview)
- [Architecture](#architecture)
- [NLP Models](#nlp-models)
- [Pipeline Stages](#pipeline-stages)
- [Installation](#installation)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Database Collections](#database-collections)
- [Configuration](#configuration)

## 🎯 System Overview

This system analyzes Instagram posts and comments to identify youth at risk of emotional distress. It uses state-of-the-art NLP models to detect:

- **Negative sentiment patterns** and volatility
- **Distress emotions** (sadness, anger, fear)
- **Cognitive distortions** (catastrophizing, hopelessness, etc.)
- **Behavioral changes** (engagement patterns, late-night activity)

The system provides **human-in-the-loop** support by ranking cases by risk level, allowing youth workers to prioritize interventions.

## 🏗️ Architecture

```
Instagram Data (MongoDB)
         ↓
┌─────────────────────────────────────┐
│   Stage 1: NLP Signal Extraction    │
│  - Sentiment Analysis                │
│  - Emotion Detection                 │
│  - Cognitive Distortion Detection    │
└─────────────────────────────────────┘
         ↓
  text_units_signals (MongoDB)
         ↓
┌─────────────────────────────────────┐
│ Stage 2: Feature Engineering        │
│  - Aggregate signals per user       │
│  - Compute distortion metrics       │
│  - Analyze sentiment volatility     │
│  - Calculate risk scores            │
└─────────────────────────────────────┘
         ↓
  case_risk_profiles (MongoDB)
         ↓
    Youth Worker Dashboard
```

## 🤖 NLP Models

### 1. Sentiment Analysis
**Model:** `cardiffnlp/twitter-roberta-base-sentiment-latest`

Detects emotional polarity:
- **Negative** - Distress, criticism, hostility
- **Neutral** - Factual, informational
- **Positive** - Support, encouragement

**Output:** Sentiment label, confidence score, numeric sentiment score (-1 to 1)

### 2. Emotion Detection
**Model:** `j-hartmann/emotion-english-distilroberta-base`

Identifies specific emotions:
- **Distress emotions:** sadness, anger, fear
- **Other emotions:** joy, surprise, disgust, neutral

**Output:** Primary emotion, distress flag, distress score

### 3. Cognitive Distortion Detection
**Model:** `sentence-transformers/all-MiniLM-L6-v2`

Detects distorted thinking patterns:
- **Overgeneralization** - "I always fail", "Nothing ever works"
- **All-or-nothing thinking** - "I'm completely worthless"
- **Catastrophizing** - "This is the worst thing ever"
- **Hopelessness** - "There's no point", "I give up"

**Method:** Sentence embedding similarity with distortion templates

**Output:** Distortion flag, distortion category, similarity score

## 📊 Pipeline Stages

### Stage 1: NLP Signal Extraction

**Purpose:** Analyze individual text units (captions/comments)

**Process:**
1. Extract text from Instagram posts in MongoDB
2. Preprocess text (remove URLs, normalize whitespace)
3. Run through all 3 NLP models
4. Store enriched signals in `text_units_signals` collection
5. Export to CSV (`nlp_signals.csv`)

**Runtime:** ~2-5 seconds per text unit

**Output:**
```python
{
  "case_user": "username",
  "text": "original comment text",
  "sentiment_label": "negative",
  "sentiment_score": -0.72,
  "emotion_label": "sadness",
  "is_distress": true,
  "distortion_indicator": 1,
  "distortion_category": "hopelessness",
  ...
}
```

### Stage 2: Behavioral Feature Engineering

**Purpose:** Aggregate signals into case-level risk profiles

**Process:**
1. Fetch all signals for each case user (time-windowed)
2. Compute distortion metrics (rate, trends, categories)
3. Analyze sentiment volatility (std deviation, polarity shifts)
4. Detect engagement anomalies (volume spikes, late-night activity)
5. Calculate composite risk score (0-100)
6. Extract supporting evidence (top concerning comments)
7. Store profiles in `case_risk_profiles` collection

**Risk Scoring Formula:**
```
risk_score = (
  distortion_rate * 25% +
  sentiment_volatility * 20% +
  negative_sentiment * 15% +
  distress_emotions * 25% +
  engagement_abnormality * 15%
)
```

**Risk Levels:**
- **High** (≥70) - Priority 1, urgent review needed
- **Medium** (40-69) - Priority 2, monitor closely
- **Low** (<40) - Priority 3, routine monitoring

**Output:**
```python
{
  "case_user": "username",
  "risk_score": 78.5,
  "risk_level": "High",
  "priority": 1,
  "distortion_rate": 0.35,
  "sentiment_std": 0.68,
  "distress_emotion_rate": 0.42,
  "key_signals": [
    "High cognitive distortion rate: 35%",
    "Elevated distress emotions: 42%"
  ],
  "top_distress_comments": [...],
  ...
}
```

## 🚀 Installation

### 1. Install Dependencies

```bash
cd backend
poetry install
```

Or using pip:
```bash
pip install -r requirements.txt
```

### 2. Download NLP Models

Models are automatically downloaded on first use. Ensure you have:
- Internet connection
- ~2GB disk space for models
- Sufficient RAM (4GB minimum, 8GB recommended)

### 3. Configure Environment

Create `.env` file:
```env
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/database
MONGODB_DB_NAME=instagram_scraper
SCRAPFLY_KEY=your_scrapfly_key
```

### 4. Initialize Database

```python
from config.database import MongoDB
await MongoDB.connect_db()
```

## 💻 Usage

### Option 1: Using the Jupyter Notebook

Open and run `analytics_demo.ipynb` for an interactive walkthrough.

### Option 2: Using Python API

```python
from analytics.signal_extraction import run_nlp_extraction
from analytics.feature_engineering import run_feature_engineering

# Stage 1: Extract NLP signals
stage1_results = await run_nlp_extraction(
    case_users=None,  # Process all users
    limit=100          # Process first 100 posts
)

# Stage 2: Compute risk profiles
stage2_results = await run_feature_engineering(
    case_users=None,  # Process all users with signals
    window_days=7      # 7-day analysis window
)
```

### Option 3: Using REST API

Start the server:
```bash
cd backend
uvicorn app:app --reload --port 8000
```

Run full pipeline:
```bash
curl -X POST http://localhost:8000/api/analytics/run-full-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "case_users": null,
    "window_days": 7,
    "limit_posts": 100
  }'
```

Get risk profiles:
```bash
curl http://localhost:8000/api/analytics/risk-profiles?risk_level=High
```

## 📡 API Documentation

### Analytics Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analytics/extract-signals` | POST | Run Stage 1 (NLP extraction) |
| `/api/analytics/compute-risk-profiles` | POST | Run Stage 2 (feature engineering) |
| `/api/analytics/run-full-pipeline` | POST | Run both stages |
| `/api/analytics/risk-profiles` | GET | Query risk profiles with filters |
| `/api/analytics/risk-profiles/{username}` | GET | Get profile for specific user |
| `/api/analytics/signals/{username}` | GET | Get NLP signals for user |
| `/api/analytics/stats` | GET | Get overall statistics |

### Request Example

```json
POST /api/analytics/run-full-pipeline
{
  "case_users": ["user1", "user2"],  // Optional: specific users
  "window_days": 7,                   // Analysis time window
  "limit_posts": 50                   // Max posts to process in Stage 1
}
```

### Response Example

```json
{
  "status": "success",
  "message": "Full analytics pipeline completed",
  "started_at": "2026-02-28T10:30:00",
  "results": {
    "stage1_nlp_extraction": {
      "text_units_found": 234,
      "signals_created": 189,
      "duration_seconds": 45.2
    },
    "stage2_feature_engineering": {
      "profiles_created": 12,
      "high_risk_cases": ["user1"],
      "duration_seconds": 8.1
    }
  }
}
```

## 🗄️ Database Collections

### `text_units_signals`
Stores NLP analysis results for individual text units.

**Schema:**
```javascript
{
  case_user: String,           // Post owner username
  text_type: String,           // "caption" or "comment"
  text: String,                // Original text
  post_id: String,
  author: String,              // Comment author
  
  sentiment_label: String,     // "negative", "neutral", "positive"
  sentiment_score: Number,     // -1 to 1
  
  emotion_label: String,       // "sadness", "anger", "fear", etc.
  is_distress: Boolean,
  distress_score: Number,      // 0 to 1
  
  distortion_indicator: Number, // 0 or 1
  distortion_category: String,  // "hopelessness", etc.
  
  processed_at: Date
}
```

### `case_risk_profiles`
Stores aggregated risk assessments per user.

**Schema:**
```javascript
{
  case_user: String,
  risk_score: Number,          // 0-100
  risk_level: String,          // "Low", "Medium", "High"
  priority: Number,            // 1, 2, or 3
  
  distortion_rate: Number,     // 0-1
  sentiment_std: Number,       // Volatility measure
  distress_emotion_rate: Number,
  
  key_signals: [String],       // Human-readable signals
  top_distress_comments: [String],
  
  computed_at: Date,
  last_updated: Date
}
```

## ⚙️ Configuration

### Risk Scoring Weights

Adjust in `backend/analytics/feature_engineering.py`:

```python
risk_score = (
    distortion_score * 0.25 +      # Cognitive distortions
    sentiment_volatility * 0.20 +   # Emotional instability
    negative_sentiment * 0.15 +     # Negativity
    distress_emotion * 0.25 +       # Distress emotions
    engagement_abnormality * 0.15   # Behavioral changes
)
```

### Risk Level Thresholds

```python
if risk_score >= 70:  # High risk
    priority = 1
elif risk_score >= 40:  # Medium risk
    priority = 2
else:  # Low risk
    priority = 3
```

### Distortion Detection Threshold

Adjust in `backend/analytics/nlp_models.py`:

```python
CognitiveDistortionDetector(threshold=0.6)  # 0-1, higher = stricter
```

## 📈 Performance

**Stage 1 (NLP Extraction):**
- ~2-5 seconds per text unit (CPU)
- ~0.5-1 seconds per text unit (GPU)
- Batch processing supported

**Stage 2 (Feature Engineering):**
- ~1-2 seconds per user
- Highly efficient (pure Python/NumPy)

**Typical Workload:**
- 1000 posts → ~30-60 minutes (Stage 1)
- 50 users → ~2-3 minutes (Stage 2)

## 🔒 Privacy & Ethics

### Data Handling
- ✅ Only public Instagram data is analyzed
- ✅ Original social media content is NOT stored permanently
- ✅ Data refreshed every 6 hours to minimize retention
- ✅ Signals are aggregated and anonymized where possible

### Human-in-the-Loop
- ✅ AI provides **guidance only**, not decisions
- ✅ Youth workers make all intervention decisions
- ✅ Risk scores are **supportive tools**, not deterministic
- ✅ False positives are expected and acceptable

### Ethical Guidelines
- Use trauma-informed language in all outreach
- Respect youth autonomy and consent
- Escalate high-risk cases to trained professionals
- Regular model audits for bias and fairness

## 🛠️ Troubleshooting

### Models not loading
```bash
# Clear Hugging Face cache
rm -rf ~/.cache/huggingface

# Re-download models
python -c "from analytics.nlp_models import NLPPipeline; NLPPipeline()"
```

### MongoDB connection issues
```python
# Test connection
from config.database import MongoDB
await MongoDB.connect_db()
```

### Out of memory
- Reduce batch size in pipeline
- Process users in smaller groups
- Use limit parameter: `limit_posts=50`

## 📚 References

**NLP Models:**
- [Cardiff NLP Sentiment](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest)
- [Emotion Detection](https://huggingface.co/j-hartmann/emotion-english-distilroberta-base)
- [Sentence Transformers](https://www.sbert.net/)

**Research:**
- [Social Media Mental Health Screening](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6111060/)
- [Cognitive Distortions in Text](https://arxiv.org/abs/2106.12853)

## 📝 License

This project is part of the SCS Youth Helper Dashboard for Dell Innovate 2026.

## 🤝 Contributing

For questions or contributions, please contact the development team.

---

**Built with ❤️ for youth mental health support**
