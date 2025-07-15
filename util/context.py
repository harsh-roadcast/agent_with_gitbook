"""Context utilities for storing request-level data like authorization headers."""
import contextvars
from typing import Optional, Dict, Any

# Context variables for request-level data
authorization_header: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('authorization_header', default=None)
user_info: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar('user_info', default=None)
request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('request_id', default=None)


def set_authorization_header(header: str) -> None:
    """Set the authorization header in context."""
    authorization_header.set(header)


def get_authorization_header() -> Optional[str]:
    """Get the authorization header from context."""
    return authorization_header.get()


def set_user_info(info: Dict[str, Any]) -> None:
    """Set user info in context."""
    user_info.set(info)


def get_user_info() -> Optional[Dict[str, Any]]:
    """Get user info from context."""
    return user_info.get()


def set_request_id(req_id: str) -> None:
    """Set request ID in context."""
    request_id.set(req_id)


def get_request_id() -> Optional[str]:
    """Get request ID from context."""
    return request_id.get()


def clear_context() -> None:
    """Clear all context variables."""
    authorization_header.set(None)
    user_info.set(None)
    request_id.set(None)
