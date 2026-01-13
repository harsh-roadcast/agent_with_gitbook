"""Simple GitBook web crawler that exports documentation pages."""
from __future__ import annotations

import logging
import os
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urldefrag

import requests
from bs4 import BeautifulSoup
import json

logger = logging.getLogger(__name__)

DEFAULT_GITBOOK_URL = os.getenv("GITBOOK_SPACE_URL", "https://roadcast.gitbook.io/roadcast-docs")
DEFAULT_ALLOWED_PREFIXES = tuple(
    prefix.strip() for prefix in os.getenv("GITBOOK_ALLOWED_PREFIXES", "/documentation").split(",") if prefix.strip()
)
DEFAULT_MAX_PAGES = int(os.getenv("GITBOOK_CRAWLER_MAX_PAGES", "200"))
DEFAULT_AUTH_TOKEN = os.getenv("GITBOOK_AUTH_TOKEN")


@dataclass
class GitBookCrawlerConfig:
    base_url: str = DEFAULT_GITBOOK_URL
    allowed_path_prefixes: Tuple[str, ...] = DEFAULT_ALLOWED_PREFIXES
    max_pages: int = DEFAULT_MAX_PAGES
    request_timeout: int = 15
    auth_token: Optional[str] = DEFAULT_AUTH_TOKEN

    def __post_init__(self) -> None:
        if not self.base_url:
            self.base_url = DEFAULT_GITBOOK_URL
        self.base_url = self.base_url.rstrip("/")
        if not self.allowed_path_prefixes:
            self.allowed_path_prefixes = ("/",)
        else:
            self.allowed_path_prefixes = tuple(prefix if prefix.startswith("/") else f"/{prefix}" for prefix in self.allowed_path_prefixes)


class GitBookCrawler:
    """Breadth-first crawler over a GitBook space."""

    def __init__(self, config: Optional[GitBookCrawlerConfig] = None) -> None:
        self.config = config or GitBookCrawlerConfig()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DSPy-GitBook-Crawler/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })
        if self.config.auth_token:
            self.session.headers["Authorization"] = f"Bearer {self.config.auth_token}"

    def crawl(self, start_path: str = "/documentation") -> List[Dict[str, str]]:
        start_url = self._normalize_url(start_path)
        if not start_url:
            logger.warning(
                "Start path '%s' is not accessible. Falling back to base URL %s",
                start_path,
                self.config.base_url,
            )
            start_url = self.config.base_url

        queue = deque([start_url])
        visited: Set[str] = set()
        documents: List[Dict[str, str]] = []

        while queue and len(documents) < self.config.max_pages:
            current_url = queue.popleft()
            if current_url in visited:
                continue
            visited.add(current_url)

            if not self._is_allowed(current_url):
                logger.debug("Skipping disallowed URL %s", current_url)
                continue

            logger.info("Fetching GitBook page %s", current_url)
            response = self._safe_get(current_url)
            if not response:
                continue

            document = self._parse_document(current_url, response.text)
            documents.append(document)

            for link in self._extract_links(current_url, response.text):
                if link not in visited and self._is_allowed(link):
                    queue.append(link)

        logger.info("Crawler finished. Visited %s pages, stored %s documents", len(visited), len(documents))
        return documents

    def _safe_get(self, url: str) -> Optional[requests.Response]:
        try:
            response = self.session.get(url, timeout=self.config.request_timeout)
            if response.status_code >= 400:
                logger.warning("Failed to fetch %s (status %s)", url, response.status_code)
                return None
            return response
        except requests.RequestException as exc:
            logger.error("Request error for %s: %s", url, exc)
            return None

    def _parse_document(self, url: str, html: str) -> Dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup
        for tag in main.find_all(["script", "style", "noscript"]):
            tag.decompose()

        text_lines = [line.strip() for line in main.get_text("\n").splitlines() if line.strip()]
        headings = [heading.get_text(" ", strip=True) for heading in main.find_all(["h1", "h2", "h3", "h4"])]
        title = (soup.title.string.strip() if soup.title and soup.title.string else url).strip()

        return {
            "title": title,
            "url": url,
            "path": self._path_for_url(url),
            "headings": headings,
            "text": "\n".join(text_lines),
            "crawled_at": datetime.now(timezone.utc).isoformat()
        }

    def _extract_links(self, base_url: str, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if not href:
                continue
            normalized = self._normalize_url(href, base_url)
            if normalized:
                links.append(normalized)
        return links

    def _normalize_url(self, href: str, base: Optional[str] = None) -> Optional[str]:
        if href.startswith("javascript:"):
            return None
        if href.startswith("#"):
            return None
        reference = urljoin(base or self.config.base_url + "/", href)
        reference, _ = urldefrag(reference)
        if not reference.startswith(self.config.base_url):
            return None
        return reference.rstrip("/")

    def _is_allowed(self, url: str) -> bool:
        path = self._path_for_url(url)
        if path == "/":
            return True
        return any(path.startswith(prefix) for prefix in self.config.allowed_path_prefixes)

    def _path_for_url(self, url: str) -> str:
        if not url:
            return "/"
        path = url.replace(self.config.base_url, "")
        if not path.startswith("/"):
            path = f"/{path}"
        return re.sub(r"/+", "/", path)


def save_documents_as_jsonl(documents: List[Dict[str, str]], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as handle:
        for doc in documents:
            payload = {**doc, "text": doc.get("text", "").strip()}
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")