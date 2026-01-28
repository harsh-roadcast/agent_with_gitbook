"""Shared GitBook crawling, ingestion, and agent helpers."""
from __future__ import annotations

import json
import logging
import re
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Set
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urldefrag

import dspy
import requests
from bs4 import BeautifulSoup
from elasticsearch import NotFoundError

from agents.agent_config import get_agent_by_name
from core.config import config_manager
from modules.signatures import GitBookAnswerSignature
from services.bulk_index_service import bulk_index_documents, create_index_if_not_exists
from services.models import QueryErrorException, QueryResult
from services.search_service import (
    convert_vector_results_to_markdown,
    es_client,
    execute_query,
    execute_vector_query,
    generate_embedding,
)

logger = logging.getLogger(__name__)

CRAWLER_USER_AGENT = "DSPy-GitBook-Crawler/1.0"
CRAWLER_ACCEPT_HEADER = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

INGEST_USER_AGENT = "DSPy-GitBook-Ingestor/1.0"
INGEST_ACCEPT_HEADER = "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
MANIFEST_PATHS = ["-/manifest.json", "_/manifest.json", "manifest.json"]
SENTENCE_TRANSFORMER_DIM = 384

AGENT_NAME = "gitbook_rag_copilot"
LONG_FORM_KEYWORDS = (
    "detailed",
    "long",
    "longer",
    "full",
    "comprehensive",
    "in depth",
    "in-depth",
    "deep dive",
    "extensive",
    "elaborate",
    "explain in detail",
    "more detail",
    "dive deep",
)

_INGEST_SESSION: Optional[requests.Session] = None
_INGEST_SESSION_TOKEN: Optional[str] = None


# -----------------------------------------------------------------------------
# Crawling helpers
# -----------------------------------------------------------------------------

def crawl_gitbook_documents(start_path: str = "/documentation", max_pages: Optional[int] = None) -> List[Dict[str, str]]:
    """Breadth-first crawl of the configured GitBook space."""
    config = config_manager.config.gitbook
    limit = max_pages if max_pages is not None else config.max_pages
    session = _create_crawler_session(config.auth_token)

    start_url = _normalize_url(start_path, config)
    if not start_url:
        logger.warning("Start path '%s' is not accessible. Falling back to base URL %s", start_path, config.base_url)
        start_url = config.base_url

    queue = deque([start_url])
    visited: Set[str] = set()
    documents: List[Dict[str, str]] = []

    while queue and len(documents) < limit:
        current_url = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)

        if not _is_allowed(current_url, config):
            logger.debug("Skipping disallowed URL %s", current_url)
            continue

        logger.info("Fetching GitBook page %s", current_url)
        response = _safe_get(session, current_url, config.request_timeout)
        if not response:
            continue

        document = _parse_document(current_url, response.text, config)
        documents.append(document)

        for link in _extract_links(current_url, response.text, config):
            if link not in visited and _is_allowed(link, config):
                queue.append(link)

    logger.info("Crawler finished. Visited %s pages, stored %s documents", len(visited), len(documents))
    return documents


def save_documents_as_jsonl(documents: List[Dict[str, str]], output_path: str) -> None:
    """Persist crawled documents to JSONL for debugging/exports."""
    with open(output_path, "w", encoding="utf-8") as handle:
        for doc in documents:
            payload = {**doc, "text": doc.get("text", "").strip()}
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _create_crawler_session(auth_token: Optional[str]) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": CRAWLER_USER_AGENT, "Accept": CRAWLER_ACCEPT_HEADER})
    if auth_token:
        session.headers["Authorization"] = f"Bearer {auth_token}"
    return session


def _safe_get(session: requests.Session, url: str, timeout: int) -> Optional[requests.Response]:
    try:
        response = session.get(url, timeout=timeout)
        if response.status_code >= 400:
            logger.warning("Failed to fetch %s (status %s)", url, response.status_code)
            return None
        return response
    except requests.RequestException as exc:
        logger.error("Request error for %s: %s", url, exc)
        return None


def _parse_document(url: str, html: str, config) -> Dict[str, str]:
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
        "path": _path_for_url(url, config),
        "headings": headings,
        "text": "\n".join(text_lines),
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_links(base_url: str, html: str, config) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    for anchor in soup.find_all("a", href=True):
        normalized = _normalize_url(anchor.get("href"), config, base_url)
        if normalized:
            links.append(normalized)
    return links


def _normalize_url(href: Optional[str], config, base: Optional[str] = None) -> Optional[str]:
    if not href or href.startswith("javascript:") or href.startswith("#"):
        return None
    reference = urljoin(base or f"{config.base_url}/", href)
    reference, _ = urldefrag(reference)
    if not reference.startswith(config.base_url):
        return None
    return reference.rstrip("/")


def _is_allowed(url: str, config) -> bool:
    path = _path_for_url(url, config)
    if path == "/":
        return True
    return any(path.startswith(prefix) for prefix in config.allowed_path_prefixes)


def _path_for_url(url: str, config) -> str:
    if not url:
        return "/"
    path = url.replace(config.base_url, "")
    if not path.startswith("/"):
        path = f"/{path}"
    return re.sub(r"/+", "/", path)


# -----------------------------------------------------------------------------
# Ingestion and search helpers
# -----------------------------------------------------------------------------

def ingest_space(max_pages: Optional[int] = None, force_reindex: bool = False) -> Dict[str, Any]:
    """Fetch GitBook pages, embed their chunks, and bulk index them into Elasticsearch."""
    gitbook_cfg, processor_cfg = _get_configs()
    start_time = time.time()

    collection = collect_documents(max_pages=max_pages)
    documents = collection["documents"]
    pages_discovered = collection["pages_discovered"]
    pages_processed = collection["pages_processed"]
    chunks_generated = collection["chunks_generated"]

    logger.info(
        "Preparing to index %s GitBook chunks produced from %s pages",
        len(documents),
        pages_processed,
    )

    if force_reindex and es_client.indices.exists(index=processor_cfg.index_name):
        logger.warning("Force reindex requested. Deleting index '%s'", processor_cfg.index_name)
        es_client.indices.delete(index=processor_cfg.index_name)

    create_index_if_not_exists(
        index_name=processor_cfg.index_name,
        mapping=index_mapping(),
    )

    indexing_result = bulk_index_documents(
        processor_cfg.index_name,
        documents,
        max_docs=len(documents) or 1,
    )
    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "space": _gitbook_space_name(gitbook_cfg),
        "index_name": processor_cfg.index_name,
        "documents_indexed": indexing_result.get("indexed_count", 0),
        "failed_documents": indexing_result.get("failed_count", 0),
        "pages_discovered": pages_discovered,
        "pages_ingested": pages_processed,
        "chunks_indexed": chunks_generated,
        "duration_seconds": elapsed,
    }


def collect_documents(max_pages: Optional[int] = None) -> Dict[str, Any]:
    """Collect GitBook pages and convert them into chunk-level payloads."""
    gitbook_cfg, processor_cfg = _get_configs()
    session = _get_ingest_session(gitbook_cfg)
    pages = _build_page_index(session, gitbook_cfg)
    if not pages:
        raise RuntimeError("Unable to discover any GitBook pages to ingest")

    documents: List[Dict[str, Any]] = []
    pages_processed = 0
    limit = max_pages if max_pages is not None else processor_cfg.max_pages

    for page in pages:
        if limit and pages_processed >= limit:
            break

        document = _fetch_page_document(page, session, gitbook_cfg)
        if not document:
            continue

        chunk_documents = prepare_document_chunks(document)
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


def search_documents(query: str, limit: int = 5, use_vector: bool = True) -> QueryResult:
    """Execute a semantic-first search across GitBook documents."""
    if not query or not query.strip():
        raise ValueError("Query must not be empty")

    processor_cfg = config_manager.config.gitbook_processor
    size = min(max(limit, 1), 25)

    if use_vector:
        try:
            vector_payload = {
                "query_text": query,
                "index": processor_cfg.index_name,
                "size": size,
                "_source": _vector_source_fields(),
            }
            vector_result = execute_vector_query(vector_payload)
            documents = vector_result.result
            if documents:
                markdown = convert_vector_results_to_markdown(
                    documents,
                    f"Vector results from {processor_cfg.index_name}",
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
                "Unexpected vector search error for query '%s': %s",
                query,
                exc,
                exc_info=True,
            )

    body = {
        "size": size,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title^3", "headings^2", "text"],
                "type": "best_fields",
            }
        },
        "highlight": {
            "fields": {
                "text": {"fragment_size": 120, "number_of_fragments": 3}
            }
        },
    }

    try:
        return execute_query(body, processor_cfg.index_name)
    except NotFoundError as exc:  # pragma: no cover - depends on ES state
        logger.error("GitBook index '%s' missing: %s", processor_cfg.index_name, exc)
        raise


def prepare_document_chunks(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize a GitBook document and emit chunk-level payloads with embeddings."""
    gitbook_cfg, processor_cfg = _get_configs()
    normalized = _normalize_document_payload(document, gitbook_cfg)
    return _build_chunk_documents(normalized, processor_cfg.chunk_size)


def index_mapping() -> Dict[str, Any]:
    """Return the Elasticsearch mapping for GitBook documents."""
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


def _get_configs():
    app_cfg = config_manager.config
    return app_cfg.gitbook, app_cfg.gitbook_processor


def _get_ingest_session(gitbook_cfg) -> requests.Session:
    global _INGEST_SESSION, _INGEST_SESSION_TOKEN
    if _INGEST_SESSION is None or _INGEST_SESSION_TOKEN != gitbook_cfg.auth_token:
        session = requests.Session()
        session.headers.update({
            "User-Agent": INGEST_USER_AGENT,
            "Accept": INGEST_ACCEPT_HEADER,
        })
        if gitbook_cfg.auth_token:
            session.headers["Authorization"] = f"Bearer {gitbook_cfg.auth_token}"
        _INGEST_SESSION = session
        _INGEST_SESSION_TOKEN = gitbook_cfg.auth_token
    return _INGEST_SESSION


def _build_page_index(session: requests.Session, gitbook_cfg) -> List[Dict[str, Any]]:
    manifest = _fetch_manifest(session, gitbook_cfg)
    pages = _extract_manifest_pages(manifest, gitbook_cfg) if manifest else []

    if not pages:
        logger.warning("Manifest parsing failed, falling back to sitemap for %s", gitbook_cfg.base_url)
        pages = _extract_sitemap_pages(session, gitbook_cfg)

    unique_pages = {page["url"]: page for page in pages}
    logger.info("Discovered %s unique GitBook pages", len(unique_pages))
    return list(unique_pages.values())


def _fetch_manifest(session: requests.Session, gitbook_cfg) -> Optional[Dict[str, Any]]:
    for raw_path in MANIFEST_PATHS:
        manifest_url = f"{gitbook_cfg.base_url}/{raw_path}"
        try:
            response = session.get(manifest_url, timeout=gitbook_cfg.request_timeout)
            if response.status_code == 200:
                logger.info("Fetched GitBook manifest from %s", manifest_url)
                return response.json()
        except requests.RequestException as exc:
            logger.debug("Manifest fetch failed for %s: %s", manifest_url, exc)
    return None


def _extract_manifest_pages(manifest: Dict[str, Any], gitbook_cfg) -> List[Dict[str, Any]]:
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
            slug = item.get("slug") or _slugify(path)
            url = path if path.startswith("http") else f"{gitbook_cfg.base_url}/{path.lstrip('/')}"
            pages.append(
                {
                    "id": item.get("id") or item.get("pageId") or slug,
                    "title": title,
                    "slug": slug,
                    "url": url,
                    "path": path,
                }
            )
            children = item.get("children") or item.get("items") or []
            if isinstance(children, list) and children:
                walk(children)

    if nodes:
        walk(nodes)

    logger.info("Extracted %s pages from GitBook manifest", len(pages))
    return pages


def _extract_sitemap_pages(session: requests.Session, gitbook_cfg) -> List[Dict[str, Any]]:
    sitemap_url = f"{gitbook_cfg.base_url}/sitemap.xml"
    pages = _parse_sitemap(session, sitemap_url, visited=set(), gitbook_cfg=gitbook_cfg)
    if not pages:
        logger.warning("Recursive sitemap parsing returned zero pages, falling back to flat parser")
        pages = _parse_flat_sitemap(session, sitemap_url, gitbook_cfg)
    logger.info("Extracted %s pages from sitemap", len(pages))
    return pages


def _parse_sitemap(
    session: requests.Session,
    sitemap_url: str,
    visited: Set[str],
    gitbook_cfg,
) -> List[Dict[str, Any]]:
    if sitemap_url in visited:
        return []
    visited.add(sitemap_url)

    try:
        response = session.get(sitemap_url, timeout=gitbook_cfg.request_timeout)
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

    sitemap_nodes = list(root.iter(sitemap_tag))
    if sitemap_nodes:
        for node in sitemap_nodes:
            loc = node.find(loc_tag)
            if not loc or not loc.text:
                continue
            nested_url = loc.text.strip()
            if not nested_url.startswith("http"):
                continue
            pages.extend(_parse_sitemap(session, nested_url, visited, gitbook_cfg))
        return pages

    for url_node in root.iter(url_tag):
        loc = url_node.find(loc_tag)
        if not loc or not loc.text:
            continue
        url = loc.text.strip()
        if not url.startswith(gitbook_cfg.base_url):
            continue
        if url.endswith(".xml"):
            pages.extend(_parse_sitemap(session, url, visited, gitbook_cfg))
            continue
        path = url.replace(gitbook_cfg.base_url, "").lstrip("/") or "/"
        slug = _slugify(path)
        title = path.replace("-", " ").title() or "Untitled"
        pages.append(
            {
                "id": slug,
                "title": title,
                "slug": slug,
                "url": url,
                "path": path,
            }
        )

    return pages


def _parse_flat_sitemap(session: requests.Session, sitemap_url: str, gitbook_cfg) -> List[Dict[str, Any]]:
    try:
        response = session.get(sitemap_url, timeout=gitbook_cfg.request_timeout)
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
        if not url.startswith(gitbook_cfg.base_url):
            continue
        path = url.replace(gitbook_cfg.base_url, "").lstrip("/") or "/"
        slug = _slugify(path)
        pages.append(
            {
                "id": slug,
                "title": path.replace("-", " ").title(),
                "slug": slug,
                "url": url,
                "path": path,
            }
        )

    return pages


def _fetch_page_document(page: Dict[str, Any], session: requests.Session, gitbook_cfg) -> Optional[Dict[str, Any]]:
    url = page["url"]
    try:
        response = session.get(url, timeout=gitbook_cfg.request_timeout)
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
    slug = page.get("slug") or _slugify(page.get("path") or title)
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
        "space": _gitbook_space_name(gitbook_cfg),
        "last_fetched_at": datetime.now(timezone.utc).isoformat(),
        "word_count": word_count,
        "reading_time_minutes": reading_time,
    }

    normalized = _normalize_document_payload(document, gitbook_cfg)
    logger.debug(
        "Prepared GitBook document payload: %s",
        json.dumps({k: normalized[k] for k in ("id", "title", "url")}),
    )
    return normalized


def _normalize_document_payload(document: Dict[str, Any], gitbook_cfg) -> Dict[str, Any]:
    text = (document.get("text") or "").strip()
    path = document.get("path") or document.get("slug") or document.get("url") or "gitbook"
    title = document.get("title") or "Untitled"
    slug = document.get("slug") or _slugify(path or title)
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
        "space": document.get("space") or _gitbook_space_name(gitbook_cfg),
        "last_fetched_at": document.get("last_fetched_at") or datetime.now(timezone.utc).isoformat(),
        "word_count": word_count,
        "reading_time_minutes": reading_time,
    }


def _build_chunk_documents(document: Dict[str, Any], chunk_size: int) -> List[Dict[str, Any]]:
    text = document.get("text", "")
    if not text:
        return []

    chunks = _chunk_text(text, chunk_size)
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

        chunk_documents.append(
            {
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
            }
        )

    return chunk_documents


def _chunk_text(text: str, chunk_size: int) -> List[str]:
    if not text:
        return []

    words = text.split()
    chunks: List[str] = []
    for start in range(0, len(words), chunk_size):
        chunk_words = words[start : start + chunk_size]
        chunk = " ".join(chunk_words).strip()
        if len(chunk) > 20:
            chunks.append(chunk)
    return chunks


def _vector_source_fields() -> List[str]:
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


def _gitbook_space_name(gitbook_cfg) -> str:
    return gitbook_cfg.base_url.rstrip("/").split("/")[-1] or "gitbook-space"


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "root"


# -----------------------------------------------------------------------------
# Agent helpers
# -----------------------------------------------------------------------------

def generate_gitbook_answer(query: str, limit: int = 4) -> Dict[str, Any]:
    if not query or not query.strip():
        raise ValueError("Query must not be empty")

    agent_config = get_agent_by_name(AGENT_NAME)
    search_result = search_documents(query, limit)
    documents = search_result.result

    if not documents:
        return {
            "answer": "## Direct Answer\nI couldn't find anything for that question.\n\n## Key Details\n- No GitBook passages matched the query.\n\n## References\n*None*",
            "references": [],
            "documents": [],
        }

    snippets = _prepare_snippets(documents)
    references = _build_references(documents)

    instructions = "\n".join(
        agent_config.query_instructions
        + [
            "Follow the template strictly:",
            "## Direct Answer\n<2-3 sentence summary>",
            "## Key Details\n- Bullet fact with inline [number]\n- Another fact",
            "## References\n[List every reference as [n] Title — URL]",
            "Keep the overall response under 150 words unless the user explicitly asks for a detailed or long explanation.",
        ]
    )

    predictor = dspy.Predict(GitBookAnswerSignature)
    response = predictor(
        system_prompt=agent_config.system_prompt,
        user_question=query,
        snippets=snippets,
        format_instructions=instructions,
    )

    answer_text = response.answer_markdown.strip() if response and getattr(response, "answer_markdown", None) else ""
    if not answer_text:
        answer_text = "## Direct Answer\nI'm unable to draft a summary right now.\n\n## Key Details\n- Try again shortly.\n\n## References\n*None*"

    if "## References" in answer_text:
        answer_text = answer_text.split("## References", 1)[0].strip()

    if not _wants_detailed_answer(query):
        answer_text = _enforce_word_limit(answer_text, 150)

    return {
        "answer": answer_text,
        "references": references,
        "documents": documents,
    }


def stream_gitbook_answer(query: str, limit: int = 4) -> Iterator[Dict[str, Any]]:
    """Yield incremental GitBook answer events suitable for StreamingResponse."""
    yield {"type": "status", "message": "Collecting GitBook passages"}
    result = generate_gitbook_answer(query, limit)

    answer_text = result.get("answer", "")
    references = result.get("references", [])
    documents = result.get("documents", [])

    has_chunk = False
    for chunk in _chunk_answer_text(answer_text):
        has_chunk = True
        yield {"type": "answer_chunk", "delta": chunk}

    if not has_chunk:
        yield {"type": "answer_chunk", "delta": "I couldn't find anything for that query."}

    yield {
        "type": "references",
        "references": references,
        "documents": documents,
    }

    yield {"type": "done"}


def _wants_detailed_answer(query: str) -> bool:
    if not query:
        return False

    normalized = query.lower()
    for keyword in LONG_FORM_KEYWORDS:
        if keyword in normalized or re.search(rf"\b{re.escape(keyword)}\b", normalized):
            return True
    return False


def _enforce_word_limit(markdown: str, limit: int = 150) -> str:
    if limit <= 0:
        return markdown

    words_used = 0
    lines = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append(line)
            continue

        if stripped.startswith("## "):
            lines.append(line)
            continue

        prefix = ""
        body = stripped
        if stripped.startswith("- "):
            prefix = "- "
            body = stripped[2:].strip()

        tokens = body.split()
        available = limit - words_used
        if available <= 0:
            break

        if len(tokens) <= available:
            lines.append(f"{prefix}{body}")
            words_used += len(tokens)
        else:
            truncated = " ".join(tokens[:available]) + "…"
            lines.append(f"{prefix}{truncated}")
            words_used = limit
            break

    return "\n".join(lines).strip()


def _prepare_snippets(documents: List[Dict], max_chars: int = 600) -> List[str]:
    snippets = []
    for idx, doc in enumerate(documents, 1):
        title = doc.get("title") or "Untitled"
        url = doc.get("url") or ""
        text = (doc.get("text") or "").replace("\r", " ")
        excerpt = text[:max_chars].strip()
        snippets.append(f"[{idx}] Title: {title}\nURL: {url}\nExcerpt: {excerpt}")
    return snippets


def _build_references(documents: List[Dict]) -> List[str]:
    references = []
    for idx, doc in enumerate(documents, 1):
        title = doc.get("title") or "Untitled"
        url = doc.get("url") or ""
        references.append(f"[{idx}] {title} — {url}")
    return references


def _chunk_answer_text(answer: str, chunk_size: int = 280) -> Iterator[str]:
    sanitized = (answer or "").strip()
    if not sanitized:
        return

    start = 0
    length = len(sanitized)
    while start < length:
        end = min(start + chunk_size, length)
        yield sanitized[start:end]
        start = end
