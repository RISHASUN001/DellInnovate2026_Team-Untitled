"""
Placeholder authentication middleware.
In production this would validate JWTs; here it reads X-User-Id and X-User-Role headers.
Falls back to env-configured defaults so every endpoint works out of the box.
"""
from dataclasses import dataclass
from typing import Optional
from fastapi import Request
from .config import settings

VALID_ROLES = {"Admin", "Youth Helper"}


@dataclass
class AuthUser:
    user_id: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "Admin"

    @property
    def is_helper(self) -> bool:
        return self.role == "Youth Helper"


def get_current_user(request: Request) -> AuthUser:
    """Extract user identity from headers with env fallback."""
    user_id = request.headers.get("X-User-Id", settings.default_user_id).strip()
    role = request.headers.get("X-User-Role", settings.default_user_role).strip()

    if role not in VALID_ROLES:
        role = settings.default_user_role

    return AuthUser(user_id=user_id, role=role)


async def require_admin(request: Request) -> AuthUser:
    user = get_current_user(request)
    if not user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


async def require_auth(request: Request) -> AuthUser:
    return get_current_user(request)
