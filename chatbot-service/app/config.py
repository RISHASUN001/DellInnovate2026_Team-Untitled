import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── OpenRouter LLM ──────────────────────────────────────────────────────
    openrouter_api_key: str = "sk-or-placeholder"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-chat-v3.1"

    # ── Embeddings + ChromaDB ───────────────────────────────────────────────
    embedding_model: str = "openai/text-embedding-ada-002"
    openrouter_embedding_model: str = "openai/text-embedding-ada-002"
    chroma_persist_dir: str = "../data/chromadb"
    docs_dir: str = "./docs"

    # ── Inter-service URLs ──────────────────────────────────────────────────
    case_service_url: str = "http://localhost:8003"
    mcp_service_url: str = "http://localhost:8002"

    # ── Auth defaults ───────────────────────────────────────────────────────
    default_user_id: str = "sarah_l"
    default_user_role: str = "Admin"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    class Config:
        env_file = "../.env"  # Look for .env in parent directory
        extra = "ignore"


settings = Settings()

# Legacy exports for compatibility
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY = settings.openrouter_api_key
OPENROUTER_BASE_URL = settings.openrouter_base_url
OPENROUTER_MODEL = settings.openrouter_model
