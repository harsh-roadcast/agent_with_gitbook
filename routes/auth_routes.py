"""Authentication routes for JWT token handling."""
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from services.auth_service import get_current_user, authenticator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/me")
async def get_user_profile(user_info: Dict[str, Any] = Depends(get_current_user)):
    """
    Get current user profile information from JWT token.

    Returns:
        User profile information extracted from the JWT token
    """
    try:
        logger.info(f"User profile requested for user: {user_info.get('user_id')}")

        # Return user info (no sensitive data since we don't store anything)
        profile = {
            "user_id": user_info.get("user_id"),
            "username": user_info.get("username"),
            "email": user_info.get("email"),
            "roles": user_info.get("roles", []),
            "permissions": user_info.get("permissions", []),
            "token_issued_at": user_info.get("issued_at"),
            "token_expires_at": user_info.get("expires_at")
        }

        # Remove None values
        profile = {k: v for k, v in profile.items() if v is not None}

        return JSONResponse(content={
            "status": "success",
            "user": profile
        })

    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )


@router.post("/validate")
async def validate_token(user_info: Dict[str, Any] = Depends(get_current_user)):
    """
    Validate JWT token and return validation status.

    Returns:
        Token validation status and basic user info
    """
    try:
        logger.info(f"Token validation requested for user: {user_info.get('user_id')}")

        return JSONResponse(content={
            "status": "success",
            "valid": True,
            "user_id": user_info.get("user_id"),
            "username": user_info.get("username"),
            "message": "Token is valid"
        })

    except Exception as e:
        logger.error(f"Error validating token: {e}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "status": "error",
                "valid": False,
                "message": "Invalid token"
            }
        )


@router.get("/health")
async def auth_health():
    """
    Check authentication service health.

    Returns:
        Authentication service status
    """
    try:
        # Check if JWT secret is configured
        secret_configured = bool(authenticator.secret_key)

        return JSONResponse(content={
            "status": "success" if secret_configured else "warning",
            "auth_service": "running",
            "jwt_configured": secret_configured,
            "algorithm": authenticator.algorithm,
            "message": "Authentication service is healthy" if secret_configured else "JWT_SECRET_KEY not configured"
        })

    except Exception as e:
        logger.error(f"Error checking auth health: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "auth_service": "error",
                "message": str(e)
            }
        )
