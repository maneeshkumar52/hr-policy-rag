"""JWT validation and RBAC for the HR RAG system."""
from typing import Optional
import structlog
from fastapi import HTTPException, Header
from jose import jwt, JWTError
from src.models import UserContext
from src.config import get_settings

logger = structlog.get_logger(__name__)

# Mock user database for development
MOCK_USERS = {
    "user-001": UserContext(user_id="user-001", email="alice@contoso.com", role="employee", department="Engineering", clearance_level=1),
    "user-002": UserContext(user_id="user-002", email="bob@contoso.com", role="manager", department="Finance", clearance_level=2),
    "user-003": UserContext(user_id="user-003", email="carol@contoso.com", role="hr_admin", department="HR", clearance_level=3),
}

ROLE_CLEARANCE_MAP = {
    "employee": 1,
    "manager": 2,
    "hr_admin": 3,
}


def create_test_token(user_id: str, role: str = None) -> str:
    """Create a test JWT token for development."""
    settings = get_settings()
    payload = {"sub": user_id, "user_id": user_id}
    if role:
        payload["role"] = role
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def validate_token(authorization: Optional[str] = Header(None)) -> UserContext:
    """
    Validate JWT and extract user context with RBAC.

    Args:
        authorization: Bearer token from Authorization header.

    Returns:
        UserContext with user details and clearance level.
    """
    settings = get_settings()

    if not authorization:
        # Development fallback: return employee-level user
        logger.warning("no_auth_header_using_dev_user")
        return MOCK_USERS["user-001"]

    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub") or payload.get("user_id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user identifier")

        # Look up user in mock DB (in production: Azure AD graph API)
        user = MOCK_USERS.get(user_id)
        if not user:
            # Create user from token claims
            role = payload.get("role", "employee")
            user = UserContext(
                user_id=user_id,
                email=payload.get("email", f"{user_id}@contoso.com"),
                role=role,
                department=payload.get("department", "General"),
                clearance_level=ROLE_CLEARANCE_MAP.get(role, 1),
            )

        logger.info("auth_successful", user_id=user.user_id, role=user.role, clearance=user.clearance_level)
        return user

    except JWTError as exc:
        logger.error("jwt_validation_failed", error=str(exc))
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as exc:
        logger.error("auth_error", error=str(exc))
        raise HTTPException(status_code=401, detail="Authentication failed")
