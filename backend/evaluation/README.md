# Evaluation Folder — Logic & How It Connects to the Pipeline

This folder contains scripts used to **validate**, **calibrate**, and **stress-test** the Stage2 risk scoring outputs.

The project goal is to prioritize social media cases for youth workers by ranking users with early signs of emotional distress.

---

## What the pipeline produces

### Stage1 (NLP Signals)
Produces comment-level signals such as:
- Emotion label + emotion score
- Sentiment label + sentiment score
- Distortion indicator (+ optional distortion score)
- Timestamped comment text (for evidence)

### Stage2 (Behavioral Aggregation)
Aggregates Stage1 signals into user-level features such as:
- Risk_Score (0–100)
- Distortion_Rate, Distortion_Count
- Volatility_Score, Rapid_Shifts
- Comment_Bursts, Long_Gaps
- Engagement_Pattern + Overall_Risk_Level
- Requires_Attention (boolean proxy label used for evaluation/calibration)

Stage2 output file: `backend/stage2_user_analysis.csv`

---

## Script Overview

### 1) `scorecard_eval.py`
Purpose: Evaluate the Stage2 outputs as a triage system.

Typical checks include:
- threshold-based metrics: precision/recall/F1 at a decision threshold
- ranking metrics: does the system put high-risk users near the top?

This helps answer: “If a youth worker only reviews top-K cases, how many true high-risk users are included?”

---

### 2) `calibration.py`
Purpose: Train a **logistic regression decision layer** that maps Stage2 features → probability of requiring attention.

Outputs:
- `backend/calibrated_user_probs.csv` (Stage2 rows + calibrated_prob_attention)
- `backend/evaluation/artifacts/calibration_lr.joblib` (saved LR pipeline)
- `backend/evaluation/artifacts/calibration_meta.json` (features used + recommended thresholds)

Why calibration is needed:
- Stage2 Risk_Score is often heuristic / rule-based.
- LR calibration learns weights from labeled cases, producing a consistent probability score for ranking/triage.

---

### 3) `ablation.py`
Purpose: Validate which features actually matter by removing one feature group at a time and measuring performance drop.

This helps ensure:
- the system isn’t relying on one brittle feature
- the risk score has consistent drivers

---

### 4) `simulate_regimes.py`
Purpose: Stress-test the scoring under synthetic patterns like:
- sudden crisis spike
- gradual withdrawal
- random noisy users

This helps separate:
- true regime changes vs. noise
- volatility-driven false alarms

---

## How Evaluation Connects to the Case Board

### Case board generation: `backend/build_case_board.py`
The case board merges:
- Stage2 user-level scores (ranking/priority)
- Stage1 comment evidence (excerpts + timestamps) to explain “why flagged”

**Decision layer behavior**
- If `calibrated_prob_attention` exists in Stage2 output, the board uses it as the main risk score.
- Otherwise it falls back to legacy `Risk_Score / 100`.
