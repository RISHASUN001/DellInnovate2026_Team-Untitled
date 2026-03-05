from dataclasses import dataclass
from fastapi import Request, HTTPException
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
    user_id = request.headers.get("X-User-Id", settings.default_user_id).strip()
    role = request.headers.get("X-User-Role", settings.default_user_role).strip()
    if role not in VALID_ROLES:
        role = settings.default_user_role
    return AuthUser(user_id=user_id, role=role)


def require_admin(request: Request) -> AuthUser:
    user = get_current_user(request)
    if not user.is_admin:
        raise HTTPException(403, "Admin role required")
    return user
