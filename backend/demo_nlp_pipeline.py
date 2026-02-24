"""
Demo NLP Pipeline - Standalone demonstration
Creates sample comment data and processes it through the NLP Signal Pipeline
"""
import json
import pandas as pd
from datetime import datetime
from services.nlp_service import NLPService
from loguru import logger

# Sample comment data simulating Instagram comments with various emotional tones
SAMPLE_COMMENTS = [
    {
        "user": "user123",
        "comment_text": "I'm feeling so hopeless and depressed lately. Nothing seems to matter anymore.",
        "post_shortcode": "ABC123",
        "post_owner": "influencer1",
        "created_at": "2024-01-15T10:30:00Z",
        "likes": 5
    },
    {
        "user": "user456",
        "comment_text": "This is absolutely disgusting! I can't believe you would post this. You're the worst!",
        "post_shortcode": "ABC123",
        "post_owner": "influencer1",
        "created_at": "2024-01-15T11:00:00Z",
        "likes": 2
    },
    {
        "user": "user789",
        "comment_text": "I'm so scared about the future. What if everything goes wrong?",
        "post_shortcode": "DEF456",
        "post_owner": "influencer1",
        "created_at": "2024-01-15T12:00:00Z",
        "likes": 8
    },
    {
        "user": "user101",
        "comment_text": "This makes me so happy! You're amazing and I love your content!",
        "post_shortcode": "DEF456",
        "post_owner": "influencer1",
        "created_at": "2024-01-15T13:00:00Z",
        "likes": 15
    },
    {
        "user": "user202",
        "comment_text": "Great post! Very informative and well done.",
        "post_shortcode": "GHI789",
        "post_owner": "influencer2",
        "created_at": "2024-01-15T14:00:00Z",
        "likes": 10
    },
    {
        "user": "user303",
        "comment_text": "I hate my life. Everything is falling apart and I don't know what to do.",
        "post_shortcode": "GHI789",
        "post_owner": "influencer2",
        "created_at": "2024-01-15T15:00:00Z",
        "likes": 3
    },
    {
        "user": "user404",
        "comment_text": "Wow! I'm so surprised by this news! Incredible!",
        "post_shortcode": "JKL012",
        "post_owner": "influencer2",
        "created_at": "2024-01-15T16:00:00Z",
        "likes": 12
    },
    {
        "user": "user505",
        "comment_text": "You make me so angry with your ignorance. This is unacceptable behavior.",
        "post_shortcode": "JKL012",
        "post_owner": "influencer2",
        "created_at": "2024-01-15T17:00:00Z",
        "likes": 1
    },
    {
        "user": "user606",
        "comment_text": "I'm terrified of what might happen. This is really scary stuff.",
        "post_shortcode": "MNO345",
        "post_owner": "influencer3",
        "created_at": "2024-01-15T18:00:00Z",
        "likes": 6
    },
    {
        "user": "user707",
        "comment_text": "You're the best! I absolutely love everything you do! So much joy!",
        "post_shortcode": "MNO345",
        "post_owner": "influencer3",
        "created_at": "2024-01-15T19:00:00Z",
        "likes": 20
    },
    {
        "user": "user808",
        "comment_text": "Nice picture. Looks good.",
        "post_shortcode": "PQR678",
        "post_owner": "influencer3",
        "created_at": "2024-01-15T20:00:00Z",
        "likes": 7
    },
    {
        "user": "user909",
        "comment_text": "I feel so worthless and alone. Nobody cares about me anymore.",
        "post_shortcode": "PQR678",
        "post_owner": "influencer3",
        "created_at": "2024-01-15T21:00:00Z",
        "likes": 4
    }
]

def save_sample_data():
    """Save sample data to JSON file"""
    output_file = "demo_sample_comments.json"
    with open(output_file, 'w') as f:
        json.dump(SAMPLE_COMMENTS, f, indent=2)
    logger.info(f"Saved {len(SAMPLE_COMMENTS)} sample comments to {output_file}")
    return output_file

def run_nlp_pipeline():
    """Run the complete NLP pipeline demonstration"""
    logger.info("=" * 60)
    logger.info("NLP SIGNAL PIPELINE DEMONSTRATION")
    logger.info("=" * 60)
    
    # Step 1: Save sample data
    logger.info("\n[Step 1] Creating sample comment data...")
    sample_file = save_sample_data()
    
    # Step 2: Initialize NLP service
    logger.info("\n[Step 2] Initializing NLP Service (loading models)...")
    nlp = NLPService()
    logger.success("NLP Service initialized successfully!")
    
    # Step 3: Analyze each comment
    logger.info("\n[Step 3] Analyzing comments with emotion & sentiment detection...")
    analyzed_comments = []
    
    for i, comment in enumerate(SAMPLE_COMMENTS, 1):
        logger.info(f"\nAnalyzing comment {i}/{len(SAMPLE_COMMENTS)}...")
        logger.info(f"Text: '{comment['comment_text'][:60]}...'")
        
        # Run NLP analysis
        analysis = nlp.analyze_text(comment['comment_text'])
        
        # Add metadata from original comment
        analysis.update({
            'user': comment['user'],
            'post_shortcode': comment['post_shortcode'],
            'post_owner': comment['post_owner'],
            'comment_created_at': comment['created_at'],
            'likes': comment['likes']
        })
        
        analyzed_comments.append(analysis)
        
        # Show results
        logger.info(f"  → Primary Emotion: {analysis['primary_emotion']} ({analysis['primary_emotion_score']:.3f})")
        logger.info(f"  → Sentiment: {analysis['sentiment']} ({analysis['sentiment_score']:.3f})")
        logger.info(f"  → Distortion: {'⚠️  YES' if analysis['distortion_indicator'] else '✓ NO'} (score: {analysis['distortion_score']:.3f})")
    
    # Step 4: Create Signal DataFrame
    logger.info("\n[Step 4] Creating Signal DataFrame...")
    df = nlp.create_signal_dataframe(analyzed_comments)
    
    logger.info(f"\nDataFrame created with {len(df)} rows and {len(df.columns)} columns")
    logger.info(f"Columns: {', '.join(df.columns[:8])}...")
    
    # Step 5: Export to CSV
    logger.info("\n[Step 5] Exporting Signal CSV...")
    output_csv = "signal_data_demo.csv"
    df.to_csv(output_csv, index=False)
    logger.success(f"Signal CSV exported to: {output_csv}")
    
    # Step 6: Show summary statistics
    logger.info("\n" + "=" * 60)
    logger.info("ANALYSIS SUMMARY")
    logger.info("=" * 60)
    
    logger.info(f"\nTotal Comments Analyzed: {len(df)}")
    
    logger.info("\n📊 Distortion Indicator Breakdown:")
    logger.info(f"  ⚠️  High Distortion (concerning): {len(df[df['Distortion_Indicator'] == True])}")
    logger.info(f"  ✓ Low Distortion (normal): {len(df[df['Distortion_Indicator'] == False])}")
    
    logger.info("\n😊 Emotion Label Distribution:")
    for emotion in ['sadness', 'anger', 'fear', 'joy', 'love', 'surprise']:
        count = len(df[df['Emotion_Label'] == emotion])
        if count > 0:
            logger.info(f"  {emotion.capitalize()}: {count}")
    
    logger.info("\n💭 Sentiment Distribution:")
    for sentiment in ['positive', 'neutral', 'negative']:
        count = len(df[df['Sentiment'] == sentiment])
        if count > 0:
            logger.info(f"  {sentiment.capitalize()}: {count}")
    
    # Step 7: Show top concerning comments
    logger.info("\n⚠️  TOP 5 MOST CONCERNING COMMENTS (Highest Distortion):")
    logger.info("-" * 60)
    top_concerning = df.nlargest(5, 'Distortion_Score')
    
    for idx, row in top_concerning.iterrows():
        logger.warning(f"\n{row['User']} (Distortion: {row['Distortion_Score']:.3f}):")
        logger.warning(f"  Text: {row['Comment_Text'][:80]}...")
        logger.warning(f"  Emotion: {row['Emotion_Label']} | Sentiment: {row['Sentiment']}")
        logger.warning(f"  Sadness: {row['Sadness_Score']:.2f} | Anger: {row['Anger_Score']:.2f} | Fear: {row['Fear_Score']:.2f}")
    
    # Step 8: Show sample rows from CSV
    logger.info("\n" + "=" * 60)
    logger.info("SAMPLE OUTPUT (First 3 rows from Signal CSV)")
    logger.info("=" * 60)
    print("\n" + df.head(3).to_string())
    
    logger.info("\n" + "=" * 60)
    logger.success("✓ NLP Pipeline Demo Complete!")
    logger.info("=" * 60)
    logger.info(f"\nOutput files created:")
    logger.info(f"  1. Sample data: {sample_file}")
    logger.info(f"  2. Signal CSV: {output_csv}")
    logger.info(f"\nYou can now:")
    logger.info(f"  - Open {output_csv} in Excel/Google Sheets")
    logger.info(f"  - Use it for further analysis")
    logger.info(f"  - Feed it into Stage 2 of your pipeline")

if __name__ == "__main__":
    run_nlp_pipeline()
