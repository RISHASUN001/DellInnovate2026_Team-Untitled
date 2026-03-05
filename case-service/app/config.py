from pydantic_settings import BaseSettings
import os
from pathlib import Path


class Settings(BaseSettings):
    mongodb_uri: str = ""
    scs_db_name: str = "dellinnovate"
    default_user_id: str = "sarah_l"
    default_user_role: str = "Admin"
    allowed_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000"

    class Config:
        # Look for .env in parent directory
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        extra = "ignore"

    @property
    def mongo_uri(self) -> str:
        """Get MongoDB URI from env or settings"""
        return self.mongodb_uri or os.getenv("MONGODB_URI", "")


settings = Settings()
