from pydantic import BaseModel, Field, GetJsonSchemaHandler
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from pydantic_core import CoreSchema
from pydantic.json_schema import JsonSchemaValue

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        json_schema.update(type="string")
        return json_schema

class InstagramUserModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str
    name: Optional[str] = None
    user_id: Optional[str] = None
    category: Optional[str] = None
    business_category: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None
    bio_links: Optional[List[str]] = []
    homepage: Optional[str] = None
    followers: Optional[int] = 0
    follows: Optional[int] = 0
    facebook_id: Optional[str] = None
    is_private: Optional[bool] = False
    is_verified: Optional[bool] = False
    profile_image: Optional[str] = None
    video_count: Optional[int] = 0
    videos: Optional[List[Dict[str, Any]]] = []
    image_count: Optional[int] = 0
    images: Optional[List[Dict[str, Any]]] = []
    saved_count: Optional[int] = 0
    collections_count: Optional[int] = 0
    related_profiles: Optional[List[str]] = []
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True  # Changed from allow_population_by_field_name in v2
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class InstagramPostModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    post_id: Optional[str] = None
    shortcode: str
    username: Optional[str] = None  # The username who posted this
    dimensions: Optional[Dict] = None
    src: Optional[str] = None
    thumbnail_src: Optional[str] = None
    media_preview: Optional[str] = None
    video_url: Optional[str] = None
    views: Optional[int] = 0
    likes: Optional[int] = 0
    location: Optional[str] = None
    taken_at: Optional[int] = None
    related: Optional[List[str]] = []
    type: Optional[str] = None
    video_duration: Optional[float] = None
    music: Optional[Dict] = None
    is_video: Optional[bool] = False
    tagged_users: Optional[List[str]] = []
    captions: Optional[List[str]] = []
    related_profiles: Optional[List[str]] = []
    comments_count: Optional[int] = 0
    comments_disabled: Optional[bool] = False
    comments_next_page: Optional[str] = None
    comments: Optional[List[Dict]] = []
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class ScrapeJobModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    job_type: str  # "user", "post", "user_posts"
    targets: List[str]  # usernames or post URLs
    status: str  # "pending", "in_progress", "completed", "failed"
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class ScrapeRequest(BaseModel):
    usernames: List[str]
    scrape_posts: bool = True
    max_posts_per_user: Optional[int] = None
    scrape_post_details: bool = True
    post_urls: Optional[List[str]] = []
    
    class Config:
        populate_by_name = True


# ========== Analytics Models ==========

class TextUnitSignalModel(BaseModel):
    """
    Model for storing NLP signals from individual text units (captions/comments)
    Collection: text_units_signals
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    # Text unit identification
    case_user: str  # Instagram username of the post owner (user receiving comments)
    text_type: str  # "caption" or "comment"
    text: str  # Original text content
    post_id: str  # Post shortcode/ID
    comment_id: Optional[str] = None  # Comment ID if text_type is "comment"
    author: Optional[str] = None  # Username of text author (commenter or post owner)
    timestamp: Optional[datetime] = None
    
    # NLP Analysis Results
    sentiment_label: str  # "negative", "neutral", "positive"
    sentiment_score: float  # -1 to 1
    sentiment_probabilities: Dict[str, float]  # All sentiment probabilities
    
    emotion_label: str  # Primary detected emotion
    emotion_score: float  # Confidence score
    emotion_probabilities: Dict[str, float]  # All emotion probabilities
    is_distress: bool  # Whether emotion indicates distress
    distress_score: float  # Combined sadness/anger/fear score
    
    distortion_indicator: int  # 0 or 1
    distortion_score: float  # Similarity score
    distortion_category: Optional[str] = None  # Type of distortion detected
    distortion_all_scores: Optional[Dict[str, float]] = None  # All distortion type scores
    
    # Metadata
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    preprocessed_text: Optional[str] = None  # Cleaned text used for analysis
    language: Optional[str] = None  # Detected language
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class CaseRiskProfileModel(BaseModel):
    """
    Model for storing aggregated risk profiles per case user
    Collection: case_risk_profiles
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    # Case identification
    case_user: str  # Instagram username
    
    # Time windows
    analysis_window_days: int  # e.g., 7, 30
    window_start: datetime
    window_end: datetime
    
    # Signal counts
    total_comments_received: int
    total_captions: int
    total_text_units: int
    
    # Distortion metrics
    distortion_count: int
    distortion_rate: float  # distorted_comments / total_comments
    distortion_trend: Optional[float] = None  # Change in distortion rate
    distortion_categories: Dict[str, int]  # Count by distortion type
    
    # Sentiment metrics
    avg_sentiment_score: float
    sentiment_std: float  # Volatility measure
    negative_sentiment_rate: float
    positive_sentiment_rate: float
    sentiment_shift_rate: Optional[float] = None  # Rapid polarity changes
    
    # Emotion metrics
    distress_emotion_count: int  # sadness/anger/fear
    distress_emotion_rate: float
    emotion_distribution: Dict[str, int]  # Count by emotion type
    avg_distress_score: float
    
    # Engagement metrics
    comment_volume_change: Optional[float] = None  # Compared to previous period
    abnormal_activity: bool  # Flag for unusual patterns
    late_night_activity_rate: Optional[float] = None  # 11 PM - 2 AM posts
    
    # Risk scoring
    risk_score: float  # 0-100 composite risk score
    risk_level: str  # "Low", "Medium", "High"
    priority: int  # 1 (High), 2 (Medium), 3 (Low)
    
    # Supporting evidence
    top_distress_comments: List[str] = []  # Sample concerning comments
    key_signals: List[str] = []  # Human-readable signal descriptions
    
    # Metadata
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class AnalyticsPipelineJobModel(BaseModel):
    """
    Model for tracking analytics pipeline execution jobs
    Collection: analytics_jobs
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    job_type: str  # "nlp_extraction", "feature_engineering", "full_pipeline"
    status: str  # "pending", "running", "completed", "failed"
    
    # Configuration
    case_users: Optional[List[str]] = None  # Specific users to process (None = all)
    window_days: Optional[int] = 7  # Time window for feature engineering
    
    # Progress tracking
    total_items: Optional[int] = None
    processed_items: Optional[int] = 0
    failed_items: Optional[int] = 0
    
    # Results
    results_summary: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = []
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}