"""HTML parsing utilities for GitBook documents."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urljoin, urldefrag

from bs4 import BeautifulSoup


class GitBookHTMLParser:
    """Handles HTML parsing for GitBook pages."""

    def parse_content(self, url: str, html: str, base_url: str) -> Dict[str, str]:
        """
        Parse HTML content and extract structured data.
        
        Args:
            url: The URL of the page
            html: Raw HTML content
            base_url: Base URL for path normalization
            
        Returns:
            Dictionary with title, url, path, headings, text, and crawled_at
        """
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup
        
        # Remove scripts, styles, and noscript tags
        for tag in main.find_all(["script", "style", "noscript"]):
            tag.decompose()

        # Extract text content
        text_lines = [line.strip() for line in main.get_text("\n").splitlines() if line.strip()]
        
        # Extract headings
        headings = [
            heading.get_text(" ", strip=True) 
            for heading in main.find_all(["h1", "h2", "h3", "h4"])
        ]
        
        # Extract title
        title = self._extract_title(soup, url)

        return {
            "title": title,
            "url": url,
            "path": self._normalize_path(url, base_url),
            "headings": headings,
            "text": "\n".join(text_lines),
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }

    def extract_links(self, html: str, base_url: str, current_url: str) -> List[str]:
        """
        Extract and normalize all links from HTML content.
        
        Args:
            html: Raw HTML content
            base_url: Base URL for filtering
            current_url: Current page URL for relative link resolution
            
        Returns:
            List of normalized, absolute URLs
        """
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []
        
        for anchor in soup.find_all("a", href=True):
            normalized = self.normalize_url(anchor.get("href"), base_url, current_url)
            if normalized:
                links.append(normalized)
        
        return links

    @staticmethod
    def normalize_url(href: str | None, base_url: str, reference_url: str | None = None) -> str | None:
        """
        Normalize a URL by resolving it against a base and removing fragments.
        
        Args:
            href: The href attribute value
            base_url: Base URL for domain filtering
            reference_url: Reference URL for relative link resolution
            
        Returns:
            Normalized URL or None if invalid/external
        """
        if not href or href.startswith("javascript:") or href.startswith("#"):
            return None
        
        reference = urljoin(reference_url or f"{base_url}/", href)
        reference, _ = urldefrag(reference)
        
        if not reference.startswith(base_url):
            return None
        
        return reference.rstrip("/")

    @staticmethod
    def _extract_title(soup: BeautifulSoup, fallback_url: str) -> str:
        """Extract page title with fallback."""
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        return fallback_url

    @staticmethod
    def _normalize_path(url: str, base_url: str) -> str:
        """Normalize URL to path relative to base."""
        if not url:
            return "/"
        
        path = url.replace(base_url, "")
        if not path.startswith("/"):
            path = f"/{path}"
        
        return re.sub(r"/+", "/", path)

    @staticmethod
    def slugify(value: str) -> str:
        """Convert a string to a URL-friendly slug."""
        cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return cleaned or "root"
