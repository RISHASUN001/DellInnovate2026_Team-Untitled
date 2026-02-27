from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .config import settings
from .database import get_db, close_db
from .schema import SCHEMA_SQL
from .seed import seed
from .routes import cases, checklist, history, notes


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("case-service starting up...")
    db = await get_db()
    # Create all tables
    await db.executescript(SCHEMA_SQL)
    await db.commit()
    # Seed mock data (idempotent)
    await seed(db)
    yield
    await close_db()
    logger.info("case-service shut down.")


app = FastAPI(
    title="SCS Case Service",
    description="Core case management API for SCS Youth Case Dashboard",
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

app.include_router(cases.router)
app.include_router(checklist.router)
app.include_router(history.router)
app.include_router(notes.router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "case-service"}


@app.get("/")
async def root():
    return {
        "service": "SCS Case Service",
        "version": "1.0.0",
        "endpoints": {
            "cases_summary": "GET /cases/summary",
            "assigned_cases": "GET /cases/assigned",
            "needs_review": "GET /cases/needs-review",
            "case_detail": "GET /cases/{case_id}",
            "case_history": "GET /cases/{case_id}/history",
            "checklist": "GET /cases/{case_id}/checklist",
            "notes": "GET /cases/{case_id}/notes",
            "followups": "GET /cases/{case_id}/followups",
        },
    }
