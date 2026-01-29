"""Simplified authentication utilities for JWT token handling."""
import logging
from typing import Dict, Any

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from util.context import set_user_info
from modules.models import authenticator

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme for FastAPI
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """FastAPI dependency to get current authenticated user."""
    token = credentials.credentials
    user_info = authenticator.validate_token(token)

    # Store user info in context for access throughout the request
    set_user_info(user_info)

    return user_info

def generate_startup_token() -> str:
    """Generate a token on startup and return it."""
    token = authenticator.create_token(user_id="1", username="137")
    print(f"\n{'='*60}")
    print(f"🔑 AUTHENTICATION TOKEN (Valid for 24 hours)")
    print(f"{'='*60}")
    print(f"Bearer {token}")
    print(f"{'='*60}")
    print(f"Use this token in Authorization header: Bearer {token}")
    print(f"{'='*60}\n")
    return token
