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

class CommentUserModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str  # Instagram username of the commenter
    user_id: Optional[str] = None  # Instagram user ID
    comments: List[Dict[str, Any]] = []  # List of comments by this user
    total_comments: int = 0
    posts_commented_on: List[str] = []  # List of post shortcodes they commented on
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class BioLinkModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str  # The Instagram user whose bio this link is from
    url: str  # The original URL from bio
    scraped_url: Optional[str] = None  # Final URL after redirects
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    site_name: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    error: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class SocialCloudModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str  # The Instagram user
    platform: str  # e.g., "twitter", "facebook", "linkedin", "tiktok", "youtube", "snapchat"
    profile_url: str  # The social media profile URL
    profile_username: Optional[str] = None  # Username on that platform
    extracted_from: str = "bio_links"  # Where we found this link
    added_at: datetime = Field(default_factory=datetime.utcnow)
    
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