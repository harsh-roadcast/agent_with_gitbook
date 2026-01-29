"""HTTP utilities for GitBook services."""
from __future__ import annotations

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class HTTPClient:
    """Handles HTTP requests with error handling and retry logic."""

    def __init__(self, user_agent: str, accept_header: str, auth_token: Optional[str] = None):
        """
        Initialize HTTP client with headers.
        
        Args:
            user_agent: User-Agent header value
            accept_header: Accept header value
            auth_token: Optional authorization token
        """
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": accept_header,
        })
        
        if auth_token:
            self.session.headers["Authorization"] = f"Bearer {auth_token}"

    def get(self, url: str, timeout: int = 30) -> Optional[requests.Response]:
        """
        Safely GET a URL with error handling.
        
        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
            
        Returns:
            Response object or None if request failed
        """
        try:
            response = self.session.get(url, timeout=timeout)
            
            if response.status_code >= 400:
                logger.warning(
                    "Failed to fetch %s (status %s)", 
                    url, 
                    response.status_code
                )
                return None
            
            return response
            
        except requests.RequestException as exc:
            logger.error("Request error for %s: %s", url, exc)
            return None

    def get_json(self, url: str, timeout: int = 30) -> Optional[dict]:
        """
        Safely GET JSON from a URL.
        
        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
            
        Returns:
            Parsed JSON dict or None if request failed
        """
        response = self.get(url, timeout)
        
        if not response:
            return None
        
        try:
            return response.json()
        except ValueError as exc:
            logger.error("Failed to parse JSON from %s: %s", url, exc)
            return None

    def close(self) -> None:
        """Close the underlying session."""
        self.session.close()
