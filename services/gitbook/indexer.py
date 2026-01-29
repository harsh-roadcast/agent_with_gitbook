"""GitBook document indexing and ingestion service."""
from __future__ import annotations

import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from bs4 import BeautifulSoup

from services.bulk_index_service import bulk_index_documents, create_index_if_not_exists
from services.search_service import generate_embedding

from .html_parser import GitBookHTMLParser
from .http_utils import HTTPClient
from .crawler import GitBookCrawler

logger = logging.getLogger(__name__)


class GitBookIndexer:
    """Handles GitBook document ingestion, chunking, and indexing."""

    MANIFEST_PATHS = ["-/manifest.json", "_/manifest.json", "manifest.json"]
    SENTENCE_TRANSFORMER_DIM = 384

    def __init__(
        self,
        base_url: str,
        chunk_size: int = 200,
        auth_token: Optional[str] = None,
        timeout: int = 30,
        allowed_path_prefixes: Optional[List[str]] = None,
    ):
        """
        Initialize GitBook indexer.
        
        Args:
            base_url: Base URL of the GitBook site
            chunk_size: Number of words per chunk
            auth_token: Optional authentication token
            timeout: Request timeout in seconds
            allowed_path_prefixes: Path prefixes for crawler fallback
        """
        self.base_url = base_url.rstrip("/")
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.allowed_path_prefixes = allowed_path_prefixes or ["/"]
        
        self.parser = GitBookHTMLParser()
        self.http_client = HTTPClient(
            user_agent="DSPy-GitBook-Ingestor/1.0",
            accept_header="application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            auth_token=auth_token,
        )
        
        # Lazy-loaded crawler for fallback
        self._crawler: Optional[GitBookCrawler] = None
        self._auth_token = auth_token

    def ingest_and_index(
        self,
        index_name: str,
        max_pages: Optional[int] = None,
        force_reindex: bool = False,
    ) -> Dict[str, Any]:
        """
        Ingest GitBook pages and index them into Elasticsearch.
        
        Args:
            index_name: Target Elasticsearch index name
            max_pages: Maximum number of pages to ingest
            force_reindex: Whether to delete and recreate the index
            
        Returns:
            Dictionary with ingestion statistics
        """
        from services.search_service import es_client
        
        start_time = time.time()

        # Collect and prepare documents
        collection = self.collect_documents(max_pages)
        documents = collection["documents"]
        pages_discovered = collection["pages_discovered"]
        pages_processed = collection["pages_processed"]
        chunks_generated = collection["chunks_generated"]

        logger.info(
            "Preparing to index %s GitBook chunks from %s pages",
            len(documents),
            pages_processed,
        )

        # Handle force reindex
        if force_reindex and es_client.indices.exists(index=index_name):
            logger.warning("Force reindex requested. Deleting index '%s'", index_name)
            es_client.indices.delete(index=index_name)

        # Create index if needed
        create_index_if_not_exists(
            index_name=index_name,
            mapping=self.get_index_mapping(),
        )

        # Bulk index documents
        indexing_result = bulk_index_documents(
            index_name,
            documents,
            max_docs=len(documents) or 1,
        )
        
        elapsed = round(time.time() - start_time, 2)

        return {
            "success": True,
            "space": self._get_space_name(),
            "index_name": index_name,
            "documents_indexed": indexing_result.get("indexed_count", 0),
            "failed_documents": indexing_result.get("failed_count", 0),
            "pages_discovered": pages_discovered,
            "pages_ingested": pages_processed,
            "chunks_indexed": chunks_generated,
            "duration_seconds": elapsed,
        }

    def collect_documents(self, max_pages: Optional[int] = None) -> Dict[str, Any]:
        """
        Collect GitBook pages and convert to chunk-level documents.
        
        Args:
            max_pages: Maximum number of pages to collect
            
        Returns:
            Dictionary with documents and statistics
        """
        pages = self._build_page_index()
        
        if not pages:
            raise RuntimeError("Unable to discover any GitBook pages to ingest")

        documents: List[Dict[str, Any]] = []
        pages_processed = 0
        limit = max_pages or len(pages)

        for page in pages:
            if pages_processed >= limit:
                break

            document = self._fetch_page_document(page)
            if not document:
                continue

            chunk_documents = self._prepare_document_chunks(document)
            if not chunk_documents:
                continue

            documents.extend(chunk_documents)
            pages_processed += 1

        if not documents:
            raise RuntimeError("GitBook ingestion produced zero documents")

        return {
            "documents": documents,
            "pages_discovered": len(pages),
            "pages_processed": pages_processed,
            "chunks_generated": len(documents),
        }

    def _build_page_index(self) -> List[Dict[str, Any]]:
        """Build index of all pages to ingest."""
        manifest = self._fetch_manifest()
        pages = self._extract_manifest_pages(manifest) if manifest else []

        if not pages:
            logger.warning(
                "Manifest parsing failed, falling back to sitemap for %s",
                self.base_url,
            )
            pages = self._extract_sitemap_pages()

        if not pages:
            logger.warning(
                "Sitemap parsing failed, falling back to crawler for %s",
                self.base_url,
            )
            pages = self._crawl_pages()

        unique_pages = {page["url"]: page for page in pages}
        logger.info("Discovered %s unique GitBook pages", len(unique_pages))
        
        return list(unique_pages.values())

    def _crawl_pages(self) -> List[Dict[str, Any]]:
        """Fallback: Use GitBookCrawler to discover pages."""
        if self._crawler is None:
            self._crawler = GitBookCrawler(
                base_url=self.base_url,
                allowed_path_prefixes=self.allowed_path_prefixes,
                auth_token=self._auth_token,
                timeout=self.timeout,
            )
        
        # Crawl and convert to page index format
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

    @staticmethod
    def _extract_xml_namespace(root: ET.Element) -> str:
        """Extract XML namespace from root element."""
        if root.tag.startswith("{"):
            return root.tag.split("}")[0].strip("{")
        return ""

    def _fetch_page_document(self, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetch and parse a single GitBook page."""
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

    def _prepare_document_chunks(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert document into chunks with embeddings."""
        text = document.get("text", "")
        if not text:
            return []

        chunks = self._chunk_text(text)
        if not chunks:
            return []

        chunk_documents: List[Dict[str, Any]] = []
        chunk_count = len(chunks)
        
        for chunk_id, chunk_text in enumerate(chunks):
            try:
                embedding = generate_embedding(chunk_text)
            except Exception as exc:
                logger.warning("Failed to embed GitBook chunk %s: %s", chunk_id, exc)
                continue

            chunk_documents.append({
                "id": f"{document['id']}_chunk_{chunk_id}",
                "page_id": document["id"],
                "chunk_id": chunk_id,
                "chunk_count": chunk_count,
                "title": document["title"],
                "slug": document["slug"],
                "url": document["url"],
                "path": document["path"],
                "headings": document.get("headings", []),
                "text": chunk_text,
                "excerpt": chunk_text[:500],
                "source": document["source"],
                "space": document["space"],
                "last_fetched_at": document["last_fetched_at"],
                "word_count": document.get("word_count", 0),
                "reading_time_minutes": document.get("reading_time_minutes", 0.0),
                "embedding": embedding,
            })

        return chunk_documents

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into word-based chunks."""
        if not text:
            return []

        words = text.split()
        chunks: List[str] = []
        
        for start in range(0, len(words), self.chunk_size):
            chunk_words = words[start : start + self.chunk_size]
            chunk = " ".join(chunk_words).strip()
            
            if len(chunk) > 20:  # Minimum chunk size
                chunks.append(chunk)
        
        return chunks

    def _get_space_name(self) -> str:
        """Extract space name from base URL."""
        return self.base_url.rstrip("/").split("/")[-1] or "gitbook-space"

    def get_index_mapping(self) -> Dict[str, Any]:
        """Return Elasticsearch index mapping."""
        return {
            "properties": {
                "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "slug": {"type": "keyword"},
                "url": {"type": "keyword"},
                "path": {"type": "keyword"},
                "headings": {"type": "keyword"},
                "text": {"type": "text"},
                "excerpt": {"type": "text"},
                "source": {"type": "keyword"},
                "space": {"type": "keyword"},
                "last_fetched_at": {"type": "date"},
                "word_count": {"type": "integer"},
                "reading_time_minutes": {"type": "float"},
                "page_id": {"type": "keyword"},
                "chunk_id": {"type": "integer"},
                "chunk_count": {"type": "integer"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": self.SENTENCE_TRANSFORMER_DIM,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        }

    @staticmethod
    def save_documents_as_jsonl(documents: List[Dict[str, str]], output_path: str) -> None:
        """Save documents to JSONL file."""
        with open(output_path, "w", encoding="utf-8") as handle:
            for doc in documents:
                payload = {**doc, "text": doc.get("text", "").strip()}
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def close(self) -> None:
        """Close HTTP client resources."""
        self.http_client.close()
