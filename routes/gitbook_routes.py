"""Routes for GitBook ingestion and search."""
import json
import logging
from pathlib import Path
from typing import Any, Dict

from elasticsearch import NotFoundError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.auth_service import get_current_user
from services.bulk_index_service import create_index_if_not_exists, bulk_index_documents
from services.gitbook_crawler import GitBookCrawler, GitBookCrawlerConfig
from services.gitbook_processor import gitbook_processor
from services.search_service import es_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/gitbook", tags=["gitbook"])

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
JSONL_SNAPSHOT = WORKSPACE_ROOT / "gitbook_docs.jsonl"
JSON_SNAPSHOT = WORKSPACE_ROOT / "gitbook_docs.json"


class GitBookIngestRequest(BaseModel):
    force_reindex: bool = Field(False, description="Drop and recreate the index before ingesting")
    max_pages: int | None = Field(
        default=None,
        ge=1,
        le=500,
        description="Optional hard limit for number of pages to ingest"
    )
    start_path: str = Field("/documentation", description="GitBook path to start crawling from")
    index_name: str | None = Field(
        default=None,
        description="Optional override for the Elasticsearch index name"
    )


class GitBookSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query text")
    limit: int = Field(5, ge=1, le=25, description="Maximum number of results to return")


class GitBookChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User prompt for the GitBook RAG chatbot")
    limit: int = Field(4, ge=1, le=10, description="Maximum GitBook passages to ground the answer")


@router.post("/ingest")
async def ingest_gitbook_documentation(
    payload: GitBookIngestRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Trigger a fresh GitBook ingestion run."""
    try:
        logger.info("User %s requested GitBook crawl ingest", current_user.get("username"))
        logger.info("GitBook ingest payload: %s", payload.model_dump())

        crawler_config = GitBookCrawlerConfig()
        if payload.max_pages is not None:
            crawler_config.max_pages = payload.max_pages
        logger.info(
            "GitBook crawler configured with max_pages=%s (default=%s)",
            crawler_config.max_pages,
            GitBookCrawlerConfig().max_pages
        )

        crawler = GitBookCrawler(crawler_config)
        documents = crawler.crawl(start_path=payload.start_path)

        if not documents:
            raise HTTPException(status_code=500, detail="Crawl finished but returned no documents")

        chunked_documents = []
        for raw_doc in documents:
            chunked_documents.extend(gitbook_processor.prepare_document_chunks(raw_doc))

        if not chunked_documents:
            raise HTTPException(status_code=500, detail="No embeddable GitBook chunks were generated from the crawl")

        # Persist snapshots locally for debugging/exports
        JSONL_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        with JSONL_SNAPSHOT.open("w", encoding="utf-8") as handle:
            for doc in chunked_documents:
                handle.write(json.dumps(doc, ensure_ascii=False) + "\n")

        JSON_SNAPSHOT.write_text(
            json.dumps(chunked_documents, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        target_index = (payload.index_name or gitbook_processor.config.index_name).strip().lower()
        if not target_index:
            raise HTTPException(status_code=400, detail="Invalid target index name")

        if payload.force_reindex and es_client.indices.exists(index=target_index):
            logger.info("Force reindex enabled, deleting existing index '%s'", target_index)
            es_client.indices.delete(index=target_index)

        create_index_if_not_exists(
            index_name=target_index,
            mapping=gitbook_processor.index_mapping()
        )

        bulk_result = bulk_index_documents(
            target_index,
            chunked_documents,
            max_docs=len(chunked_documents) or 1
        )

        return {
            "message": "GitBook crawl and ingest completed",
            "documents_crawled": len(documents),
            "chunks_generated": len(chunked_documents),
            "jsonl_path": str(JSONL_SNAPSHOT),
            "json_path": str(JSON_SNAPSHOT),
            "index_name": target_index,
            "bulk_index_result": bulk_result
        }
    except Exception as exc:
        logger.error("GitBook ingestion failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"GitBook ingestion failed: {exc}") from exc


@router.post("/search")
async def search_gitbook(payload: GitBookSearchRequest):
    """Search previously ingested GitBook documents."""
    try:
        result = gitbook_processor.search_documents(payload.query, payload.limit)
        return result.model_dump()
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="GitBook index not found. Please ingest first.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("GitBook search failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="GitBook search failed") from exc


@router.post("/chat")
async def chat_gitbook(payload: GitBookChatRequest):
    """Deprecated in favor of /v1/chat/completions."""
    raise HTTPException(
        status_code=410,
        detail="/v1/gitbook/chat is deprecated. Use /v1/chat/completions with model='gitbook_rag'."
    )
