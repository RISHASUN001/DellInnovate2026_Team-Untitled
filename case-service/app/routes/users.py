"""
Users route — exposes the scs_users collection for the Admin assignment dropdown.

AUTH_SERVICE_CALL: The /users endpoints do not currently enforce authentication.
In production, gate these routes with a proper auth dependency that verifies the
caller has Admin or Youth Helper role (e.g. via JWT from the identity provider).
"""
from fastapi import APIRouter, HTTPException, Query
from ..database import get_db, serialize_doc

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/helpers")
async def get_helpers():
    """Return all Youth Helper staff — used to populate assignment dropdowns."""
    db = await get_db()
    users_col = db['scs_users']
    
    cursor = users_col.find(
        {"role": "youth_helper", "is_active": True}
    ).sort("username", 1)
    
    users = await cursor.to_list(length=None)
    return [serialize_doc(user) for user in users]


@router.get("")
async def get_all_users(role: str = Query(None)):
    """Return all staff (Admin + Youth Helper) or filter by role.
    AUTH_SERVICE_CALL: Restrict to Admin role in production."""
    db = await get_db()
    users_col = db['scs_users']
    
    # Build query filter
    query = {"is_active": True}
    if role:
        query["role"] = role
    
    cursor = users_col.find(query).sort("role", 1).sort("username", 1)
    users = await cursor.to_list(length=None)
    
    return [serialize_doc(user) for user in users]


@router.get("/{user_id}")
async def get_user(user_id: str):
    """Return a single user by user_id."""
    db = await get_db()
    users_col = db['scs_users']
    
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    
    return serialize_doc(user)
