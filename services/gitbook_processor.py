"""GitBook ingestion and search utilities."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from elasticsearch import NotFoundError

from services.bulk_index_service import create_index_if_not_exists, bulk_index_documents
from services.models import QueryResult, QueryErrorException
from services.search_service import (
    es_client,
    execute_query,
    execute_vector_query,
    convert_vector_results_to_markdown,
    generate_embedding,
)

logger = logging.getLogger(__name__)

DEFAULT_GITBOOK_URL = os.getenv("GITBOOK_SPACE_URL", "https://roadcast.gitbook.io/roadcast-docs")
DEFAULT_GITBOOK_INDEX = os.getenv("GITBOOK_INDEX_NAME", "gitbook_docs")
DEFAULT_MAX_PAGES = int(os.getenv("GITBOOK_MAX_PAGES", "150"))
DEFAULT_AUTH_TOKEN = os.getenv("GITBOOK_AUTH_TOKEN")
DEFAULT_CHUNK_SIZE = int(os.getenv("GITBOOK_CHUNK_SIZE", "1000"))
SENTENCE_TRANSFORMER_DIM = 384  # all-MiniLM-L6-v2 output dimension


@dataclass
class GitBookProcessorConfig:
    """Configuration object for the GitBook processor."""

    base_url: str = DEFAULT_GITBOOK_URL
    index_name: str = DEFAULT_GITBOOK_INDEX
    default_max_pages: int = DEFAULT_MAX_PAGES
    request_timeout: int = 15
    auth_token: Optional[str] = DEFAULT_AUTH_TOKEN

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.space = self.base_url.split("/")[-1] or "gitbook-space"


class GitBookProcessorService:
    """High level service that ingests GitBook content into Elasticsearch."""

    def __init__(self, config: Optional[GitBookProcessorConfig] = None) -> None:
        self.config = config or GitBookProcessorConfig()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DSPy-GitBook-Ingestor/1.0",
            "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })
        if self.config.auth_token:
            self.session.headers["Authorization"] = f"Bearer {self.config.auth_token}"
        self.chunk_size = DEFAULT_CHUNK_SIZE

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------
    def ingest_space(self, max_pages: Optional[int] = None, force_reindex: bool = False) -> Dict[str, Any]:
        """Fetch pages from GitBook and index them into Elasticsearch."""
        start_time = time.time()
        collection = self.collect_documents(max_pages=max_pages)
        documents = collection["documents"]
        pages_discovered = collection["pages_discovered"]
        pages_processed = collection["pages_processed"]
        chunks_generated = collection["chunks_generated"]

        logger.info(
            "Preparing to index %s GitBook chunks produced from %s pages",
            len(documents),
            pages_processed,
        )

        if force_reindex and es_client.indices.exists(index=self.config.index_name):
            logger.warning("Force reindex requested. Deleting index '%s'", self.config.index_name)
            es_client.indices.delete(index=self.config.index_name)

        create_index_if_not_exists(
            index_name=self.config.index_name,
            mapping=self._index_mapping()
        )

        indexing_result = bulk_index_documents(
            self.config.index_name,
            documents,
            max_docs=len(documents) or 1
        )
        elapsed = round(time.time() - start_time, 2)

        return {
            "success": True,
            "space": self.config.space,
            "index_name": self.config.index_name,
            "documents_indexed": indexing_result.get("indexed_count", 0),
            "failed_documents": indexing_result.get("failed_count", 0),
            "pages_discovered": pages_discovered,
            "pages_ingested": pages_processed,
            "chunks_indexed": chunks_generated,
            "duration_seconds": elapsed
        }

    def collect_documents(self, max_pages: Optional[int] = None) -> Dict[str, Any]:
        """Collect GitBook pages and convert them into document payloads."""
        max_pages = max_pages or self.config.default_max_pages
        pages = self._build_page_index()
        if not pages:
            raise RuntimeError("Unable to discover any GitBook pages to ingest")

        documents: List[Dict[str, Any]] = []
        pages_processed = 0

        for page in pages:
            if max_pages and pages_processed >= max_pages:
                break

            document = self._fetch_page_document(page)
            if not document:
                continue

            chunk_documents = self.prepare_document_chunks(document)
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
            "chunks_generated": len(documents)
        }

    def search_documents(self, query: str, limit: int = 5, use_vector: bool = True) -> QueryResult:
        """Execute a semantic-first search across GitBook documents."""
        if not query or not query.strip():
            raise ValueError("Query must not be empty")

        size = min(max(limit, 1), 25)

        if use_vector:
            try:
                vector_payload = {
                    "query_text": query,
                    "index": self.config.index_name,
                    "size": size,
                    "_source": self._vector_source_fields(),
                }
                vector_result = execute_vector_query(vector_payload)
                documents = vector_result.result
                if documents:
                    markdown = convert_vector_results_to_markdown(
                        documents,
                        f"Vector results from {self.config.index_name}"
                    )
                    return QueryResult(
                        success=True,
                        result=documents,
                        total_count=len(documents),
                        query_type="vector",
                        markdown_content=markdown,
                    )
            except QueryErrorException as exc:
                logger.warning(
                    "Vector search failed for query '%s': %s. Falling back to keyword search.",
                    query,
                    exc.query_error.error,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "Unexpected vector search error for query '%s': %s", query, exc, exc_info=True
                )

        body = {
            "size": size,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "headings^2", "text"],
                    "type": "best_fields"
                }
            },
            "highlight": {
                "fields": {
                    "text": {"fragment_size": 120, "number_of_fragments": 3}
                }
            }
        }

        try:
            return execute_query(body, self.config.index_name)
        except NotFoundError as exc:  # pragma: no cover - depends on ES state
            logger.error("GitBook index '%s' missing: %s", self.config.index_name, exc)
            raise

    # ------------------------------------------------------------------
    # Page discovery helpers
    # ------------------------------------------------------------------
    def _build_page_index(self) -> List[Dict[str, Any]]:
        manifest = self._fetch_manifest()
        pages = self._extract_manifest_pages(manifest) if manifest else []

        if not pages:
            logger.warning("Manifest parsing failed, falling back to sitemap for %s", self.config.base_url)
            pages = self._extract_sitemap_pages()

        unique_pages = {}
        for page in pages:
            unique_pages[page["url"]] = page

        logger.info("Discovered %s unique GitBook pages", len(unique_pages))
        return list(unique_pages.values())

    def _fetch_manifest(self) -> Optional[Dict[str, Any]]:
        manifest_paths = ["-/manifest.json", "_/manifest.json", "manifest.json"]
        for raw_path in manifest_paths:
            manifest_url = f"{self.config.base_url}/{raw_path}"
            try:
                response = self.session.get(manifest_url, timeout=self.config.request_timeout)
                if response.status_code == 200:
                    logger.info("Fetched GitBook manifest from %s", manifest_url)
                    return response.json()
            except requests.RequestException as exc:
                logger.debug("Manifest fetch failed for %s: %s", manifest_url, exc)
        return None

    def _extract_manifest_pages(self, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not manifest:
            return []

        path_candidates = manifest.get("pages") or manifest.get("pageMap") or manifest.get("articles")
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
                slug = item.get("slug") or self._slugify(path)
                url = path if path.startswith("http") else f"{self.config.base_url}/{path.lstrip('/')}"
                pages.append({
                    "id": item.get("id") or item.get("pageId") or slug,
                    "title": title,
                    "slug": slug,
                    "url": url,
                    "path": path
                })
                children = item.get("children") or item.get("items") or []
                if isinstance(children, list) and children:
                    walk(children)

        if nodes:
            walk(nodes)

        logger.info("Extracted %s pages from GitBook manifest", len(pages))
        return pages

    def _extract_sitemap_pages(self) -> List[Dict[str, Any]]:
        sitemap_url = f"{self.config.base_url}/sitemap.xml"
        pages = self._parse_sitemap(sitemap_url, visited=set())
        if not pages:
            logger.warning("Recursive sitemap parsing returned zero pages, falling back to flat parser")
            pages = self._parse_flat_sitemap(sitemap_url)
        logger.info("Extracted %s pages from sitemap", len(pages))
        return pages

    def _parse_sitemap(self, sitemap_url: str, visited: set[str]) -> List[Dict[str, Any]]:
        if sitemap_url in visited:
            return []
        visited.add(sitemap_url)

        try:
            response = self.session.get(sitemap_url, timeout=self.config.request_timeout)
            if response.status_code != 200:
                logger.warning("Sitemap fetch failed for %s with status %s", sitemap_url, response.status_code)
                return []

            root = ET.fromstring(response.content)
        except (requests.RequestException, ET.ParseError) as exc:
            logger.error("Failed to parse sitemap %s: %s", sitemap_url, exc)
            return []

        namespace = ""
        if root.tag.startswith("{"):
            namespace = root.tag.split("}")[0].strip("{")
        loc_tag = f"{{{namespace}}}loc" if namespace else "loc"
        url_tag = f"{{{namespace}}}url" if namespace else "url"
        sitemap_tag = f"{{{namespace}}}sitemap" if namespace else "sitemap"

        pages: List[Dict[str, Any]] = []

        # Handle sitemap index files that point to more sitemaps
        sitemap_nodes = list(root.iter(sitemap_tag))
        if sitemap_nodes:
            for node in sitemap_nodes:
                loc = node.find(loc_tag)
                if not loc or not loc.text:
                    continue
                nested_url = loc.text.strip()
                if not nested_url.startswith("http"):
                    continue
                pages.extend(self._parse_sitemap(nested_url, visited))
            return pages

        # Handle actual URL sets
        for url_node in root.iter(url_tag):
            loc = url_node.find(loc_tag)
            if not loc or not loc.text:
                continue
            url = loc.text.strip()
            if not url.startswith(self.config.base_url):
                continue
            if url.endswith(".xml"):
                pages.extend(self._parse_sitemap(url, visited))
                continue
            path = url.replace(self.config.base_url, "").lstrip("/") or "/"
            slug = self._slugify(path)
            title = path.replace("-", " ").title() or "Untitled"
            pages.append({
                "id": slug,
                "title": title,
                "slug": slug,
                "url": url,
                "path": path
            })

        return pages

    def _parse_flat_sitemap(self, sitemap_url: str) -> List[Dict[str, Any]]:
        try:
            response = self.session.get(sitemap_url, timeout=self.config.request_timeout)
            if response.status_code != 200:
                logger.warning("Flat sitemap fetch failed for %s with status %s", sitemap_url, response.status_code)
                return []

            root = ET.fromstring(response.content)
        except (requests.RequestException, ET.ParseError) as exc:
            logger.error("Failed to parse flat sitemap %s: %s", sitemap_url, exc)
            return []

        namespace = ""
        if root.tag.startswith("{"):
            namespace = root.tag.split("}")[0].strip("{")
        loc_tag = f"{{{namespace}}}loc" if namespace else "loc"

        pages: List[Dict[str, Any]] = []
        for loc in root.iter(loc_tag):
            if not loc.text:
                continue
            url = loc.text.strip()
            if not url.startswith(self.config.base_url):
                continue
            path = url.replace(self.config.base_url, "").lstrip("/") or "/"
            slug = self._slugify(path)
            pages.append({
                "id": slug,
                "title": path.replace("-", " ").title(),
                "slug": slug,
                "url": url,
                "path": path
            })

        return pages

    # ------------------------------------------------------------------
    # Page parsing helpers
    # ------------------------------------------------------------------
    def _fetch_page_document(self, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url = page["url"]
        try:
            response = self.session.get(url, timeout=self.config.request_timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Failed to fetch GitBook page %s: %s", url, exc)
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        main = soup.find("main") or soup
        for tag in main.find_all(["script", "style", "noscript"]):
            tag.decompose()

        text_chunks = [line.strip() for line in main.get_text("\n").splitlines() if line.strip()]
        page_text = "\n".join(text_chunks)
        headings = [heading.get_text(" ", strip=True) for heading in main.find_all(["h1", "h2", "h3", "h4"])]
        title = page.get("title") or (soup.title.string.strip() if soup.title and soup.title.string else url)
        slug = page.get("slug") or self._slugify(page.get("path") or title)
        word_count = len(page_text.split()) if page_text else 0
        reading_time = round(word_count / 200, 2) if word_count else 0.0

        document = {
            "id": page.get("id") or slug,
            "title": title,
            "slug": slug,
            "url": url,
            "path": page.get("path") or slug,
            "headings": headings,
            "text": page_text,
            "excerpt": page_text[:500],
            "source": "gitbook",
            "space": self.config.space,
            "last_fetched_at": datetime.now(timezone.utc).isoformat(),
            "word_count": word_count,
            "reading_time_minutes": reading_time
        }

        normalized = self._normalize_document_payload(document)
        logger.debug(
            "Prepared GitBook document payload: %s",
            json.dumps({k: normalized[k] for k in ("id", "title", "url")})
        )
        return normalized

    # ------------------------------------------------------------------
    # Document transformation helpers
    # ------------------------------------------------------------------
    def prepare_document_chunks(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Normalize a GitBook document and emit chunk-level payloads with embeddings."""
        normalized = self._normalize_document_payload(document)
        return self._build_chunk_documents(normalized)

    def _normalize_document_payload(self, document: Dict[str, Any]) -> Dict[str, Any]:
        text = (document.get("text") or "").strip()
        path = document.get("path") or document.get("slug") or document.get("url") or "gitbook"
        title = document.get("title") or "Untitled"
        slug = document.get("slug") or self._slugify(path or title)
        word_count = len(text.split()) if text else document.get("word_count", 0)
        reading_time = round(word_count / 200, 2) if word_count else document.get("reading_time_minutes", 0.0)

        return {
            "id": document.get("id") or slug,
            "title": title,
            "slug": slug,
            "url": document.get("url") or "",
            "path": path,
            "headings": document.get("headings") or [],
            "text": text,
            "excerpt": (document.get("excerpt") or text[:500]) if text else "",
            "source": document.get("source") or "gitbook",
            "space": document.get("space") or self.config.space,
            "last_fetched_at": document.get("last_fetched_at") or datetime.now(timezone.utc).isoformat(),
            "word_count": word_count,
            "reading_time_minutes": reading_time,
        }

    def _build_chunk_documents(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
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
            except Exception as exc:  # pragma: no cover - defensive logging
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
        if not text:
            return []

        words = text.split()
        chunks: List[str] = []
        for start in range(0, len(words), self.chunk_size):
            chunk_words = words[start:start + self.chunk_size]
            chunk = " ".join(chunk_words).strip()
            if len(chunk) > 20:
                chunks.append(chunk)
        return chunks

    def _vector_source_fields(self) -> List[str]:
        return [
            "title",
            "slug",
            "url",
            "path",
            "headings",
            "text",
            "excerpt",
            "source",
            "space",
            "last_fetched_at",
            "word_count",
            "reading_time_minutes",
            "page_id",
            "chunk_id",
            "chunk_count",
        ]

    def index_mapping(self) -> Dict[str, Any]:
        return self._index_mapping()

    def _index_mapping(self) -> Dict[str, Any]:
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
                    "dims": SENTENCE_TRANSFORMER_DIM,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        }

    @staticmethod
    def _slugify(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return cleaned or "root"


gitbook_processor = GitBookProcessorService()
"""Singleton GitBook processor used across the application."""
