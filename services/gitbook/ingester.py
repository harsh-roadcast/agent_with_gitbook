"""GitBook page discovery and fetching."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from bs4 import BeautifulSoup

from .crawler import GitBookCrawler
from .html_parser import GitBookHTMLParser
from .http_utils import HTTPClient

logger = logging.getLogger(__name__)


class GitBookIngester:
    """Discovers and fetches GitBook pages."""

    MANIFEST_PATHS = ["-/manifest.json", "_/manifest.json", "manifest.json"]

    def __init__(
        self,
        base_url: str,
        auth_token: Optional[str] = None,
        timeout: int = 30,
        allowed_path_prefixes: Optional[List[str]] = None,
    ):
        """
        Initialize GitBook ingester.
        
        Args:
            base_url: Base URL of the GitBook site
            auth_token: Optional authentication token
            timeout: Request timeout in seconds
            allowed_path_prefixes: Path prefixes for crawler
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.allowed_path_prefixes = allowed_path_prefixes or ["/"]
        
        self.parser = GitBookHTMLParser()
        self.http_client = HTTPClient(
            user_agent="DSPy-GitBook-Ingestor/1.0",
            accept_header="application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            auth_token=auth_token,
        )
        
        self._crawler: Optional[GitBookCrawler] = None
        self._auth_token = auth_token

    def discover_pages(self, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Discover all GitBook pages using manifest → sitemap → crawler fallback.
        
        Args:
            max_pages: Optional limit on number of pages to discover
            
        Returns:
            List of page metadata dictionaries
        """
        # Try manifest first
        manifest = self._fetch_manifest()
        pages = self._extract_manifest_pages(manifest) if manifest else []

        # Fallback to sitemap
        if not pages:
            logger.warning("Manifest parsing failed, falling back to sitemap for %s", self.base_url)
            pages = self._extract_sitemap_pages()

        # Fallback to crawler
        if not pages:
            logger.warning("Sitemap parsing failed, falling back to crawler for %s", self.base_url)
            pages = self._crawl_pages()

        # Deduplicate and limit
        unique_pages = {page["url"]: page for page in pages}
        discovered = list(unique_pages.values())
        
        if max_pages and len(discovered) > max_pages:
            discovered = discovered[:max_pages]
        
        logger.info("Discovered %s unique GitBook pages", len(discovered))
        return discovered

    def fetch_page_content(self, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch and parse a single GitBook page.
        
        Args:
            page: Page metadata dictionary
            
        Returns:
            Document dictionary with full content or None if fetch failed
        """
        url = page["url"]
        response = self.http_client.get(url, self.timeout)
        
        if not response:
            logger.error("Failed to fetch GitBook page %s", url)
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        main = soup.find("main") or soup
        
        # Remove unwanted tags
        for tag in main.find_all(["script", "style", "noscript"]):
            tag.decompose()

        # Extract content
        text_chunks = [
            line.strip() 
            for line in main.get_text("\n").splitlines() 
            if line.strip()
        ]
        page_text = "\n".join(text_chunks)
        
        headings = [
            heading.get_text(" ", strip=True)
            for heading in main.find_all(["h1", "h2", "h3", "h4"])
        ]
        
        title = page.get("title") or (
            soup.title.string.strip() if soup.title and soup.title.string else url
        )
        slug = page.get("slug") or self.parser.slugify(page.get("path") or title)
        
        word_count = len(page_text.split()) if page_text else 0
        reading_time = round(word_count / 200, 2) if word_count else 0.0

        return {
            "id": page.get("id") or slug,
            "title": title,
            "slug": slug,
            "url": url,
            "path": page.get("path") or slug,
            "headings": headings,
            "text": page_text,
            "excerpt": page_text[:500],
            "source": "gitbook",
            "space": self._get_space_name(),
            "last_fetched_at": datetime.now(timezone.utc).isoformat(),
            "word_count": word_count,
            "reading_time_minutes": reading_time,
        }

    def _fetch_manifest(self) -> Optional[Dict[str, Any]]:
        """Fetch GitBook manifest.json."""
        for raw_path in self.MANIFEST_PATHS:
            manifest_url = f"{self.base_url}/{raw_path}"
            manifest = self.http_client.get_json(manifest_url, self.timeout)
            
            if manifest:
                logger.info("Fetched GitBook manifest from %s", manifest_url)
                return manifest
        
        return None

    def _extract_manifest_pages(self, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract pages from manifest structure."""
        if not manifest:
            return []

        path_candidates = (
            manifest.get("pages") 
            or manifest.get("pageMap") 
            or manifest.get("articles")
        )
        
        nodes: List[Dict[str, Any]] = []
        
        if isinstance(path_candidates, list):
            nodes = path_candidates
        elif isinstance(path_candidates, dict):
            nodes = list(path_candidates.values())

        pages: List[Dict[str, Any]] = []

        def walk(items: List[Dict[str, Any]]) -> None:
            for item in items:
                if not isinstance(item, dict):
                    continue
                
                path = item.get("path") or item.get("url") or item.get("slug")
                if not path:
                    continue
                
                title = item.get("title") or item.get("name") or "Untitled"
                slug = item.get("slug") or self.parser.slugify(path)
                url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
                
                pages.append({
                    "id": item.get("id") or item.get("pageId") or slug,
                    "title": title,
                    "slug": slug,
                    "url": url,
                    "path": path,
                })
                
                children = item.get("children") or item.get("items") or []
                if isinstance(children, list) and children:
                    walk(children)

        if nodes:
            walk(nodes)

        logger.info("Extracted %s pages from GitBook manifest", len(pages))
        return pages

    def _extract_sitemap_pages(self) -> List[Dict[str, Any]]:
        """Extract pages from sitemap.xml."""
        sitemap_url = f"{self.base_url}/sitemap.xml"
        pages = self._parse_sitemap(sitemap_url, visited=set())
        
        if not pages:
            logger.warning("Recursive sitemap parsing returned zero pages")
        
        logger.info("Extracted %s pages from sitemap", len(pages))
        return pages

    def _parse_sitemap(self, sitemap_url: str, visited: Set[str]) -> List[Dict[str, Any]]:
        """Recursively parse sitemap XML."""
        if sitemap_url in visited:
            return []
        
        visited.add(sitemap_url)

        response = self.http_client.get(sitemap_url, self.timeout)
        if not response:
            logger.warning("Sitemap fetch failed for %s", sitemap_url)
            return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            logger.error("Failed to parse sitemap %s: %s", sitemap_url, exc)
            return []

        # Detect namespace
        namespace = self._extract_xml_namespace(root)
        loc_tag = f"{{{namespace}}}loc" if namespace else "loc"
        url_tag = f"{{{namespace}}}url" if namespace else "url"
        sitemap_tag = f"{{{namespace}}}sitemap" if namespace else "sitemap"

        pages: List[Dict[str, Any]] = []

        # Check for nested sitemaps
        sitemap_nodes = list(root.iter(sitemap_tag))
        if sitemap_nodes:
            for node in sitemap_nodes:
                loc = node.find(loc_tag)
                if loc and loc.text:
                    nested_url = loc.text.strip()
                    if nested_url.startswith("http"):
                        pages.extend(self._parse_sitemap(nested_url, visited))
            return pages

        # Parse URL entries
        for url_node in root.iter(url_tag):
            loc = url_node.find(loc_tag)
            if not loc or not loc.text:
                continue
            
            url = loc.text.strip()
            
            if not url.startswith(self.base_url):
                continue
            
            if url.endswith(".xml"):
                pages.extend(self._parse_sitemap(url, visited))
                continue
            
            path = url.replace(self.base_url, "").lstrip("/") or "/"
            slug = self.parser.slugify(path)
            title = path.replace("-", " ").title() or "Untitled"
            
            pages.append({
                "id": slug,
                "title": title,
                "slug": slug,
                "url": url,
                "path": path,
            })

        return pages

    def _crawl_pages(self) -> List[Dict[str, Any]]:
        """Use GitBookCrawler to discover pages."""
        if self._crawler is None:
            self._crawler = GitBookCrawler(
                base_url=self.base_url,
                allowed_path_prefixes=self.allowed_path_prefixes,
                auth_token=self._auth_token,
                timeout=self.timeout,
            )
        
        documents = self._crawler.crawl(start_path="/", max_pages=200)
        
        pages = []
        for doc in documents:
            slug = self.parser.slugify(doc.get("path") or doc.get("title") or doc["url"])
            pages.append({
                "id": slug,
                "title": doc.get("title", "Untitled"),
                "slug": slug,
                "url": doc["url"],
                "path": doc.get("path", "/"),
            })
        
        return pages

    def _get_space_name(self) -> str:
        """Extract space name from base URL."""
        return self.base_url.rstrip("/").split("/")[-1] or "gitbook-space"

    @staticmethod
    def _extract_xml_namespace(root: ET.Element) -> str:
        """Extract XML namespace from root element."""
        if root.tag.startswith("{"):
            return root.tag.split("}")[0].strip("{")
        return ""

    def close(self) -> None:
        """Close HTTP client resources."""
        self.http_client.close()
