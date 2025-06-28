"""Authentication routes for user login and registration."""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from services.auth_service import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["authentication"])
security = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

@router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate user and return access token."""
    user = authenticate_user(request.username, request.password)

    access_token = create_access_token(
        data={"sub": user["username"], "user_id": user["id"]}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=1800  # 30 minutes
    )

@router.post("/auth/register", response_model=Dict[str, str])
async def register(request: RegisterRequest):
    """Register a new user."""
    hashed_password = hash_password(request.password)

    # Create user record
    user_data = {
        "username": request.username,
        "email": request.email,
        "password_hash": hashed_password,
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True
    }

    logger.info(f"User {request.username} registered successfully")
    return {"message": "User registered successfully", "username": request.username}

@router.get("/auth/me", response_model=Dict[str, Any])
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user information."""
    return {
        "username": current_user.get("username"),
        "user_id": current_user.get("user_id"),
        "authenticated": True
    }
