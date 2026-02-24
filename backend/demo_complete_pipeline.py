"""
Complete NLP Pipeline Demo - Stage 1 + Stage 2
Shows emotion analysis, cognitive distortions, sentiment volatility, and engagement patterns
"""
import json
import pandas as pd
from datetime import datetime, timedelta
from services.nlp_service import NLPService
from services.pattern_analysis_service import PatternAnalysisService
from loguru import logger


# Enhanced sample data with multiple comments per user over time
def generate_sample_data():
    """Generate sample comments with temporal patterns"""
    base_time = datetime(2024, 1, 15, 10, 0, 0)
    
    return [
        # User "alex_troubled" - Shows crisis burst pattern with distortions
        {
            "user": "alex_troubled",
            "comment_text": "I always mess everything up. Nothing ever goes right for me.",
            "post_shortcode": "ABC123",
            "created_at": (base_time + timedelta(hours=0)).isoformat() + "Z",
            "likes": 2
        },
        {
            "user": "alex_troubled",
            "comment_text": "Everyone thinks I'm a complete failure. They're probably right.",
            "post_shortcode": "ABC123",
            "created_at": (base_time + timedelta(hours=0.5)).isoformat() + "Z",
            "likes": 1
        },
        {
            "user": "alex_troubled",
            "comment_text": "This is a disaster. My whole life is falling apart and there's nothing I can do.",
            "post_shortcode": "DEF456",
            "created_at": (base_time + timedelta(hours=1)).isoformat() + "Z",
            "likes": 0
        },
        {
            "user": "alex_troubled",
            "comment_text": "I should have known better. It's all my fault everything is terrible.",
            "post_shortcode": "DEF456",
            "created_at": (base_time + timedelta(hours=1.2)).isoformat() + "Z",
            "likes": 3
        },
        
        # User "sarah_volatile" - Shows sentiment volatility
        {
            "user": "sarah_volatile",
            "comment_text": "This is the worst thing I've ever seen! Absolutely horrible!",
            "post_shortcode": "GHI789",
            "created_at": (base_time + timedelta(hours=2)).isoformat() + "Z",
            "likes": 5
        },
        {
            "user": "sarah_volatile",
            "comment_text": "Wait, actually this is amazing! I love it so much!",
            "post_shortcode": "GHI789",
            "created_at": (base_time + timedelta(hours=3)).isoformat() + "Z",
            "likes": 10
        },
        {
            "user": "sarah_volatile",
            "comment_text": "Never mind, I hate this. Everything about it is terrible.",
            "post_shortcode": "JKL012",
            "created_at": (base_time + timedelta(hours=4)).isoformat() + "Z",
            "likes": 2
        },
        {
            "user": "sarah_volatile",
            "comment_text": "Actually you know what, this is perfect! Best thing ever!",
            "post_shortcode": "JKL012",
            "created_at": (base_time + timedelta(hours=5)).isoformat() + "Z",
            "likes": 8
        },
        
        # User "mike_healthy" - Normal, healthy engagement
        {
            "user": "mike_healthy",
            "comment_text": "Nice work! I really appreciate the effort you put into this.",
            "post_shortcode": "MNO345",
            "created_at": (base_time + timedelta(hours=6)).isoformat() + "Z",
            "likes": 15
        },
        {
            "user": "mike_healthy",
            "comment_text": "Great point here. I'll have to think more about this.",
            "post_shortcode": "PQR678",
            "created_at": (base_time + timedelta(hours=12)).isoformat() + "Z",
            "likes": 12
        },
        {
            "user": "mike_healthy",
            "comment_text": "Thanks for sharing this perspective!",
            "post_shortcode": "STU901",
            "created_at": (base_time + timedelta(hours=18)).isoformat() + "Z",
            "likes": 18
        },
        
        # User "emma_catastrophizing" - High cognitive distortions
        {
            "user": "emma_catastrophizing",
            "comment_text": "This is going to be a complete catastrophe. Everything will be ruined forever.",
            "post_shortcode": "VWX234",
            "created_at": (base_time + timedelta(hours=8)).isoformat() + "Z",
            "likes": 1
        },
        {
            "user": "emma_catastrophizing",
            "comment_text": "I must be perfect or else everything will be a total disaster. No other option.",
            "post_shortcode": "VWX234",
            "created_at": (base_time + timedelta(hours=9)).isoformat() + "Z",
            "likes": 2
        },
        {
            "user": "emma_catastrophizing",
            "comment_text": "What if everything goes wrong? This will be the end of everything.",
            "post_shortcode": "YZA567",
            "created_at": (base_time + timedelta(hours=10)).isoformat() + "Z",
            "likes": 0
        },
        
        # User "jack_declining" - Declining engagement pattern
        {
            "user": "jack_declining",
            "comment_text": "Hey this is cool!",
            "post_shortcode": "BCD890",
            "created_at": (base_time + timedelta(hours=0)).isoformat() + "Z",
            "likes": 8
        },
        {
            "user": "jack_declining",
            "comment_text": "Not sure about this anymore...",
            "post_shortcode": "BCD890",
            "created_at": (base_time + timedelta(hours=48)).isoformat() + "Z",
            "likes": 3
        },
        {
            "user": "jack_declining",
            "comment_text": "I don't know. Nothing seems worth it.",
            "post_shortcode": "EFG123",
            "created_at": (base_time + timedelta(hours=96)).isoformat() + "Z",
            "likes": 1
        }
    ]


def run_complete_pipeline():
    """Run the complete Stage 1 + Stage 2 pipeline"""
    logger.info("=" * 70)
    logger.info("COMPLETE NLP PIPELINE - STAGE 1 + STAGE 2 DEMONSTRATION")
    logger.info("=" * 70)
    
    # Generate sample data
    logger.info("\n[Step 1] Generating sample comment data with temporal patterns...")
    sample_comments = generate_sample_data()
    
    # Save to JSON
    with open("demo_stage2_comments.json", 'w') as f:
        json.dump(sample_comments, f, indent=2)
    logger.success(f"Generated {len(sample_comments)} sample comments")
    
    # Initialize services
    logger.info("\n[Step 2] Initializing NLP Services...")
    nlp = NLPService()
    pattern_analyzer = PatternAnalysisService()
    logger.success("Services initialized!")
    
    # STAGE 1: Emotion & Sentiment Analysis
    logger.info("\n" + "=" * 70)
    logger.info("STAGE 1: EMOTION & SENTIMENT ANALYSIS")
    logger.info("=" * 70)
    
    analyzed_comments = []
    for comment in sample_comments:
        analysis = nlp.analyze_text(comment['comment_text'])
        analysis.update({
            'user': comment['user'],
            'post_shortcode': comment['post_shortcode'],
            'comment_created_at': comment['created_at'],
            'likes': comment['likes']
        })
        analyzed_comments.append(analysis)
    
    logger.info(f"\n✓ Analyzed {len(analyzed_comments)} comments for emotion & sentiment")
    
    # Create Signal DataFrame
    signal_df = nlp.create_signal_dataframe(analyzed_comments)
    signal_df.to_csv("stage1_signal_data.csv", index=False)
    logger.success("Stage 1 complete → stage1_signal_data.csv")
    
    # STAGE 2: Pattern Analysis
    logger.info("\n" + "=" * 70)
    logger.info("STAGE 2: PATTERN ANALYSIS")
    logger.info("=" * 70)
    
    # Group comments by user
    user_comments = {}
    for comment in analyzed_comments:
        username = comment['user']
        if username not in user_comments:
            user_comments[username] = []
        user_comments[username].append(comment)
    
    logger.info(f"\nAnalyzing {len(user_comments)} unique users...")
    
    # Analyze each user
    user_analyses = []
    for username, comments in user_comments.items():
        logger.info(f"\n{'─' * 70}")
        logger.info(f"Analyzing user: {username} ({len(comments)} comments)")
        logger.info(f"{'─' * 70}")
        
        analysis = pattern_analyzer.analyze_user_comprehensive(comments, username)
        user_analyses.append(analysis)
        
        # Display results
        logger.info(f"\n📊 COGNITIVE DISTORTIONS:")
        logger.info(f"  Total distortions detected: {analysis['cognitive_distortions']['total_distortions']}")
        logger.info(f"  Avg distortion ratio: {analysis['cognitive_distortions']['avg_distortion_ratio']:.2f} per 100 words")
        logger.info(f"  Comments with distortions: {analysis['cognitive_distortions']['comments_with_distortions']}/{len(comments)}")
        
        logger.info(f"\n📈 SENTIMENT VOLATILITY:")
        vol = analysis['sentiment_volatility']
        logger.info(f"  Volatility score: {vol['volatility_score']:.3f}")
        logger.info(f"  Mean sentiment: {vol['mean_sentiment']:.3f}")
        logger.info(f"  Rapid shifts: {vol['rapid_shifts']}")
        logger.info(f"  Risk level: {vol['risk_level']}")
        logger.info(f"  Trend: {vol['sentiment_trend']}")
        
        logger.info(f"\n👥 ENGAGEMENT PATTERNS:")
        eng = analysis['engagement_patterns']
        logger.info(f"  Pattern type: {eng['pattern']}")
        logger.info(f"  Time span: {eng['time_span_hours']:.1f} hours")
        logger.info(f"  Avg time between comments: {eng['avg_time_between_hours']:.1f} hours")
        logger.info(f"  Comment bursts: {eng['comment_bursts']}")
        logger.info(f"  Long gaps: {eng['long_gaps']}")
        logger.info(f"  Distortion rate: {eng['distortion_rate']:.1%}")
        logger.info(f"  Engagement score: {eng['engagement_score']:.1f}/100")
        
        # Risk assessment
        risk = analysis['risk_assessment']
        if risk['overall_risk_level'] == 'high':
            logger.warning(f"\n⚠️  RISK ASSESSMENT: {risk['overall_risk_level'].upper()}")
        elif risk['overall_risk_level'] == 'medium':
            logger.warning(f"\n⚡ RISK ASSESSMENT: {risk['overall_risk_level'].upper()}")
        else:
            logger.info(f"\n✓ RISK ASSESSMENT: {risk['overall_risk_level'].upper()}")
        
        logger.info(f"  Risk score: {risk['risk_score']}/100")
        if risk['risk_factors']:
            logger.info(f"  Risk factors:")
            for factor in risk['risk_factors']:
                logger.info(f"    • {factor}")
        
        logger.info(f"\n💡 RECOMMENDATIONS:")
        for rec in analysis['recommendations']:
            logger.info(f"  → {rec}")
    
    # Create comprehensive analysis DataFrame
    logger.info("\n" + "=" * 70)
    logger.info("CREATING COMPREHENSIVE ANALYSIS REPORT")
    logger.info("=" * 70)
    
    report_data = []
    for analysis in user_analyses:
        report_data.append({
            'Username': analysis['username'],
            'Total_Comments': analysis['total_comments_analyzed'],
            'Distortion_Count': analysis['cognitive_distortions']['total_distortions'],
            'Distortion_Ratio': analysis['cognitive_distortions']['avg_distortion_ratio'],
            'Volatility_Score': analysis['sentiment_volatility']['volatility_score'],
            'Rapid_Shifts': analysis['sentiment_volatility']['rapid_shifts'],
            'Volatility_Risk': analysis['sentiment_volatility']['risk_level'],
            'Engagement_Pattern': analysis['engagement_patterns']['pattern'],
            'Distortion_Rate': analysis['engagement_patterns']['distortion_rate'],
            'Comment_Bursts': analysis['engagement_patterns']['comment_bursts'],
            'Long_Gaps': analysis['engagement_patterns']['long_gaps'],
            'Overall_Risk_Level': analysis['risk_assessment']['overall_risk_level'],
            'Risk_Score': analysis['risk_assessment']['risk_score'],
            'Requires_Attention': analysis['risk_assessment']['requires_attention']
        })
    
    report_df = pd.DataFrame(report_data)
    report_df = report_df.sort_values('Risk_Score', ascending=False)
    report_df.to_csv("stage2_user_analysis.csv", index=False)
    
    logger.success("\nStage 2 complete → stage2_user_analysis.csv")
    
    # Summary statistics
    logger.info("\n" + "=" * 70)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 70)
    
    logger.info(f"\n📊 Overall Statistics:")
    logger.info(f"  Total comments analyzed: {len(analyzed_comments)}")
    logger.info(f"  Unique users: {len(user_analyses)}")
    logger.info(f"  High-risk users: {sum(1 for a in user_analyses if a['risk_assessment']['overall_risk_level'] == 'high')}")
    logger.info(f"  Medium-risk users: {sum(1 for a in user_analyses if a['risk_assessment']['overall_risk_level'] == 'medium')}")
    logger.info(f"  Users requiring attention: {sum(1 for a in user_analyses if a['risk_assessment']['requires_attention'])}")
    
    # Top concerns
    logger.info(f"\n⚠️  TOP PRIORITY USERS (Highest Risk):")
    logger.info("-" * 70)
    
    high_risk_users = sorted(user_analyses, key=lambda x: x['risk_assessment']['risk_score'], reverse=True)[:3]
    
    for i, user in enumerate(high_risk_users, 1):
        logger.warning(f"\n{i}. {user['username']} (Risk Score: {user['risk_assessment']['risk_score']})")
        logger.warning(f"   Risk Level: {user['risk_assessment']['overall_risk_level']}")
        logger.warning(f"   Pattern: {user['engagement_patterns']['pattern']}")
        logger.warning(f"   Volatility: {user['sentiment_volatility']['risk_level']}")
        if user['risk_assessment']['risk_factors']:
            logger.warning(f"   Factors: {', '.join(user['risk_assessment']['risk_factors'][:2])}")
    
    # Display sample results
    logger.info("\n" + "=" * 70)
    logger.info("SAMPLE: USER ANALYSIS REPORT (Top 3 Users by Risk)")
    logger.info("=" * 70)
    print("\n" + report_df.head(3).to_string(index=False))
    
    logger.info("\n" + "=" * 70)
    logger.success("✓ COMPLETE PIPELINE ANALYSIS FINISHED!")
    logger.info("=" * 70)
    
    logger.info(f"\n📁 Output Files:")
    logger.info(f"  1. Sample data: demo_stage2_comments.json")
    logger.info(f"  2. Stage 1 output: stage1_signal_data.csv")
    logger.info(f"  3. Stage 2 output: stage2_user_analysis.csv")
    
    logger.info(f"\n🎯 Key Insights:")
    logger.info(f"  • Cognitive distortions identify unhealthy thinking patterns")
    logger.info(f"  • Sentiment volatility detects emotional instability")
    logger.info(f"  • Engagement patterns reveal behavioral changes")
    logger.info(f"  • Combined risk scoring prioritizes users needing support")
    
    return user_analyses


if __name__ == "__main__":
    run_complete_pipeline()
