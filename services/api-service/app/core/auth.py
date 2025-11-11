"""IAP-based authentication and role-based access control."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.firestore_client import firestore_client
from app.models import UserInfo, UserRole

logger = logging.getLogger(__name__)

# Cache for role assignments (refresh every 5 minutes)
_role_cache: dict[str, tuple[UserRole, datetime]] = {}
_CACHE_TTL_SECONDS = 300


async def get_iap_user_info(request: Request) -> dict:
    """
    Extract user info from IAP headers and JWT.

    IAP adds the following headers:
    - X-Goog-Authenticated-User-Email: "accounts.google.com:user@example.com"
    - X-Goog-IAP-JWT-Assertion: JWT with user info (name, picture, etc.)

    For local development (no IAP), check X-Dev-User header.

    Returns:
        Dict with user info: email, name, picture

    Raises:
        HTTPException: If no user email found in headers
    """
    # For local development (no IAP), check for X-Dev-User header
    if settings.environment == "local":
        dev_user = request.headers.get("X-Dev-User")
        if dev_user:
            logger.info(f"Local dev mode: Using X-Dev-User={dev_user}")
            return {
                "email": dev_user,
                "name": dev_user.split("@")[0].replace(".", " ").title(),
                "picture": None,
            }

    # Production: Read IAP header for email
    iap_user = request.headers.get("X-Goog-Authenticated-User-Email")
    if not iap_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing IAP authentication header",
        )

    # Strip the "accounts.google.com:" prefix
    if ":" in iap_user:
        email = iap_user.split(":", 1)[1]
    else:
        email = iap_user

    # Try to decode JWT for additional user info (name, picture)
    user_info = {"email": email, "name": None, "picture": None}

    iap_jwt = request.headers.get("X-Goog-IAP-JWT-Assertion")
    if iap_jwt:
        try:
            # Decode JWT without verification (we trust IAP already verified it)
            import base64
            import json

            # Split JWT and decode payload (middle part)
            parts = iap_jwt.split(".")
            if len(parts) == 3:
                # Add padding if needed
                payload = parts[1]
                payload += "=" * (4 - len(payload) % 4)
                decoded = base64.urlsafe_b64decode(payload)
                jwt_data = json.loads(decoded)

                # Extract name and picture from JWT
                user_info["name"] = jwt_data.get("name")
                user_info["picture"] = jwt_data.get("picture")

        except Exception as e:
            logger.warning(f"Failed to decode IAP JWT for user info: {e}")

    # Fallback name from email if not in JWT
    if not user_info["name"]:
        user_info["name"] = email.split("@")[0].replace(".", " ").title()

    return user_info


async def get_user_role(email: str) -> UserRole:
    """
    Get user role from Firestore with caching.

    Role resolution order:
    1. Exact email match
    2. Domain match (e.g., @nextnovate.com)
    3. Default: BLOCKED (no access - must be explicitly granted a role)

    Args:
        email: User email address

    Returns:
        UserRole enum
    """
    # Check cache first
    now = datetime.now(UTC)
    if email in _role_cache:
        cached_role, cached_at = _role_cache[email]
        if (now - cached_at).total_seconds() < _CACHE_TTL_SECONDS:
            return cached_role

    # Query Firestore for role assignments
    role_collection = firestore_client.db.collection("user_roles")

    # 1. Check for exact email match
    email_query = role_collection.where("email", "==", email.lower()).limit(1)
    email_results = list(email_query.stream())

    if email_results:
        role_data = email_results[0].to_dict()
        role = UserRole(role_data["role"])
        _role_cache[email] = (role, now)
        return role

    # 2. Check for domain match
    domain = email.split("@")[-1].lower()
    domain_query = role_collection.where("domain", "==", domain).limit(1)
    domain_results = list(domain_query.stream())

    if domain_results:
        role_data = domain_results[0].to_dict()
        role = UserRole(role_data["role"])
        _role_cache[email] = (role, now)
        return role

    # 3. Default to BLOCKED (no access)
    role = UserRole.BLOCKED
    _role_cache[email] = (role, now)
    return role


async def get_current_user(request: Request) -> UserInfo:
    """
    Extract and validate current user from IAP headers.

    Supports "Act As" for admins via X-Act-As header.

    This is the main dependency for protected endpoints.
    """
    user_info = await get_iap_user_info(request)

    # Check for "Act As" header (admin only)
    act_as_email = request.headers.get("X-Act-As")

    if act_as_email:
        # Verify the actual user is an admin
        actual_role = await get_user_role(user_info["email"])
        if actual_role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can use 'Act As' functionality",
            )

        # Act as the specified user
        target_email = act_as_email.lower()
        target_role = await get_user_role(target_email)

        return UserInfo(
            email=target_email,
            name=target_email.split("@")[0].replace(".", " ").title(),
            role=target_role,
            picture=None,  # No picture when acting as
        )

    # Normal mode - return actual user
    role = await get_user_role(user_info["email"])

    return UserInfo(
        email=user_info["email"],
        name=user_info["name"],
        role=role,
        picture=user_info["picture"],
    )


def require_role(*allowed_roles: UserRole):
    """
    Decorator to require specific roles for an endpoint.

    Usage:
        @router.get("/admin-only")
        @require_role(UserRole.ADMIN)
        async def admin_endpoint(user: UserInfo = Depends(get_current_user)):
            ...

    Args:
        *allowed_roles: One or more UserRole values that are allowed
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs (injected by FastAPI Depends)
            user = kwargs.get("user")
            if not user or not isinstance(user, UserInfo):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Explicitly block users with BLOCKED role
            if user.role == UserRole.BLOCKED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. Your account has not been granted access to this application. Please contact an administrator.",
                )

            if user.role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{user.role.value}' not authorized. Required: {[r.value for r in allowed_roles]}",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def invalidate_role_cache(email: str | None = None):
    """
    Invalidate role cache for a specific user or all users.

    Args:
        email: User email to invalidate, or None to clear entire cache
    """
    if email:
        _role_cache.pop(email.lower(), None)
    else:
        _role_cache.clear()
