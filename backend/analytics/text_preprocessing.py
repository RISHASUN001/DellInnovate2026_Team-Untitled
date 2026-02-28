"""
Text Preprocessing Utilities for NLP Pipeline
"""

import re
from typing import Optional, List
from loguru import logger

class TextPreprocessor:
    """
    Lightweight text preprocessing for social media content
    """
    
    # Common URL patterns
    URL_PATTERN = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    
    # Social media mentions and hashtags (keep these as they can be meaningful)
    MENTION_PATTERN = re.compile(r'@\w+')
    HASHTAG_PATTERN = re.compile(r'#\w+')
    
    # Excessive whitespace
    WHITESPACE_PATTERN = re.compile(r'\s+')
    
    # HTML entities and formatting
    HTML_PATTERN = re.compile(r'<[^>]+>')
    
    def __init__(self, 
                 remove_urls: bool = True,
                 remove_mentions: bool = False,  # Keep mentions by default
                 remove_hashtags: bool = False,  # Keep hashtags by default
                 normalize_whitespace: bool = True):
        """
        Initialize text preprocessor
        
        Args:
            remove_urls: Remove HTTP/HTTPS URLs
            remove_mentions: Remove @mentions
            remove_hashtags: Remove #hashtags
            normalize_whitespace: Normalize whitespace to single spaces
        """
        self.remove_urls = remove_urls
        self.remove_mentions = remove_mentions
        self.remove_hashtags = remove_hashtags
        self.normalize_whitespace = normalize_whitespace
    
    def preprocess(self, text: str) -> str:
        """
        Preprocess text with configured options
        
        Args:
            text: Input text to preprocess
            
        Returns:
            Preprocessed text
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Remove HTML tags
        text = self.HTML_PATTERN.sub(' ', text)
        
        # Remove URLs
        if self.remove_urls:
            text = self.URL_PATTERN.sub(' ', text)
        
        # Remove mentions
        if self.remove_mentions:
            text = self.MENTION_PATTERN.sub(' ', text)
        
        # Remove hashtags
        if self.remove_hashtags:
            text = self.HASHTAG_PATTERN.sub(' ', text)
        
        # Normalize whitespace
        if self.normalize_whitespace:
            text = self.WHITESPACE_PATTERN.sub(' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def batch_preprocess(self, texts: List[str]) -> List[str]:
        """
        Preprocess multiple texts
        
        Args:
            texts: List of input texts
            
        Returns:
            List of preprocessed texts
        """
        return [self.preprocess(text) for text in texts]
    
    def is_valid_text(self, text: str, min_length: int = 3) -> bool:
        """
        Check if text is valid for analysis
        
        Args:
            text: Text to validate
            min_length: Minimum character length
            
        Returns:
            True if text is valid, False otherwise
        """
        if not text or not isinstance(text, str):
            return False
        
        processed = self.preprocess(text)
        
        # Check minimum length
        if len(processed) < min_length:
            return False
        
        # Check if text has actual content (not just punctuation/emojis)
        alpha_chars = sum(c.isalpha() for c in processed)
        if alpha_chars < 2:
            return False
        
        return True


class LanguageDetector:
    """
    Simple language detection for filtering non-English content
    (Optional - can be enhanced with langdetect library if needed)
    """
    
    # Common English stop words for basic detection
    ENGLISH_STOPWORDS = {
        'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
        'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
        'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
        'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
        'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me'
    }
    
    def is_likely_english(self, text: str, threshold: float = 0.3) -> bool:
        """
        Basic check if text is likely English
        
        Args:
            text: Text to check
            threshold: Minimum ratio of English stopwords
            
        Returns:
            True if likely English, False otherwise
        """
        if not text:
            return False
        
        # Tokenize (simple split)
        words = re.findall(r'\b\w+\b', text.lower())
        
        if not words:
            return False
        
        # Count English stopwords
        english_word_count = sum(1 for word in words if word in self.ENGLISH_STOPWORDS)
        
        # Calculate ratio
        ratio = english_word_count / len(words)
        
        return ratio >= threshold
    
    def detect_language(self, text: str) -> str:
        """
        Simple language detection
        
        Args:
            text: Text to detect language
            
        Returns:
            'en' for English, 'unknown' otherwise
        """
        if self.is_likely_english(text):
            return 'en'
        return 'unknown'


def extract_text_units_from_post(post_data: dict) -> List[dict]:
    """
    Extract text units (captions and comments) from Instagram post document
    
    Args:
        post_data: Instagram post document from MongoDB
        
    Returns:
        List of text units with metadata
    """
    text_units = []
    case_user = post_data.get('username')
    post_id = post_data.get('shortcode') or post_data.get('post_id')
    
    # Extract captions
    captions = post_data.get('captions', [])
    for caption in captions:
        if caption and isinstance(caption, str) and caption.strip():
            text_units.append({
                'case_user': case_user,
                'text_type': 'caption',
                'text': caption,
                'post_id': post_id,
                'author': case_user,  # Caption is by the post owner
                'timestamp': post_data.get('scraped_at')
            })
    
    # Extract comments
    comments = post_data.get('comments', [])
    for comment in comments:
        if isinstance(comment, dict):
            comment_text = comment.get('text', '')
            if comment_text and comment_text.strip():
                # Handle owner field - can be string or dict
                owner = comment.get('owner')
                if isinstance(owner, dict):
                    author = owner.get('username')
                elif isinstance(owner, str):
                    author = owner
                else:
                    author = None
                
                text_units.append({
                    'case_user': case_user,  # The user receiving the comment
                    'text_type': 'comment',
                    'text': comment_text,
                    'post_id': post_id,
                    'comment_id': comment.get('id'),
                    'author': author,
                    'timestamp': comment.get('created_at')
                })
    
    return text_units


def extract_text_units_from_user_posts(posts: List[dict]) -> List[dict]:
    """
    Extract all text units from multiple posts of a user
    
    Args:
        posts: List of Instagram post documents
        
    Returns:
        Combined list of text units
    """
    all_text_units = []
    
    for post in posts:
        text_units = extract_text_units_from_post(post)
        all_text_units.extend(text_units)
    
    logger.info(f"Extracted {len(all_text_units)} text units from {len(posts)} posts")
    
    return all_text_units
