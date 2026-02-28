"""
Simple CSV output generator - standalone version
"""
import pandas as pd
import json
from datetime import datetime
import os

def create_sample_analysis_csv():
    """Create sample Instagram comment analysis CSV"""
    print("🚀 Creating sample Instagram comment analysis CSV...")
    
    # Sample analyzed comment data
    sample_data = [
        {
            "comment_id": "sample_1",
            "username": "user_123",
            "text": "I love this post! So inspiring! 😍",
            "sentiment": "positive",
            "sentiment_score": 0.92,
            "primary_emotion": "joy",
            "primary_emotion_score": 0.85,
            "emotions": {
                "joy": 0.85,
                "love": 0.12,
                "surprise": 0.02,
                "sadness": 0.01,
                "anger": 0.0,
                "fear": 0.0
            },
            "distortion_indicator": False,
            "distortion_score": 0.1,
            "cognitive_distortions": {
                "total_distortions": 0,
                "has_distortions": False,
                "all_or_nothing": 0,
                "overgeneralization": 0,
                "catastrophizing": 0
            },
            "risk_level": "low",
            "timestamp": "2026-02-28T10:30:00Z"
        },
        {
            "comment_id": "sample_2", 
            "username": "user_456",
            "text": "I'm feeling really sad and hopeless today 😢",
            "sentiment": "negative",
            "sentiment_score": 0.88,
            "primary_emotion": "sadness",
            "primary_emotion_score": 0.79,
            "emotions": {
                "sadness": 0.79,
                "fear": 0.15,
                "anger": 0.04,
                "joy": 0.01,
                "love": 0.005,
                "surprise": 0.005
            },
            "distortion_indicator": True,
            "distortion_score": 0.7,
            "cognitive_distortions": {
                "total_distortions": 2,
                "has_distortions": True,
                "all_or_nothing": 1,
                "overgeneralization": 1,
                "catastrophizing": 0
            },
            "risk_level": "high",
            "timestamp": "2026-02-28T10:35:00Z"
        },
        {
            "comment_id": "sample_3",
            "username": "user_456", 
            "text": "Everything always goes wrong for me, I'm such a failure",
            "sentiment": "negative",
            "sentiment_score": 0.95,
            "primary_emotion": "sadness",
            "primary_emotion_score": 0.82,
            "emotions": {
                "sadness": 0.82,
                "anger": 0.12,
                "fear": 0.05,
                "joy": 0.005,
                "love": 0.0,
                "surprise": 0.005
            },
            "distortion_indicator": True,
            "distortion_score": 0.9,
            "cognitive_distortions": {
                "total_distortions": 4,
                "has_distortions": True,
                "all_or_nothing": 2,
                "overgeneralization": 2,
                "catastrophizing": 0
            },
            "risk_level": "high",
            "timestamp": "2026-02-28T10:40:00Z"
        },
        {
            "comment_id": "sample_4",
            "username": "user_789",
            "text": "This is amazing! Best day ever!",
            "sentiment": "positive",
            "sentiment_score": 0.94,
            "primary_emotion": "joy",
            "primary_emotion_score": 0.91,
            "emotions": {
                "joy": 0.91,
                "surprise": 0.06,
                "love": 0.02,
                "sadness": 0.005,
                "anger": 0.0,
                "fear": 0.005
            },
            "distortion_indicator": False,
            "distortion_score": 0.1,
            "cognitive_distortions": {
                "total_distortions": 1,
                "has_distortions": True,
                "all_or_nothing": 1,
                "overgeneralization": 0,
                "catastrophizing": 0
            },
            "risk_level": "low",
            "timestamp": "2026-02-28T10:45:00Z"
        }
    ]
    
    # Create DataFrame for CSV export
    csv_data = []
    for comment in sample_data:
        row = {
            "Comment_ID": comment["comment_id"],
            "Username": comment["username"],
            "Text": comment["text"],
            "Sentiment": comment["sentiment"],
            "Sentiment_Score": comment["sentiment_score"],
            "Primary_Emotion": comment["primary_emotion"],
            "Primary_Emotion_Score": comment["primary_emotion_score"],
            "Joy_Score": comment["emotions"]["joy"],
            "Sadness_Score": comment["emotions"]["sadness"], 
            "Anger_Score": comment["emotions"]["anger"],
            "Fear_Score": comment["emotions"]["fear"],
            "Love_Score": comment["emotions"]["love"],
            "Surprise_Score": comment["emotions"]["surprise"],
            "Distortion_Indicator": comment["distortion_indicator"],
            "Distortion_Score": comment["distortion_score"],
            "Total_Cognitive_Distortions": comment["cognitive_distortions"]["total_distortions"],
            "Has_Cognitive_Distortions": comment["cognitive_distortions"]["has_distortions"],
            "All_or_Nothing_Count": comment["cognitive_distortions"]["all_or_nothing"],
            "Overgeneralization_Count": comment["cognitive_distortions"]["overgeneralization"], 
            "Catastrophizing_Count": comment["cognitive_distortions"]["catastrophizing"],
            "Risk_Level": comment["risk_level"],
            "Timestamp": comment["timestamp"]
        }
        csv_data.append(row)
    
    # Create DataFrame
    df = pd.DataFrame(csv_data)
    
    # Create output directory
    output_dir = "analysis_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filenames with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f"{output_dir}/instagram_analysis_{timestamp}.csv"
    json_filename = f"{output_dir}/instagram_analysis_{timestamp}.json"
    
    # Export CSV
    df.to_csv(csv_filename, index=False, encoding='utf-8')
    print(f"✅ CSV exported to: {csv_filename}")
    
    # Export detailed JSON
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON exported to: {json_filename}")
    
    # Show summary
    print(f"\\n📊 Analysis Summary:")
    print(f"   - Total comments: {len(sample_data)}")
    print(f"   - High risk comments: {len([c for c in sample_data if c['risk_level'] == 'high'])}")
    print(f"   - Negative sentiment: {len([c for c in sample_data if c['sentiment'] == 'negative'])}")
    print(f"   - Comments with distortions: {len([c for c in sample_data if c['distortion_indicator']])}")
    print(f"   - CSV columns: {len(df.columns)}")
    print(f"\\n📁 Output files created:")
    print(f"   - {csv_filename}")
    print(f"   - {json_filename}")
    
    return csv_filename, json_filename

if __name__ == "__main__":
    create_sample_analysis_csv()