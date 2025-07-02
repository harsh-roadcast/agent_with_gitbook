"""Simplified authentication utilities for JWT token handling."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import config_manager

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme for FastAPI
security = HTTPBearer()

class JWTAuthenticator:
    """JWT token authenticator."""

    def __init__(self):
        """Initialize with configuration."""
        self.config = config_manager.config
        self.secret_key = self.config.auth.jwt_secret_key or "dev-secret-key-change-in-production"
        self.algorithm = self.config.auth.jwt_algorithm

    def create_token(self, user_id: str = "admin", username: str = "admin") -> str:
        """Create a JWT access token."""
        expire = datetime.now(timezone.utc) + timedelta(days=365)  # 24 hour token

        payload = {
            "user_id": user_id,
            "username": username,
            "sub": username,
            "exp": expire,
            "iat": datetime.now(timezone.utc)
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate and decode JWT token."""
        payload = jwt.decode(
            token,
            self.secret_key,
            algorithms=[self.algorithm],
            options={"verify_exp": True}
        )

        return {
            'user_id': payload.get('user_id'),
            'username': payload.get('username', payload.get('sub')),
            'issued_at': payload.get('iat'),
            'expires_at': payload.get('exp')
        }

# Global authenticator instance
authenticator = JWTAuthenticator()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """FastAPI dependency to get current authenticated user."""
    token = credentials.credentials
    user_info = authenticator.validate_token(token)
    return user_info

def generate_startup_token() -> str:
    """Generate a token on startup and return it."""
    token = authenticator.create_token()
    print(f"\n{'='*60}")
    print(f"🔑 AUTHENTICATION TOKEN (Valid for 24 hours)")
    print(f"{'='*60}")
    print(f"Bearer {token}")
    print(f"{'='*60}")
    print(f"Use this token in Authorization header: Bearer {token}")
    print(f"{'='*60}\n")
    return token
