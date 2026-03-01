"""
Case history/timeline endpoints - MongoDB version
Returns ingestion history showing risk score evolution over time
"""
from fastapi import APIRouter, HTTPException, Query
from ..database import get_db, serialize_doc
from typing import Optional

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/cases/{case_id}")
async def get_case_history(
    case_id: str,
    limit: Optional[int] = Query(None, description="Limit number of history entries returned")
):
    """
    Get case history (ingestion timeline) from scs_case_history collection.
    Returns entries in chronological order (oldest first).
    
    Each entry shows:
    - ingestion_date: When this snapshot was taken
    - risk_score: Risk score at that time (0-100)
    - category: Case category
    - ai_explanation: AI explanation/signals at that time
    - model_version: AI model version used
    """
    db = await get_db()
    history_col = db['scs_case_history']
    
    # Verify case exists
    cases_col = db['scs_cases']
    case = await cases_col.find_one({"case_id": case_id})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    
    # Fetch history entries, sorted chronologically (oldest first)
    query = {"case_id": case_id}
    cursor = history_col.find(query).sort("ingestion_date", 1)
    
    if limit:
        cursor = cursor.limit(limit)
    
    entries = await cursor.to_list(length=None)
    
    return [serialize_doc(entry) for entry in entries]
