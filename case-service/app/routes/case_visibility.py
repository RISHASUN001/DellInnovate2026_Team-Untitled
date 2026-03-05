"""
Additional route for case visibility - allows Youth Helpers to see all cases in list view
but only access full details for their assigned cases
"""
from fastapi import APIRouter, Request
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("/all-visible")
async def list_all_cases_visible(request: Request):
    """
    List ALL cases with limited info for youth helpers.
    - Youth Helpers can see all cases in the list
    - But they can only view full details of cases assigned to them
    - This allows awareness without breaking confidentiality
    """
    user = get_current_user(request)
    db = await get_db()
    
    query = """
        SELECT 
            case_id,
            user_id,
            assigned_to,
            risk_score,
            category,
            case_status,
            work_status,
            status,
            priority,
            needs_review,
            created_at,
            last_signal_at FROM cases
        ORDER BY created_at DESC
    """
    
    async with db.execute(query) as cur:
        rows = await cur.fetchall()
    
    results = []
    for row in rows:
        case_dict = dict(row)
        
        # For youth helpers, mark whether they have access to full details
        if user.is_helper:
            case_dict["can_access_details"] = (case_dict["assigned_to"] == user.user_id)
        else:
            case_dict["can_access_details"] = True  # Admins can access all
        
        results.append(case_dict)
    
    return {
        "cases": results,
        "total": len(results),
        "user_role": user.role,
        "accessible_count": len([c for c in results if c["can_access_details"]])
    }
