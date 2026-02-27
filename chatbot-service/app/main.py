from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

from .config import settings
from .rag import ingest_documents
from .similarity import get_similar_cases, rebuild_graph
from .assistant import chat


class Message(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    case_context: Optional[dict] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("chatbot-service starting up — ingesting RAG documents...")
    await ingest_documents()
    logger.info("RAG ingestion complete.")
    yield
    logger.info("chatbot-service shutting down.")


app = FastAPI(
    title="SCS Chatbot Service",
    description="RAG-backed assistant with ChromaDB + NetworkX similarity for SCS Youth Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_user(request: Request) -> tuple[str, str]:
    user_id = request.headers.get("X-User-Id", settings.default_user_id)
    role = request.headers.get("X-User-Role", settings.default_user_role)
    return user_id, role


@app.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    user_id, role = _get_user(request)
    messages = [m.model_dump() for m in req.messages]
    result = await chat(
        messages=messages,
        case_context=req.case_context,
        user_id=user_id,
        user_role=role,
    )
    return result


@app.get("/similar-cases/{case_id}")
async def similar_cases_endpoint(case_id: str, top_k: int = 5):
    results = await get_similar_cases(case_id, top_k=top_k)
    return {"case_id": case_id, "similar_cases": results}


@app.post("/rebuild-graph")
async def rebuild_graph_endpoint():
    await rebuild_graph()
    return {"status": "rebuilt"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "chatbot-service"}
