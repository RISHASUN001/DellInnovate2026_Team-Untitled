"""
Simple CSV generation script for Instagram comment analysis
"""
import asyncio
import os
import json
from datetime import datetime
from config.database import MongoDB
from services.nlp_service import NLPService
from loguru import logger

async def generate_csv_output():
    """Generate CSV output from analysis"""
    logger.info("🚀 Starting Instagram Comment Analysis CSV Generator")
    
    try:
        # Connect to database
        await MongoDB.connect_db()
        logger.info("✅ Connected to MongoDB")
        
        # Initialize NLP service
        nlp = NLPService()
        logger.info("✅ NLP service initialized")
        
        # Create output directory
        output_dir = "analysis_output"
        os.makedirs(output_dir, exist_ok=True)
        
        # Test with sample data first
        logger.info("📝 Testing with sample comments...")
        sample_comments = [
            "I love this post! So inspiring! 😍",
            "I'm feeling really sad and hopeless today 😢",
            "Everything always goes wrong for me, I'm such a failure",
            "This is amazing! Best day ever!",
            "I can't do anything right, I'm worthless",
            "Great content, thanks for sharing!",
        ]
        
        # Analyze sample comments
        analyzed_samples = []
        for i, text in enumerate(sample_comments):
            result = nlp.analyze_text(text)
            result['comment_id'] = f"sample_{i+1}"
            result['username'] = "sample_user"
            analyzed_samples.append(result)
            logger.info(f"Analyzed sample {i+1}: {result['sentiment']} - {result['primary_emotion']}")
        
        # Create signal dataframe and export
        logger.info("📊 Creating signal dataframe...")
        signal_df = nlp.create_signal_dataframe({'analyzed_comments': analyzed_samples})
        
        if not signal_df.empty:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_file = f"{output_dir}/instagram_analysis_{timestamp}.csv"
            signal_df.to_csv(csv_file, index=False, encoding='utf-8')
            logger.success(f"✅ CSV exported to: {csv_file}")
            
            # Also save detailed JSON
            json_file = f"{output_dir}/instagram_analysis_{timestamp}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(analyzed_samples, f, indent=2, ensure_ascii=False)
            logger.success(f"✅ JSON exported to: {json_file}")
            
            # Show summary
            logger.info(f"📈 Analysis Summary:")
            logger.info(f"   - Total comments analyzed: {len(analyzed_samples)}")
            logger.info(f"   - CSV columns: {list(signal_df.columns)}")
            logger.info(f"   - Output files: {csv_file}, {json_file}")
            
        else:
            logger.warning("⚠️ No data to export")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        
    finally:
        try:
            await MongoDB.close_db()
            logger.info("🔐 Database connection closed")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(generate_csv_output())