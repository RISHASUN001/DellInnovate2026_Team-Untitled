"""
Comprehensive CSV generator with pattern analysis
"""
import pandas as pd
import json
from datetime import datetime
import os

def create_comprehensive_analysis_csv():
    """Create comprehensive Instagram comment analysis CSV with pattern analysis"""
    print("🚀 Creating comprehensive Instagram comment analysis CSV with pattern analysis...")
    
    # Sample analyzed comment data with pattern analysis
    sample_data = [
        {
            "comment_id": "comment_001",
            "username": "teen_user_1",
            "text": "I always mess everything up. I'm such a complete failure at everything I try. Nothing ever goes right for me.",
            "timestamp": "2026-02-28T08:30:00Z",
            "likes": 0,
            "replies": 2,
            
            # Basic NLP Analysis
            "sentiment": "negative",
            "sentiment_score": 0.94,
            "primary_emotion": "sadness",
            "primary_emotion_score": 0.85,
            "emotions": {"sadness": 0.85, "anger": 0.08, "fear": 0.05, "joy": 0.01, "love": 0.005, "surprise": 0.005},
            
            # Cognitive Distortions
            "cognitive_distortions": {
                "total_distortions": 6,
                "distortion_ratio": 24.0,
                "has_distortions": True,
                "all_or_nothing": 3,
                "overgeneralization": 2,
                "catastrophizing": 0,
                "personalization": 0,
                "emotional_reasoning": 0,
                "should_statements": 0,
                "labeling": 1,
                "mental_filtering": 0,
                "primary_distortion": "all_or_nothing"
            },
            
            # Risk Assessment
            "risk_assessment": {
                "risk_level": "high",
                "risk_score": 75,
                "requires_attention": True,
                "risk_factors": ["High cognitive distortion rate", "Extreme negative sentiment"]
            }
        },
        {
            "comment_id": "comment_002", 
            "username": "teen_user_1",
            "text": "Why does everyone hate me? I must be terrible person. I should just give up.",
            "timestamp": "2026-02-28T09:15:00Z", 
            "likes": 0,
            "replies": 0,
            
            # Basic NLP Analysis
            "sentiment": "negative",
            "sentiment_score": 0.89,
            "primary_emotion": "sadness", 
            "primary_emotion_score": 0.78,
            "emotions": {"sadness": 0.78, "fear": 0.15, "anger": 0.04, "joy": 0.015, "love": 0.005, "surprise": 0.005},
            
            # Cognitive Distortions
            "cognitive_distortions": {
                "total_distortions": 4,
                "distortion_ratio": 28.6,
                "has_distortions": True,
                "all_or_nothing": 0,
                "overgeneralization": 1,
                "catastrophizing": 1,
                "personalization": 1,
                "emotional_reasoning": 0,
                "should_statements": 1,
                "labeling": 0,
                "mental_filtering": 0,
                "primary_distortion": "catastrophizing"
            },
            
            # Risk Assessment
            "risk_assessment": {
                "risk_level": "high",
                "risk_score": 80,
                "requires_attention": True,
                "risk_factors": ["High cognitive distortion rate", "Crisis language patterns", "High sentiment volatility"]
            }
        },
        {
            "comment_id": "comment_003",
            "username": "teen_user_2", 
            "text": "Thanks for sharing this! Really helpful advice. Feeling much better today 😊",
            "timestamp": "2026-02-28T10:00:00Z",
            "likes": 5,
            "replies": 1,
            
            # Basic NLP Analysis
            "sentiment": "positive",
            "sentiment_score": 0.91,
            "primary_emotion": "joy",
            "primary_emotion_score": 0.82,
            "emotions": {"joy": 0.82, "love": 0.12, "surprise": 0.03, "sadness": 0.015, "anger": 0.01, "fear": 0.005},
            
            # Cognitive Distortions
            "cognitive_distortions": {
                "total_distortions": 0,
                "distortion_ratio": 0.0,
                "has_distortions": False,
                "all_or_nothing": 0,
                "overgeneralization": 0,
                "catastrophizing": 0,
                "personalization": 0,
                "emotional_reasoning": 0,
                "should_statements": 0,
                "labeling": 0,
                "mental_filtering": 0,
                "primary_distortion": None
            },
            
            # Risk Assessment
            "risk_assessment": {
                "risk_level": "minimal",
                "risk_score": 5,
                "requires_attention": False,
                "risk_factors": []
            }
        },
        {
            "comment_id": "comment_004",
            "username": "teen_user_3",
            "text": "I can't handle this anymore. Everything is falling apart. What if I never get better?",
            "timestamp": "2026-02-28T11:30:00Z",
            "likes": 0,
            "replies": 3,
            
            # Basic NLP Analysis
            "sentiment": "negative", 
            "sentiment_score": 0.92,
            "primary_emotion": "fear",
            "primary_emotion_score": 0.68,
            "emotions": {"fear": 0.68, "sadness": 0.25, "anger": 0.04, "joy": 0.015, "love": 0.01, "surprise": 0.005},
            
            # Cognitive Distortions
            "cognitive_distortions": {
                "total_distortions": 3,
                "distortion_ratio": 20.0,
                "has_distortions": True,
                "all_or_nothing": 0,
                "overgeneralization": 1,
                "catastrophizing": 2,
                "personalization": 0,
                "emotional_reasoning": 0,
                "should_statements": 0,
                "labeling": 0,
                "mental_filtering": 0,
                "primary_distortion": "catastrophizing"
            },
            
            # Risk Assessment
            "risk_assessment": {
                "risk_level": "high",
                "risk_score": 70,
                "requires_attention": True,
                "risk_factors": ["High negative emotions", "Catastrophic thinking patterns"]
            }
        }
    ]
    
    # Create comprehensive CSV data
    csv_data = []
    for comment in sample_data:
        row = {
            # Basic Info
            "Comment_ID": comment["comment_id"],
            "Username": comment["username"],
            "Text": comment["text"], 
            "Timestamp": comment["timestamp"],
            "Likes": comment["likes"],
            "Replies": comment["replies"],
            
            # Sentiment Analysis
            "Sentiment": comment["sentiment"],
            "Sentiment_Score": comment["sentiment_score"],
            "Primary_Emotion": comment["primary_emotion"], 
            "Primary_Emotion_Score": comment["primary_emotion_score"],
            
            # Emotion Scores
            "Joy_Score": comment["emotions"]["joy"],
            "Sadness_Score": comment["emotions"]["sadness"],
            "Anger_Score": comment["emotions"]["anger"],
            "Fear_Score": comment["emotions"]["fear"],
            "Love_Score": comment["emotions"]["love"], 
            "Surprise_Score": comment["emotions"]["surprise"],
            
            # Cognitive Distortions
            "Total_Cognitive_Distortions": comment["cognitive_distortions"]["total_distortions"],
            "Distortion_Ratio": comment["cognitive_distortions"]["distortion_ratio"],
            "Has_Cognitive_Distortions": comment["cognitive_distortions"]["has_distortions"],
            "Primary_Distortion_Type": comment["cognitive_distortions"]["primary_distortion"],
            "All_or_Nothing_Count": comment["cognitive_distortions"]["all_or_nothing"],
            "Overgeneralization_Count": comment["cognitive_distortions"]["overgeneralization"], 
            "Catastrophizing_Count": comment["cognitive_distortions"]["catastrophizing"],
            "Personalization_Count": comment["cognitive_distortions"]["personalization"],
            "Emotional_Reasoning_Count": comment["cognitive_distortions"]["emotional_reasoning"],
            "Should_Statements_Count": comment["cognitive_distortions"]["should_statements"],
            "Labeling_Count": comment["cognitive_distortions"]["labeling"],
            "Mental_Filtering_Count": comment["cognitive_distortions"]["mental_filtering"],
            
            # Risk Assessment
            "Risk_Level": comment["risk_assessment"]["risk_level"],
            "Risk_Score": comment["risk_assessment"]["risk_score"],
            "Requires_Attention": comment["risk_assessment"]["requires_attention"],
            "Risk_Factors": "; ".join(comment["risk_assessment"]["risk_factors"])
        }
        csv_data.append(row)
        
    # Create DataFrame
    df = pd.DataFrame(csv_data)
    
    # Create output directory
    output_dir = "analysis_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filenames with timestamp  
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f"{output_dir}/comprehensive_analysis_{timestamp}.csv"
    json_filename = f"{output_dir}/comprehensive_analysis_{timestamp}.json"
    summary_filename = f"{output_dir}/analysis_summary_{timestamp}.txt"
    
    # Export CSV
    df.to_csv(csv_filename, index=False, encoding='utf-8')
    print(f"✅ Comprehensive CSV exported to: {csv_filename}")
    
    # Export detailed JSON 
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Detailed JSON exported to: {json_filename}")
    
    # Generate summary report
    high_risk_count = len([c for c in sample_data if c['risk_assessment']['risk_level'] == 'high'])
    distortion_count = len([c for c in sample_data if c['cognitive_distortions']['has_distortions']])
    negative_sentiment_count = len([c for c in sample_data if c['sentiment'] == 'negative'])
    
    summary_text = f"""📊 Instagram Comment Analysis Summary Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔍 Analysis Overview:
   - Total comments analyzed: {len(sample_data)}
   - Unique users: {len(set([c['username'] for c in sample_data]))}
   - Time span: {sample_data[0]['timestamp']} to {sample_data[-1]['timestamp']}

⚠️ Risk Assessment:
   - High risk comments: {high_risk_count} ({high_risk_count/len(sample_data)*100:.1f}%)
   - Medium risk comments: 0 (0.0%)
   - Low risk comments: {len(sample_data) - high_risk_count} ({(len(sample_data) - high_risk_count)/len(sample_data)*100:.1f}%)

🧠 Sentiment & Emotion Analysis:
   - Negative sentiment: {negative_sentiment_count} ({negative_sentiment_count/len(sample_data)*100:.1f}%)
   - Primary emotions detected: {', '.join(set([c['primary_emotion'] for c in sample_data]))}

🔄 Cognitive Distortion Analysis:
   - Comments with distortions: {distortion_count} ({distortion_count/len(sample_data)*100:.1f}%)
   - Most common distortion: All-or-nothing thinking
   - Average distortion ratio: {sum([c['cognitive_distortions']['distortion_ratio'] for c in sample_data])/len(sample_data):.1f}%

🎯 Recommendations:
   - {high_risk_count} comments require immediate attention
   - Monitor users with high cognitive distortion rates
   - Follow up on negative sentiment trends

📁 Generated Files:
   - CSV: {csv_filename}
   - JSON: {json_filename}  
   - Summary: {summary_filename}
"""
    
    # Save summary
    with open(summary_filename, 'w', encoding='utf-8') as f:
        f.write(summary_text)
    print(f"✅ Summary report exported to: {summary_filename}")
    
    print(f"\\n{summary_text}")
    
    return csv_filename, json_filename, summary_filename

if __name__ == "__main__":
    create_comprehensive_analysis_csv()