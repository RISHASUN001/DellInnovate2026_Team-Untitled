# Instagram Comment Analysis Pipeline - NLP System

## 🧠 **Core NLP Capabilities**

### **Multilingual Sentiment Analysis**
- **Model**: `cardiffnlp/twitter-xlm-roberta-base-sentiment`
- **Languages**: Supports multiple languages (English, Spanish, French, German, Italian, Portuguese, etc.)
- **Output**: Positive/Negative/Neutral classification with confidence scores
- **Scale**: Converts to -1 to +1 sentiment scale for volatility analysis

### **Emotion Detection**
- **Model**: `cardiffnlp/twitter-roberta-base-emotion-multilabel-latest`
- **Languages**: English-only
- **Emotions Detected**: 6 core emotions
  - Sadness
  - Anger  
  - Fear
  - Joy
  - Love
  - Surprise
- **Output**: Confidence scores for each emotion + primary emotion identification

### **Advanced Pattern Analysis**

#### **Cognitive Distortion Detection**
Identifies 8 types of distorted thinking patterns using regex-based keyword detection:

1. **All-or-Nothing Thinking** - "always", "never", "everyone", "perfect", "terrible"
2. **Overgeneralization** - "everything", "constantly", "typical", "every time"
3. **Catastrophizing** - "disaster", "nightmare", "worst", "impossible", "doomed"
4. **Personalization** - "my fault", "because of me", "I caused", "I ruined"
5. **Emotional Reasoning** - "I feel... so it must be", "feels like... is"
6. **Should Statements** - "should", "must", "have to", "supposed to"
7. **Labeling** - "I'm a failure", "I'm worthless", "everyone is terrible"
8. **Mental Filtering** - "only bad", "nothing good", "all I see is problems"

#### **Sentiment Volatility Analysis**
- **Temporal Tracking**: Analyzes emotional shifts between consecutive comments
- **Volatility Scoring**: Calculates average absolute change in sentiment
- **Rapid Shift Detection**: Identifies concerning jumps (>1.0 on -1 to +1 scale)
- **Risk Levels**: High/Medium/Low/Stable based on volatility patterns
- **Window Analysis**: Uses sliding windows to detect periods of instability

#### **Engagement Pattern Analysis**
- **Crisis Burst Detection**: Multiple negative comments in short timeframes
- **Withdrawal Patterns**: Declining engagement with increased negativity
- **Behavioral Metrics**:
  - Comment frequency and timing
  - Burst activity (comments within 1 hour)
  - Long gaps in engagement
  - Word count patterns
  - Community interaction (likes)

## 🔧 **Technical Architecture**

### **NLP Service (`services/nlp_service.py`)**
- **Initialization**: Loads Hugging Face transformer models
- **Text Analysis**: Single comment processing with all metrics
- **User Analysis**: Comprehensive analysis of all user comments
- **Pattern Integration**: Combines basic NLP with advanced pattern detection
- **Database Integration**: Queries MongoDB for user comment history

### **Pattern Analysis Service (`services/pattern_analysis_service.py`)**
- **Cognitive Analysis**: Regex-based distortion pattern matching
- **Temporal Analysis**: Time-series sentiment volatility calculation
- **Behavioral Analysis**: Engagement pattern classification
- **Risk Assessment**: Multi-factor scoring and recommendation generation

## 📊 **Analysis Output Structure**

### **Single Comment Analysis**
```json
{
  "text": "I always mess everything up...",
  "sentiment": "negative",
  "sentiment_score": 0.89,
  "emotions": {"sadness": 0.7, "anger": 0.2, "fear": 0.1},
  "primary_emotion": "sadness",
  "distortion_indicator": true,
  "cognitive_distortions": {
    "total_distortions": 3,
    "has_distortions": true,
    "primary_distortion": "all_or_nothing"
  },
  "risk_indicators": {
    "high_negative_emotions": true,
    "cognitive_distortions_present": true
  }
}
```

### **Comprehensive User Analysis**
```json
{
  "username": "user123",
  "pattern_analysis": {
    "cognitive_distortions": {
      "total_distortions": 15,
      "avg_distortion_ratio": 12.5,
      "comments_with_distortions": 8
    },
    "sentiment_volatility": {
      "volatility_score": 1.4,
      "risk_level": "high",
      "rapid_shifts": 3,
      "sentiment_trend": "declining"
    },
    "engagement_patterns": {
      "pattern": "crisis_burst",
      "comment_bursts": 2,
      "long_gaps": 1,
      "distortion_rate": 0.6
    },
    "risk_assessment": {
      "overall_risk_level": "high",
      "risk_score": 65,
      "risk_factors": ["High sentiment volatility", "Crisis burst pattern"],
      "recommendations": ["⚠️ IMMEDIATE ATTENTION: Multiple high-risk indicators"]
    }
  }
}
```

## 🎯 **Clinical Application**

### **Risk Scoring Algorithm**
- **Base Emotion Score**: High negative emotions (sadness, anger, fear) = +15-30 points
- **Cognitive Distortions**: High distortion rate (>50%) = +25 points
- **Volatility Patterns**: Rapid emotional shifts = +15-30 points  
- **Behavioral Patterns**: Crisis bursts = +30 points, withdrawal = +20 points

### **Risk Classification**
- **High Risk (50+ points)**: Immediate attention recommended
- **Medium Risk (30-49 points)**: Enhanced monitoring
- **Low Risk (15-29 points)**: Routine monitoring
- **Minimal Risk (<15 points)**: Standard protocols

### **Recommendation Engine**
Generates specific actionable guidance based on pattern combinations:
- Crisis intervention for burst patterns + high volatility
- Support resources for high distortion rates
- Timeline monitoring for withdrawal patterns
- Community engagement for isolation indicators

## 🚀 **Getting Started**

### **Prerequisites**
- Python 3.10+
- MongoDB Atlas account
- Scrapfly API key for Instagram scraping

### **Installation**
```bash
# Clone repository
git clone https://github.com/RISHASUN001/DellInnovate2026_Team-Untitled.git
cd DellInnovate2026_Team-Untitled

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your MongoDB URI and Scrapfly API key
```

### **Configuration**
Update your `.env` file:
```bash
MONGODB_URI=mongodb+srv://your_connection_string
MONGODB_DB_NAME=instagram_scraper
SCRAPFLY_KEY=your_scrapfly_key
```

### **Usage**

#### **1. Start the API Server**
```bash
cd backend
python app.py
```
Server runs on `http://localhost:8000`

#### **2. Unified Pipeline Analysis**
```bash
# Interactive mode
python instagram_analysis_pipeline.py

# API endpoint
curl -X POST "http://localhost:8000/api/unified-pipeline/analyze-user" \
  -H "Content-Type: application/json" \
  -d '{"username": "instagram_username", "scrape_comments": true}'
```

#### **3. NLP Analysis Only**
```bash
# Analyze existing data
curl -X POST "http://localhost:8000/api/nlp/analyze/user" \
  -H "Content-Type: application/json" \
  -d '{"username": "username", "include_pattern_analysis": true}'
```

## 📋 **API Endpoints**

### **Core Analysis**
- `POST /api/nlp/analyze/text` - Single text analysis
- `POST /api/nlp/analyze/user` - Comprehensive user analysis
- `POST /api/nlp/analyze/comments` - Batch comment analysis

### **Pattern Analysis**
- `POST /api/nlp/pattern-analysis/cognitive-distortions` - Cognitive distortion detection
- `POST /api/nlp/pattern-analysis/sentiment-volatility` - Emotional volatility analysis
- `POST /api/nlp/pattern-analysis/engagement-patterns` - Behavioral pattern analysis
- `POST /api/nlp/pattern-analysis/comprehensive` - Complete pattern analysis

### **Unified Pipeline**
- `POST /api/unified-pipeline/analyze-user` - End-to-end analysis (scrape + analyze)
- `POST /api/unified-pipeline/analyze-existing` - Analyze existing MongoDB data

### **Utilities**
- `GET /api/nlp/health` - Service health check
- `POST /api/nlp/export/signal-csv` - Export analysis results

## 🏗️ **Project Structure**
```
├── backend/
│   ├── services/
│   │   ├── nlp_service.py              # Core NLP analysis
│   │   ├── pattern_analysis_service.py # Advanced pattern detection
│   │   ├── scraper_service.py          # Instagram scraping
│   │   └── comment_service.py          # Comment processing
│   ├── routes/
│   │   ├── nlp_routes.py               # NLP API endpoints
│   │   └── scraper_routes.py           # Scraping endpoints
│   ├── config/
│   │   └── database.py                 # MongoDB configuration
│   ├── app.py                          # FastAPI main application
│   └── instagram_analysis_pipeline.py  # Unified pipeline
├── src/
│   └── scs_dashboard.jsx               # React dashboard
└── README.md
```

## 📚 **Documentation**
- [Pattern Analysis Guide](backend/README_PATTERN_ANALYSIS.md) - Detailed pattern analysis documentation
- [API Documentation](http://localhost:8000/docs) - Interactive API docs (when server running)

## 🤝 **Contributing**
This project was developed for Dell Innovate 2026 as a youth mental health monitoring solution. The NLP system provides clinically-informed analysis suitable for early intervention protocols.

## ⚠️ **Important Notes**
- **Privacy Compliance**: Original social media content is analyzed but not permanently stored
- **Model Languages**: Sentiment analysis is multilingual; emotion analysis is English-only  
- **Clinical Use**: Pattern analysis uses research-informed thresholds for mental health applications
- **Performance**: Large datasets may require processing time; consider pagination for production use

The NLP system provides a comprehensive, clinically-informed analysis framework suitable for youth mental health monitoring and early intervention protocols.