"""
NLP Models for emotional distress detection

This module implements:
1. Sentiment Analysis using cardiffnlp/twitter-roberta-base-sentiment
2. Emotion Detection using j-hartmann/emotion-english-distilroberta-base
3. Cognitive Distortion Detection using sentence-transformers/all-MiniLM-L6-v2
"""

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer, AutoConfig
from sentence_transformers import SentenceTransformer, util
import numpy as np
from typing import Dict, List, Tuple, Optional
from loguru import logger
import warnings

warnings.filterwarnings('ignore')

class SentimentAnalyzer:
    """
    Sentiment Analysis Model
    Detects overall emotional polarity: Negative, Neutral, Positive
    """
    
    def __init__(self, model_name: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"):
        """
        Initialize sentiment analyzer
        
        Args:
            model_name: HuggingFace model identifier
        """
        logger.info(f"Loading sentiment model: {model_name}")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        
        # Get label mapping from config
        self.config = AutoConfig.from_pretrained(model_name)
        self.labels = ["negative", "neutral", "positive"]
        
        logger.success(f"Sentiment model loaded on {self.device}")
    
    def analyze(self, text: str) -> Dict[str, any]:
        """
        Analyze sentiment of text
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dict containing:
                - label: sentiment label (negative/neutral/positive)
                - score: confidence score
                - probabilities: dict of all label probabilities
                - sentiment_score: numeric score (-1 to 1)
        """
        if not text or not text.strip():
            return {
                "label": "neutral",
                "score": 0.0,
                "probabilities": {"negative": 0.0, "neutral": 1.0, "positive": 0.0},
                "sentiment_score": 0.0
            }
        
        try:
            # Tokenize and predict
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                scores = torch.nn.functional.softmax(outputs.logits[0], dim=0)
            
            # Get predictions
            scores_dict = {label: score.item() for label, score in zip(self.labels, scores)}
            max_label = max(scores_dict, key=scores_dict.get)
            max_score = scores_dict[max_label]
            
            # Calculate numeric sentiment score (-1 to 1)
            sentiment_score = (
                scores_dict["positive"] - scores_dict["negative"]
            )
            
            return {
                "label": max_label,
                "score": max_score,
                "probabilities": scores_dict,
                "sentiment_score": sentiment_score
            }
            
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {
                "label": "neutral",
                "score": 0.0,
                "probabilities": {"negative": 0.0, "neutral": 1.0, "positive": 0.0},
                "sentiment_score": 0.0
            }
    
    def batch_analyze(self, texts: List[str]) -> List[Dict[str, any]]:
        """
        Analyze sentiment of multiple texts in batch
        
        Args:
            texts: List of input texts
            
        Returns:
            List of sentiment analysis results
        """
        return [self.analyze(text) for text in texts]


class EmotionDetector:
    """
    Emotion Detection Model
    Detects: sadness, anger, fear, joy, surprise, disgust, neutral
    Focus on distress emotions: sadness, anger, fear
    """
    
    def __init__(self, model_name: str = "j-hartmann/emotion-english-distilroberta-base"):
        """
        Initialize emotion detector
        
        Args:
            model_name: HuggingFace model identifier
        """
        logger.info(f"Loading emotion model: {model_name}")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        
        # Emotion labels for this model
        self.labels = ["anger", "disgust", "fear", "joy", "neutral", "sadness", "surprise"]
        self.distress_emotions = ["sadness", "anger", "fear"]
        
        logger.success(f"Emotion model loaded on {self.device}")
    
    def detect(self, text: str) -> Dict[str, any]:
        """
        Detect emotion in text
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dict containing:
                - label: primary emotion label
                - score: confidence score
                - probabilities: dict of all emotion probabilities
                - is_distress: whether emotion indicates distress
                - distress_score: combined distress emotion score
        """
        if not text or not text.strip():
            return {
                "label": "neutral",
                "score": 0.0,
                "probabilities": {label: 0.0 for label in self.labels},
                "is_distress": False,
                "distress_score": 0.0
            }
        
        try:
            # Tokenize and predict
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                scores = torch.nn.functional.softmax(outputs.logits[0], dim=0)
            
            # Get predictions
            scores_dict = {label: score.item() for label, score in zip(self.labels, scores)}
            max_label = max(scores_dict, key=scores_dict.get)
            max_score = scores_dict[max_label]
            
            # Calculate distress score (sum of sadness, anger, fear)
            distress_score = sum(scores_dict[emotion] for emotion in self.distress_emotions)
            is_distress = max_label in self.distress_emotions
            
            return {
                "label": max_label,
                "score": max_score,
                "probabilities": scores_dict,
                "is_distress": is_distress,
                "distress_score": distress_score
            }
            
        except Exception as e:
            logger.error(f"Emotion detection error: {e}")
            return {
                "label": "neutral",
                "score": 0.0,
                "probabilities": {label: 0.0 for label in self.labels},
                "is_distress": False,
                "distress_score": 0.0
            }
    
    def batch_detect(self, texts: List[str]) -> List[Dict[str, any]]:
        """
        Detect emotions in multiple texts in batch
        
        Args:
            texts: List of input texts
            
        Returns:
            List of emotion detection results
        """
        return [self.detect(text) for text in texts]


class CognitiveDistortionDetector:
    """
    Cognitive Distortion Detection using Sentence Embeddings
    
    Detects distorted thinking patterns:
    - Overgeneralization
    - All-or-nothing thinking
    - Catastrophizing
    - Hopelessness language
    """
    
    # Template phrases for each distortion type
    DISTORTION_TEMPLATES = {
        "overgeneralization": [
            "I always fail",
            "I never succeed",
            "everything goes wrong",
            "nothing ever works",
            "everyone hates me",
            "nobody likes me",
            "I always mess up",
            "things never get better"
        ],
        "all_or_nothing": [
            "I'm a complete failure",
            "I'm totally worthless",
            "everything is ruined",
            "nothing matters anymore",
            "I'm either perfect or useless",
            "if I can't do it perfectly, it's not worth doing"
        ],
        "catastrophizing": [
            "this is the worst thing ever",
            "my life is over",
            "everything is falling apart",
            "this is a disaster",
            "I can't handle this",
            "this will ruin everything",
            "it's going to be terrible"
        ],
        "hopelessness": [
            "there's no point",
            "nothing will help",
            "I give up",
            "it's hopeless",
            "I can't go on",
            "what's the point of trying",
            "things will never change",
            "I don't see a way out"
        ]
    }
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", threshold: float = 0.6):
        """
        Initialize cognitive distortion detector
        
        Args:
            model_name: Sentence transformer model name
            threshold: Similarity threshold for distortion detection (0-1)
        """
        logger.info(f"Loading distortion detection model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.threshold = threshold
        
        # Pre-encode all distortion templates
        self.encoded_templates = {}
        for distortion_type, templates in self.DISTORTION_TEMPLATES.items():
            self.encoded_templates[distortion_type] = self.model.encode(
                templates, convert_to_tensor=True
            )
        
        logger.success("Cognitive distortion detector initialized")
    
    def detect(self, text: str) -> Dict[str, any]:
        """
        Detect cognitive distortions in text
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dict containing:
                - distortion_indicator: 1 if distortion detected, 0 otherwise
                - distortion_score: highest similarity score
                - distortion_category: type of distortion (if detected)
                - all_scores: similarity scores for all distortion types
        """
        if not text or not text.strip():
            return {
                "distortion_indicator": 0,
                "distortion_score": 0.0,
                "distortion_category": None,
                "all_scores": {}
            }
        
        try:
            # Encode input text
            text_embedding = self.model.encode(text, convert_to_tensor=True)
            
            # Calculate similarities with each distortion type
            distortion_scores = {}
            max_similarity = 0.0
            max_category = None
            
            for distortion_type, template_embeddings in self.encoded_templates.items():
                # Compute cosine similarities with all templates of this type
                similarities = util.cos_sim(text_embedding, template_embeddings)[0]
                
                # Take maximum similarity for this distortion type
                max_sim = similarities.max().item()
                distortion_scores[distortion_type] = max_sim
                
                if max_sim > max_similarity:
                    max_similarity = max_sim
                    max_category = distortion_type
            
            # Determine if distortion is present
            distortion_detected = max_similarity >= self.threshold
            
            return {
                "distortion_indicator": 1 if distortion_detected else 0,
                "distortion_score": max_similarity,
                "distortion_category": max_category if distortion_detected else None,
                "all_scores": distortion_scores
            }
            
        except Exception as e:
            logger.error(f"Cognitive distortion detection error: {e}")
            return {
                "distortion_indicator": 0,
                "distortion_score": 0.0,
                "distortion_category": None,
                "all_scores": {}
            }
    
    def batch_detect(self, texts: List[str]) -> List[Dict[str, any]]:
        """
        Detect cognitive distortions in multiple texts
        
        Args:
            texts: List of input texts
            
        Returns:
            List of distortion detection results
        """
        return [self.detect(text) for text in texts]


class NLPPipeline:
    """
    Complete NLP Pipeline integrating all three models
    """
    
    def __init__(self):
        """Initialize all NLP models"""
        logger.info("Initializing NLP Pipeline...")
        
        self.sentiment_analyzer = SentimentAnalyzer()
        self.emotion_detector = EmotionDetector()
        self.distortion_detector = CognitiveDistortionDetector()
        
        logger.success("NLP Pipeline ready")
    
    def analyze(self, text: str) -> Dict[str, any]:
        """
        Run complete NLP analysis on text
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dict containing all analysis results
        """
        return {
            "text": text,
            "sentiment": self.sentiment_analyzer.analyze(text),
            "emotion": self.emotion_detector.detect(text),
            "distortion": self.distortion_detector.detect(text)
        }
    
    def batch_analyze(self, texts: List[str]) -> List[Dict[str, any]]:
        """
        Run complete NLP analysis on multiple texts
        
        Args:
            texts: List of input texts
            
        Returns:
            List of complete analysis results
        """
        return [self.analyze(text) for text in texts]
