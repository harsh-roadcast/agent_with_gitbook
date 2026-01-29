"""Routes for GitBook ingestion and search."""
import logging
from typing import Any, Dict

from elasticsearch import NotFoundError
from fastapi import APIRouter, Depends, HTTPException

from services.auth_service import get_current_user
from core.config import config_manager
from services.gitbook_service import gitbook_service_manager
from modules.models import GitBookIngestRequest, GitBookSearchRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/gitbook", tags=["gitbook"])


@router.post("/ingest")
async def ingest_gitbook_documentation(
    payload: GitBookIngestRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Trigger a fresh GitBook ingestion run."""
    try:
        logger.info("User %s requested GitBook crawl ingest", current_user.get("username"))
        logger.info("GitBook ingest payload: %s", payload.model_dump())

        gitbook_cfg = config_manager.config.gitbook
        effective_max = payload.max_pages if payload.max_pages is not None else gitbook_cfg.max_pages
        logger.info(
            "GitBook crawler configured with max_pages=%s (default=%s)",
            effective_max,
            gitbook_cfg.max_pages
        )

        # Use unified ingest_space method (handles crawl + chunk + index)
        target_index = (
            payload.index_name or config_manager.config.gitbook_processor.index_name
        ).strip().lower()
        if not target_index:
            raise HTTPException(status_code=400, detail="Invalid target index name")

        # Temporarily update config if custom index provided
        original_index = config_manager.config.gitbook_processor.index_name
        if payload.index_name:
            config_manager.config.gitbook_processor.index_name = target_index

        try:
            result = gitbook_service_manager.ingest_space(
                max_pages=effective_max,
                force_reindex=payload.force_reindex
            )
        finally:
            # Restore original config
            config_manager.config.gitbook_processor.index_name = original_index

        # Optionally export to JSON/JSONL for debugging
        if result.get("success"):
            logger.info(
                "GitBook ingestion completed: %s pages → %s chunks indexed",
                result.get("pages_ingested"),
                result.get("chunks_indexed")
            )

        return {
            "message": "GitBook crawl and ingest completed",
            "documents_crawled": result.get("pages_ingested", 0),
            "chunks_generated": result.get("chunks_indexed", 0),
            "index_name": result.get("index_name"),
            "space": result.get("space"),
            "duration_seconds": result.get("duration_seconds"),
            "documents_indexed": result.get("documents_indexed", 0),
            "failed_documents": result.get("failed_documents", 0)
        }
    except Exception as exc:
        logger.error("GitBook ingestion failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"GitBook ingestion failed: {exc}") from exc


@router.post("/search")
async def search_gitbook(payload: GitBookSearchRequest):
    """Search previously ingested GitBook documents."""
    try:
        result = gitbook_service_manager.search_documents(payload.query, payload.limit)
        return result.model_dump()
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="GitBook index not found. Please ingest first.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("GitBook search failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="GitBook search failed") from exc

