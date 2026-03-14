import json
import hashlib
import pandas as pd


def make_case_id(username: str, platform: str = "instagram") -> str:
    raw = f"{platform}|{username}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


DISTRESS_EMOTIONS = {"sadness", "fear", "anger"}  # tweak if you want


def is_concerning(row: pd.Series) -> bool:
    """Heuristic to decide if a comment counts as a 'signal'."""
    emo = str(row.get("Emotion_Label", "")).lower()
    sent = str(row.get("Sentiment", "")).lower()
    dist = bool(row.get("Distortion_Indicator", False))

    # You can loosen/tighten this:
    return dist or (sent == "negative" and emo in DISTRESS_EMOTIONS)


def map_category(engagement_pattern: str, overall_risk: str) -> str:
    p = (engagement_pattern or "").lower()
    r = (overall_risk or "").lower()

    if "crisis_burst" in p:
        return "Acute Spike"
    if "declin" in p:
        return "Social Withdrawal"
    if "concerning" in p:
        return "Persistent Low Mood"
    if r == "high":
        return "Cognitive Distortions"
    return "Mixed/Other"


def build_case_board(stage2_path="stage2_user_analysis.csv",
                    stage1_path="stage1_signal_data.csv",
                    out_path="case_board.csv"):

    s2 = pd.read_csv(stage2_path)
    s1 = pd.read_csv(stage1_path)

    # Normalize names + timestamps
    s2["Username"] = s2["Username"].astype(str)
    s1["User"] = s1["User"].astype(str)

    s1["Comment_Created_At"] = pd.to_datetime(s1["Comment_Created_At"], utc=True, errors="coerce")
    s1 = s1.dropna(subset=["Comment_Created_At"])

    # Add "concerning" flag + a simple strength score for picking top evidence
    s1["is_concerning"] = s1.apply(is_concerning, axis=1).astype(bool)
    # evidence strength: emotion + sentiment + distortion score if present
    s1["evidence_strength"] = (
        s1.get("Emotion_Score", 0).fillna(0).astype(float)
        + s1.get("Sentiment_Score", 0).fillna(0).astype(float)
        + s1.get("Distortion_Score", 0).fillna(0).astype(float) / 3.0
    )

    rows = []

    for _, r in s2.iterrows():
        username = r["Username"]
        user_comments = s1[s1["User"] == username].copy()

        # fallback if stage1 doesn't have this user
        if user_comments.empty:
            created_at = pd.Timestamp.utcnow().tz_localize("UTC")
            last_signal_at = created_at
            latest_excerpt = ""
            evidence = []
        else:
            created_at = user_comments["Comment_Created_At"].min()

            concerning = user_comments[user_comments["is_concerning"]]
            if concerning.empty:
                concerning = user_comments  # fallback: use any activity as "last_signal"

            last_signal_at = concerning["Comment_Created_At"].max()

            # latest concerning excerpt
            latest_row = concerning.sort_values("Comment_Created_At", ascending=False).iloc[0]
            latest_excerpt = str(latest_row.get("Comment_Text", ""))[:220]

            # top evidence by strength
            top = concerning.sort_values("evidence_strength", ascending=False).head(3)
            evidence = []
            for _, er in top.iterrows():
                evidence.append({
                    "timestamp": pd.to_datetime(er["Comment_Created_At"]).isoformat(),
                    "emotion": er.get("Emotion_Label"),
                    "emotion_score": float(er.get("Emotion_Score", 0) or 0),
                    "sentiment": er.get("Sentiment"),
                    "sentiment_score": float(er.get("Sentiment_Score", 0) or 0),
                    "distortion": bool(er.get("Distortion_Indicator", False)),
                    "excerpt": str(er.get("Comment_Text", ""))[:220],
                })

        case_id = make_case_id(username)
        risk_score_0_1 = float(r.get("Risk_Score", 0)) / 100.0
        risk_score_0_1 = max(0.0, min(1.0, risk_score_0_1))
        category = map_category(r.get("Engagement_Pattern", ""), r.get("Overall_Risk_Level", ""))

        explanation_signals = {
            "summary": (
                f"Stage2 flags: {r.get('Overall_Risk_Level')} risk; "
                f"pattern={r.get('Engagement_Pattern')}, "
                f"distortion_rate={r.get('Distortion_Rate')}, "
                f"volatility={r.get('Volatility_Risk')}."
            ),
            "top_reasons": [
                {"signal": "distortion_rate", "value": round(float(r.get("Distortion_Rate", 0.0)), 3)},
                {"signal": "volatility_risk", "value": str(r.get("Volatility_Risk"))},
                {"signal": "engagement_pattern", "value": str(r.get("Engagement_Pattern"))},
                {"signal": "rapid_shifts", "value": int(r.get("Rapid_Shifts", 0))},
            ],
            "latest_event": {
                "timestamp": pd.to_datetime(last_signal_at).isoformat(),
                "excerpt": latest_excerpt,
            },
            "evidence": evidence,
            "feature_snapshot": {
                "total_comments": int(r.get("Total_Comments", 0)),
                "distortion_count": int(r.get("Distortion_Count", 0)),
                "distortion_ratio": float(r.get("Distortion_Ratio", 0.0)),
                "volatility_score": float(r.get("Volatility_Score", 0.0)),
                "risk_score_raw": int(r.get("Risk_Score", 0)),
                "requires_attention": bool(r.get("Requires_Attention", False)),
            },
            "model_version": "stage2_caseboard",
        }

        rows.append({
            "case_id": case_id,
            "assigned_to": "",
            "risk_score": round(risk_score_0_1, 4),
            "category": category,
            "explanation_signals": json.dumps(explanation_signals, ensure_ascii=False),
            "status": "open",
            "created_at": pd.to_datetime(created_at).isoformat(),
            "last_signal_at": pd.to_datetime(last_signal_at).isoformat(),
        })

    out = pd.DataFrame(rows).sort_values(["risk_score", "last_signal_at"], ascending=[False, False])
    out.to_csv(out_path, index=False)
    print(f"wrote {out_path} ({len(out)} cases)")


if __name__ == "__main__":
    build_case_board()