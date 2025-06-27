"""Authentication utilities for JWT token handling."""
import logging
from datetime import datetime, timezone
from functools import wraps
from typing import Dict, Any

import jwt
from jwt.exceptions import InvalidSignatureError, ExpiredSignatureError, InvalidTokenError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import config_manager
from core.exceptions import DSPyAgentException

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme for FastAPI
security = HTTPBearer()


class AuthenticationError(DSPyAgentException):
    """Raised when authentication fails."""
    pass


class JWTAuthenticator:
    """JWT token authenticator."""

    def __init__(self):
        """Initialize with configuration."""
        self.config = config_manager.config
        self.secret_key = self.config.auth.jwt_secret_key
        self.algorithm = self.config.auth.jwt_algorithm

        if not self.secret_key:
            logger.warning("JWT_SECRET_KEY not configured - authentication will fail")

    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload containing user information

        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            # Decode the JWT token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True}  # Verify expiration
            )

            # Validate required fields
            if 'user_id' not in payload:
                raise AuthenticationError("Token missing user_id")

            # Check if token is expired (additional check)
            exp = payload.get('exp')
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                raise AuthenticationError("Token has expired")

            logger.debug(f"Successfully decoded token for user: {payload.get('user_id')}")
            return payload

        except ExpiredSignatureError:
            logger.warning("JWT token has expired")
            raise AuthenticationError("Token has expired")
        except InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            raise AuthenticationError("Invalid token")
        except Exception as e:
            logger.error(f"Error decoding JWT token: {e}")
            raise AuthenticationError("Authentication failed")

    def extract_user_id(self, token: str) -> str:
        """
        Extract user ID from JWT token.

        Args:
            token: JWT token string

        Returns:
            User ID string

        Raises:
            AuthenticationError: If token is invalid or user_id not found
        """
        payload = self.decode_token(token)
        user_id = payload.get('user_id')

        if not user_id:
            raise AuthenticationError("User ID not found in token")

        return str(user_id)

    def get_user_info(self, token: str) -> Dict[str, Any]:
        """
        Get user information from JWT token.

        Args:
            token: JWT token string

        Returns:
            Dictionary containing user information
        """
        payload = self.decode_token(token)

        # Extract common user fields
        user_info = {
            'user_id': payload.get('user_id'),
            'username': payload.get('username', payload.get('sub')),
            'email': payload.get('email'),
            'roles': payload.get('roles', []),
            'permissions': payload.get('permissions', []),
            'issued_at': payload.get('iat'),
            'expires_at': payload.get('exp')
        }

        # Remove None values
        user_info = {k: v for k, v in user_info.items() if v is not None}

        return user_info


# Global authenticator instance
authenticator = JWTAuthenticator()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user.

    Args:
        credentials: HTTP authorization credentials from FastAPI

    Returns:
        User information dictionary

    Raises:
        HTTPException: If authentication fails
    """
    try:
        token = credentials.credentials
        user_info = authenticator.get_user_info(token)
        return user_info
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    FastAPI dependency to get current user ID.

    Args:
        credentials: HTTP authorization credentials from FastAPI

    Returns:
        User ID string

    Raises:
        HTTPException: If authentication fails
    """
    try:
        token = credentials.credentials
        user_id = authenticator.extract_user_id(token)
        return user_id
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_auth(func):
    """
    Decorator to require authentication for a function.

    Usage:
        @require_auth
        def my_function(user_info: dict, ...):
            # user_info contains decoded JWT data
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract token from kwargs if present
        token = kwargs.pop('token', None)
        if not token:
            raise AuthenticationError("No authentication token provided")

        try:
            user_info = authenticator.get_user_info(token)
            return await func(user_info=user_info, *args, **kwargs)
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Error in auth wrapper: {e}")
            raise AuthenticationError("Authentication failed")

    return wrapper


def optional_auth(func):
    """
    Decorator for optional authentication.

    Usage:
        @optional_auth
        def my_function(user_info: dict = None, ...):
            # user_info is None if no token, or contains user data if authenticated
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        token = kwargs.pop('token', None)
        user_info = None

        if token:
            try:
                user_info = authenticator.get_user_info(token)
            except AuthenticationError:
                # For optional auth, we don't raise errors
                pass

        return await func(user_info=user_info, *args, **kwargs)

    return wrapper

import jwt
from datetime import datetime, timedelta, timezone

SECRET_KEY = "your-super-secret-jwt-key-here-change-this-in-production"
ALGORITHM = "HS256"

payload = {
    "user_id": "12345",
    "username": "johndoe",
    "email": "john@example.com",
    "roles": ["admin"],
    "permissions": ["read", "write"],
    "iat": datetime.now(tz=timezone.utc).timestamp(),
    "exp": (datetime.now(tz=timezone.utc) + timedelta(hours=1)).timestamp()
}

token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
print(token)
