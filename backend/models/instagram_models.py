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
    created_at: Optional[datetime] = None  # Alias for timestamp, used for time windowing
    
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
    
    # ========== NEW FIELDS FOR PCA SCORING ==========
    distress_emotion: Optional[float] = None  # max(p_anger, p_sadness, p_fear) from emotion_probabilities
    is_negative: Optional[int] = None  # 1 if sentiment_label == 'negative', else 0
    distortion_flag: Optional[int] = None  # Alias for distortion_indicator (for clarity)
    
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
    
    NOTE: This model supports both legacy (hand-coded) and new (PCA+LLM) scoring systems
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    # Case identification
    case_user: str  # Instagram username
    timestamp: datetime = Field(default_factory=datetime.utcnow)  # When profile was computed
    window_days: Optional[int] = None  # Time window for signal aggregation
    
    # ========== NEW PCA + LLM SCORING FIELDS ==========
    # Aggregated component scores (0-1 scale)
    emotion_score: Optional[float] = None  # Distress emotion score (0.7*mean + 0.3*p90)
    sentiment_score: Optional[float] = None  # Negativity score (0.7*mean + 0.3*p90)
    harm_score: Optional[float] = None  # Distortion/harm score (0.7*mean + 0.3*p90)
    
    # Sample size and damping
    n_units: Optional[int] = None  # Number of text units analyzed
    damp: Optional[float] = None  # Damping factor for low sample sizes (sigmoid)
    
    # PCA-derived risk score
    risk_score_math: Optional[float] = None  # PCA PC1 score normalized to [0,1]
    pc1_loadings: Optional[Dict[str, float]] = None  # {"emotion": ..., "sentiment": ..., "harm": ...}
    pca_run_id: Optional[str] = None  # Identifier for this PCA run
    
    # Guardrailed and calibrated scores
    base_score: Optional[float] = None  # max(risk_score_math, 0.40 * harm_score)
    llm_delta: Optional[float] = None  # LLM adjustment (±0.10)
    llm_delta1: Optional[float] = None  # First LLM run delta
    llm_delta2: Optional[float] = None  # Second LLM run delta
    final_score: Optional[float] = None  # base_score + llm_delta, clamped [0,1]
    
    # Priority level
    priority_level: Optional[str] = None  # "low", "medium", "high", "critical"
    
    # Evidence traceability
    evidence_unit_ids: Optional[List[str]] = []  # IDs of key text units for explainability
    
    # ========== LEGACY FIELDS (for backward compatibility) ==========
    # Time windows
    analysis_window_days: Optional[int] = None  # e.g., 7, 30
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    
    # Signal counts
    total_comments_received: Optional[int] = None
    total_captions: Optional[int] = None
    total_text_units: Optional[int] = None
    
    # Distortion metrics
    distortion_count: Optional[int] = None
    distortion_rate: Optional[float] = None  # distorted_comments / total_comments
    distortion_trend: Optional[float] = None  # Change in distortion rate
    distortion_categories: Optional[Dict[str, int]] = None  # Count by distortion type
    
    # Sentiment metrics
    avg_sentiment_score: Optional[float] = None
    sentiment_std: Optional[float] = None  # Volatility measure
    negative_sentiment_rate: Optional[float] = None
    positive_sentiment_rate: Optional[float] = None
    sentiment_shift_rate: Optional[float] = None  # Rapid polarity changes
    
    # Emotion metrics
    distress_emotion_count: Optional[int] = None  # sadness/anger/fear
    distress_emotion_rate: Optional[float] = None
    emotion_distribution: Optional[Dict[str, int]] = None  # Count by emotion type
    avg_distress_score: Optional[float] = None
    
    # Engagement metrics
    comment_volume_change: Optional[float] = None  # Compared to previous period
    abnormal_activity: Optional[bool] = None  # Flag for unusual patterns
    late_night_activity_rate: Optional[float] = None  # 11 PM - 2 AM posts
    
    # Risk scoring (legacy 0-100 scale)
    risk_score: Optional[float] = None  # 0-100 composite risk score
    risk_level: Optional[str] = None  # "Low", "Medium", "High"
    priority: Optional[int] = None  # 1 (High), 2 (Medium), 3 (Low)
    
    # Supporting evidence
    top_distress_comments: Optional[List[str]] = []  # Sample concerning comments
    key_signals: Optional[List[str]] = []  # Human-readable signal descriptions
    metrics: Optional[Dict[str, Any]] = None  # Additional metrics
    
    # Metadata
    computed_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    last_updated: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
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


# ========== SCS Operational Models ==========

class SCSCaseModel(BaseModel):
    """
    Model for operational SCS cases
    Collection: scs_cases
    
    This is the operational case management table used by youth workers.
    Populated from case_risk_profiles by the promotion service.
    """
    case_id: str  # e.g., "CASE_2026_001"
    user_id: str  # Social media handle being monitored (e.g., "@at_risk_teen_01")
    assigned_to: Optional[str] = None  # References scs_users.user_id
    current_risk_score: float  # 0-100 scale
    category: str  # Risk category (e.g., "depression_risk", "self_harm_risk")
    ai_explanation: str  # LLM-generated or aggregated explanation
    case_status: str = "unassigned"  # "unassigned" | "assigned"
    work_status: str = "not_started"  # "not_started" | "in_progress" | "to_review" | "completed"
    priority: str = "medium"  # "low" | "medium" | "high" | "critical"
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


class SCSCaseHistoryModel(BaseModel):
    """
    Model for case history snapshots
    Collection: scs_case_history
    
    Stores one entry per ingestion cycle, tracking risk evolution over time.
    """
    history_id: int  # Auto-increment ID
    case_id: str  # References scs_cases.case_id
    risk_score: float  # Historical risk score
    category: str  # Historical category
    ai_explanation: str  # AI explanation at this point in time
    ingestion_date: datetime  # When this assessment was made
    model_version: str  # AI model version used (e.g., "nlp-v1-pca-v1-llm-v1")
    
    class Config:
        populate_by_name = True


class SCSChecklistItemModel(BaseModel):
    """
    Model for case checklist items
    Collection: scs_checklist
    
    Task tracking for each case. Mandatory items are auto-created from templates.
    """
    checklist_item_id: int  # Auto-increment ID
    case_id: str  # References scs_cases.case_id
    template_id: Optional[int] = None  # References scs_checklist_templates.template_id (null for custom)
    label: str  # Task description
    is_mandatory: bool = False  # Required task?
    completed: bool = False  # Task status
    comments: List[Dict[str, Any]] = []  # Array of {comment, timestamp, by}
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None  # References scs_users.user_id
    display_order: int = 0  # UI ordering
    created_at: datetime
    
    class Config:
        populate_by_name = True


class SCSChecklistTemplateModel(BaseModel):
    """
    Model for checklist templates
    Collection: scs_checklist_templates
    
    Defines standard mandatory tasks that are auto-created for new cases.
    """
    template_id: int  # Unique template ID
    label: str  # Task description
    is_mandatory: bool = True  # Required for all cases?
    display_order: int = 0  # UI ordering
    is_active: bool = True  # Template enabled?
    created_at: datetime
    
    class Config:
        populate_by_name = True


class SCSUserModel(BaseModel):
    """
    Model for SCS staff users
    Collection: scs_users
    
    User accounts for admins and youth helpers.
    """
    user_id: str  # Unique identifier
    username: str  # Display name
    role: str  # "admin" | "youth_helper"
    email: str  # Contact email
    is_active: bool = True  # Account status
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True