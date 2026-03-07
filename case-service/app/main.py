from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .config import settings
from .database import get_db, close_db
from .routes import cases_mongo, checklist, history, users

# Use new MongoDB-based routes
from .routes import cases_mongo as cases


app = FastAPI(
    title="SCS Case Service",
    description="Core case management API for SCS Youth Case Dashboard (MongoDB)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register MongoDB-based routes
app.include_router(cases.router)
app.include_router(checklist.router)
app.include_router(history.router)
app.include_router(users.router)


@app.on_event("startup")
async def startup():
    logger.info("SCS Case Service starting (MongoDB mode)...")
    # Test MongoDB connection
    try:
        db = await get_db()
        logger.info(f"✅ Connected to MongoDB database: {settings.scs_db_name}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        raise


@app.on_event("shutdown")
async def shutdown():
    await close_db()
    logger.info("SCS Case Service shut down.")


@app.get("/")
async def root():
    return {
        "service": "SCS Case Service",
        "version": "2.0.0",
        "database": "MongoDB",
        "status": "running"
    }


@app.get("/health")
async def health():
    try:
        db = await get_db()
        # Test DB connection
        await db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


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
