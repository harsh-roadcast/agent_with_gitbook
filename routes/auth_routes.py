"""Minimal authentication routes - only token validation."""
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends

from services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["authentication"])

@router.get("/auth/me", response_model=Dict[str, Any])
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user information from token."""
    return {
        "username": current_user.get("username"),
        "user_id": current_user.get("user_id"),
        "authenticated": True,
        "expires_at": current_user.get("expires_at")
    }
