from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = "sk-placeholder"
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "all-MiniLM-L6-v2"
    chroma_persist_dir: str = "/data/chromadb"
    docs_dir: str = "/app/docs"
    case_service_url: str = "http://case-service:8001"
    mcp_service_url: str = "http://mcp-service:8003"
    default_user_id: str = "sarah_l"
    default_user_role: str = "Admin"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
