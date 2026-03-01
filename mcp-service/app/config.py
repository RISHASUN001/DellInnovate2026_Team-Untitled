from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB settings
    mongodb_uri: str  # Read from MONGODB_URI in .env
    scs_db_name: str = "dellinnovate"
    
    # Service settings
    chatbot_service_url: str = "http://chatbot-service:8000"
    default_user_id: str = "sarah_l"
    default_user_role: str = "Admin"
    allowed_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000"

    class Config:
        env_file = "../.env"
        extra = "ignore"


settings = Settings()
