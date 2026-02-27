from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    case_db_path: str = "/data/cases.db"
    chatbot_service_url: str = "http://chatbot-service:8002"
    default_user_id: str = "sarah_l"
    default_user_role: str = "Admin"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
