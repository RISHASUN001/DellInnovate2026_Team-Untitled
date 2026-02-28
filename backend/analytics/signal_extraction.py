"""
Stage 1: NLP Signal Extraction Pipeline

This module implements the first stage of the analytics pipeline:
1. Extract text units from MongoDB (posts/comments)
2. Preprocess text
3. Run NLP models (sentiment, emotion, distortion)
4. Store signals in text_units_signals collection
5. Generate CSV export
"""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import csv
import os
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

from analytics.nlp_models import NLPPipeline
from analytics.text_preprocessing import (
    TextPreprocessor,
    LanguageDetector,
    extract_text_units_from_post
)
from config.database import MongoDB
from models.instagram_models import TextUnitSignalModel


class NLPSignalExtractor:
    """
    Stage 1: NLP Signal Extraction Pipeline
    """
    
    def __init__(self, db_client: AsyncIOMotorClient = None):
        """
        Initialize NLP signal extractor
        
        Args:
            db_client: MongoDB client (uses default if None)
        """
        self.db = db_client or MongoDB.get_db()
        self.nlp_pipeline = None  # Lazy load to avoid loading models unnecessarily
        self.preprocessor = TextPreprocessor(
            remove_urls=True,
            remove_mentions=False,
            remove_hashtags=False,
            normalize_whitespace=True
        )
        self.language_detector = LanguageDetector()
        
        logger.info("NLP Signal Extractor initialized")
    
    def _load_nlp_pipeline(self):
        """Lazy load NLP models"""
        if self.nlp_pipeline is None:
            logger.info("Loading NLP models...")
            self.nlp_pipeline = NLPPipeline()
            logger.success("NLP models loaded")
    
    async def extract_text_units_from_db(self, 
                                         case_users: Optional[List[str]] = None,
                                         limit: Optional[int] = None) -> List[Dict]:
        """
        Extract text units from Instagram posts in database
        
        Args:
            case_users: List of specific usernames to process (None = all)
            limit: Maximum number of posts to process
            
        Returns:
            List of text unit dictionaries
        """
        posts_collection = self.db.instagram_posts
        
        # Build query
        query = {}
        if case_users:
            query['username'] = {'$in': case_users}
        
        # Fetch posts
        cursor = posts_collection.find(query)
        if limit:
            cursor = cursor.limit(limit)
        
        posts = await cursor.to_list(length=None)
        
        logger.info(f"Retrieved {len(posts)} posts from database")
        
        # Extract text units from all posts
        all_text_units = []
        for post in posts:
            text_units = extract_text_units_from_post(post)
            all_text_units.extend(text_units)
        
        logger.info(f"Extracted {len(all_text_units)} text units")
        
        return all_text_units
    
    def preprocess_text_unit(self, text_unit: Dict) -> Dict:
        """
        Preprocess a single text unit
        
        Args:
            text_unit: Text unit dictionary
            
        Returns:
            Text unit with preprocessed_text and language fields
        """
        original_text = text_unit['text']
        preprocessed = self.preprocessor.preprocess(original_text)
        
        # Check if valid
        is_valid = self.preprocessor.is_valid_text(preprocessed)
        
        # Detect language
        language = self.language_detector.detect_language(preprocessed) if is_valid else 'unknown'
        
        text_unit['preprocessed_text'] = preprocessed if is_valid else ""
        text_unit['language'] = language
        text_unit['is_valid'] = is_valid
        
        return text_unit
    
    def analyze_text_unit(self, text_unit: Dict) -> Dict:
        """
        Run NLP analysis on a text unit
        
        Args:
            text_unit: Preprocessed text unit
            
        Returns:
            Text unit with NLP analysis results
        """
        self._load_nlp_pipeline()
        
        text = text_unit.get('preprocessed_text', '')
        
        if not text or not text_unit.get('is_valid', False):
            # Return default empty results
            text_unit['nlp_results'] = {
                'sentiment': {'label': 'neutral', 'score': 0.0, 'probabilities': {}, 'sentiment_score': 0.0},
                'emotion': {'label': 'neutral', 'score': 0.0, 'probabilities': {}, 'is_distress': False, 'distress_score': 0.0},
                'distortion': {'distortion_indicator': 0, 'distortion_score': 0.0, 'distortion_category': None, 'all_scores': {}}
            }
            return text_unit
        
        # Run NLP analysis
        results = self.nlp_pipeline.analyze(text)
        text_unit['nlp_results'] = results
        
        return text_unit
    
    def create_signal_document(self, text_unit: Dict) -> Dict:
        """
        Create MongoDB document for text_units_signals collection
        
        Args:
            text_unit: Analyzed text unit
            
        Returns:
            Document dictionary ready for MongoDB insertion
        """
        nlp = text_unit.get('nlp_results', {})
        sentiment = nlp.get('sentiment', {})
        emotion = nlp.get('emotion', {})
        distortion = nlp.get('distortion', {})
        
        # Extract emotion probabilities for distress_emotion calculation
        emotion_probs = emotion.get('probabilities', {})
        p_anger = emotion_probs.get('anger', 0.0)
        p_sadness = emotion_probs.get('sadness', 0.0)
        p_fear = emotion_probs.get('fear', 0.0)
        
        # Calculate distress_emotion as max of distress emotion probabilities
        distress_emotion = max(p_anger, p_sadness, p_fear)
        
        # Calculate is_negative flag
        is_negative = 1 if sentiment.get('label', 'neutral') == 'negative' else 0
        
        # Calculate distortion_flag
        distortion_flag = distortion.get('distortion_indicator', 0)
        
        document = {
            'case_user': text_unit['case_user'],
            'text_type': text_unit['text_type'],
            'text': text_unit['text'],
            'post_id': text_unit['post_id'],
            'comment_id': text_unit.get('comment_id'),
            'author': text_unit.get('author'),
            'timestamp': text_unit.get('timestamp'),
            'created_at': text_unit.get('timestamp'),  # Alias for windowing
            
            'sentiment_label': sentiment.get('label', 'neutral'),
            'sentiment_score': sentiment.get('sentiment_score', 0.0),
            'sentiment_probabilities': sentiment.get('probabilities', {}),
            'is_negative': is_negative,  # NEW: binary flag
            
            'emotion_label': emotion.get('label', 'neutral'),
            'emotion_score': emotion.get('score', 0.0),
            'emotion_probabilities': emotion_probs,
            'is_distress': emotion.get('is_distress', False),
            'distress_score': emotion.get('distress_score', 0.0),
            'distress_emotion': distress_emotion,  # NEW: numeric 0-1
            
            'distortion_indicator': distortion.get('distortion_indicator', 0),
            'distortion_flag': distortion_flag,  # NEW: alias for indicator
            'distortion_score': distortion.get('distortion_score', 0.0),
            'distortion_category': distortion.get('distortion_category'),
            'distortion_all_scores': distortion.get('all_scores'),
            
            'processed_at': datetime.utcnow(),
            'preprocessed_text': text_unit.get('preprocessed_text'),
            'language': text_unit.get('language')
        }
        
        return document
    
    async def store_signals(self, signal_documents: List[Dict]) -> int:
        """
        Store signal documents in MongoDB
        
        Args:
            signal_documents: List of signal documents
            
        Returns:
            Number of documents inserted
        """
        if not signal_documents:
            return 0
        
        signals_collection = self.db.text_units_signals
        
        try:
            result = await signals_collection.insert_many(signal_documents)
            count = len(result.inserted_ids)
            logger.success(f"Inserted {count} signal documents")
            return count
        except Exception as e:
            logger.error(f"Error storing signals: {e}")
            raise
    
    async def export_signals_to_csv(self, 
                                    output_path: str = "nlp_signals.csv",
                                    case_users: Optional[List[str]] = None) -> str:
        """
        Export signals to CSV format
        
        Args:
            output_path: Path to output CSV file
            case_users: Filter by specific case users
            
        Returns:
            Path to created CSV file
        """
        signals_collection = self.db.text_units_signals
        
        # Build query
        query = {}
        if case_users:
            query['case_user'] = {'$in': case_users}
        
        # Fetch signals
        signals = await signals_collection.find(query).to_list(length=None)
        
        logger.info(f"Exporting {len(signals)} signals to CSV")
        
        # Write CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Case_User',
                'Comment_Text',
                'Emotion_Label',
                'Sentiment_Score',
                'Distortion_Indicator'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for signal in signals:
                writer.writerow({
                    'Case_User': signal['case_user'],
                    'Comment_Text': signal['text'],
                    'Emotion_Label': signal['emotion_label'],
                    'Sentiment_Score': signal['sentiment_score'],
                    'Distortion_Indicator': signal['distortion_indicator']
                })
        
        logger.success(f"CSV exported to {output_path}")
        return output_path
    
    async def run_pipeline(self,
                          case_users: Optional[List[str]] = None,
                          limit: Optional[int] = None,
                          export_csv: bool = True,
                          csv_path: str = "nlp_signals.csv") -> Dict:
        """
        Run complete Stage 1 NLP Signal Extraction Pipeline
        
        Args:
            case_users: Specific users to process (None = all)
            limit: Maximum posts to process
            export_csv: Whether to export results to CSV
            csv_path: Path for CSV export
            
        Returns:
            Pipeline execution results
        """
        start_time = datetime.utcnow()
        logger.info("=" * 70)
        logger.info("Starting NLP Signal Extraction Pipeline (Stage 1)")
        logger.info("=" * 70)
        
        # Step 1: Extract text units from database
        logger.info("[1/5] Extracting text units from database...")
        text_units = await self.extract_text_units_from_db(case_users, limit)
        
        if not text_units:
            logger.warning("No text units found")
            return {
                'status': 'completed',
                'text_units_found': 0,
                'signals_created': 0,
                'duration_seconds': 0
            }
        
        # Step 2: Preprocess text units
        logger.info("[2/5] Preprocessing text units...")
        for i, text_unit in enumerate(text_units):
            text_units[i] = self.preprocess_text_unit(text_unit)
        
        valid_units = [tu for tu in text_units if tu.get('is_valid', False)]
        logger.info(f"Valid text units: {len(valid_units)}/{len(text_units)}")
        
        # Step 3: Run NLP analysis
        logger.info("[3/5] Running NLP analysis (sentiment, emotion, distortion)...")
        for i, text_unit in enumerate(valid_units):
            if (i + 1) % 50 == 0:
                logger.info(f"Processed {i + 1}/{len(valid_units)} text units...")
            valid_units[i] = self.analyze_text_unit(text_unit)
        
        # Step 4: Create signal documents
        logger.info("[4/5] Creating signal documents...")
        signal_documents = [self.create_signal_document(tu) for tu in valid_units]
        
        # Step 5: Store in database
        logger.info("[5/5] Storing signals in database...")
        stored_count = await self.store_signals(signal_documents)
        
        # Export to CSV if requested
        csv_file = None
        if export_csv:
            logger.info("Exporting signals to CSV...")
            csv_file = await self.export_signals_to_csv(csv_path, case_users)
        
        # Calculate duration
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("=" * 70)
        logger.success(f"Pipeline completed in {duration:.2f} seconds")
        logger.info(f"Text units processed: {len(text_units)}")
        logger.info(f"Valid units analyzed: {len(valid_units)}")
        logger.info(f"Signals stored: {stored_count}")
        if csv_file:
            logger.info(f"CSV exported: {csv_file}")
        logger.info("=" * 70)
        
        return {
            'status': 'completed',
            'text_units_found': len(text_units),
            'valid_units': len(valid_units),
            'signals_created': stored_count,
            'csv_file': csv_file,
            'duration_seconds': duration
        }


async def run_nlp_extraction(case_users: Optional[List[str]] = None,
                            limit: Optional[int] = None) -> Dict:
    """
    Convenience function to run NLP extraction pipeline
    
    Args:
        case_users: Specific users to process
        limit: Maximum posts to process
        
    Returns:
        Pipeline results
    """
    extractor = NLPSignalExtractor()
    return await extractor.run_pipeline(case_users=case_users, limit=limit)
