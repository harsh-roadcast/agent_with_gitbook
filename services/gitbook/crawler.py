"""GitBook crawling service."""
from __future__ import annotations

import logging
from collections import deque
from typing import Dict, List, Set

from .html_parser import GitBookHTMLParser
from .http_utils import HTTPClient

logger = logging.getLogger(__name__)


class GitBookCrawler:
    """Handles breadth-first crawling of GitBook sites."""

    def __init__(
        self,
        base_url: str,
        allowed_path_prefixes: List[str],
        auth_token: str | None = None,
        timeout: int = 30,
    ):
        """
        Initialize GitBook crawler.
        
        Args:
            base_url: Base URL of the GitBook site
            allowed_path_prefixes: List of allowed path prefixes to crawl
            auth_token: Optional authentication token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.allowed_path_prefixes = allowed_path_prefixes
        self.timeout = timeout
        
        self.parser = GitBookHTMLParser()
        self.http_client = HTTPClient(
            user_agent="DSPy-GitBook-Crawler/1.0",
            accept_header="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            auth_token=auth_token,
        )

    def crawl(self, start_path: str = "/", max_pages: int = 100) -> List[Dict[str, str]]:
        """
        Crawl GitBook site starting from a given path.
        
        Args:
            start_path: Starting path for crawl
            max_pages: Maximum number of pages to crawl
            
        Returns:
            List of parsed document dictionaries
        """
        start_url = self.parser.normalize_url(start_path, self.base_url)
        
        if not start_url:
            logger.warning(
                "Start path '%s' is not accessible. Falling back to base URL %s",
                start_path,
                self.base_url,
            )
            start_url = self.base_url

        queue = deque([start_url])
        visited: Set[str] = set()
        documents: List[Dict[str, str]] = []

        while queue and len(documents) < max_pages:
            current_url = queue.popleft()
            
            if current_url in visited:
                continue
            
            visited.add(current_url)

            if not self._is_allowed(current_url):
                logger.debug("Skipping disallowed URL %s", current_url)
                continue

            logger.info("Fetching GitBook page %s", current_url)
            response = self.http_client.get(current_url, self.timeout)
            
            if not response:
                continue

            # Parse document content
            document = self.parser.parse_content(current_url, response.text, self.base_url)
            documents.append(document)

            # Extract and queue new links
            links = self.parser.extract_links(response.text, self.base_url, current_url)
            for link in links:
                if link not in visited and self._is_allowed(link):
                    queue.append(link)

        logger.info(
            "Crawler finished. Visited %s pages, stored %s documents",
            len(visited),
            len(documents),
        )
        
        return documents

    def _is_allowed(self, url: str) -> bool:
        """Check if URL is allowed based on path prefixes."""
        path = self._url_to_path(url)
        
        if path == "/":
            return True
        
        return any(path.startswith(prefix) for prefix in self.allowed_path_prefixes)

    def _url_to_path(self, url: str) -> str:
        """Convert URL to path relative to base."""
        return self.parser._normalize_path(url, self.base_url)

    def close(self) -> None:
        """Close HTTP client resources."""
        self.http_client.close()
