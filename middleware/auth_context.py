"""Middleware for handling authorization context and request tracking."""
import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from util.context import set_authorization_header, set_request_id, clear_context

logger = logging.getLogger(__name__)


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and store authorization header in context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and store auth context."""
        # Clear any existing context
        clear_context()

        # Generate unique request ID
        req_id = str(uuid.uuid4())
        set_request_id(req_id)

        # Extract authorization header
        auth_header = request.headers.get("authorization")
        if auth_header:
            set_authorization_header(auth_header)
            logger.debug(f"[{req_id}] Authorization header stored in context")
        else:
            logger.debug(f"[{req_id}] No authorization header found")

        # Process the request
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"[{req_id}] Error processing request: {e}")
            raise
        finally:
            # Context will be automatically cleared when the request ends
            pass
