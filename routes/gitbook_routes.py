"""Routes for GitBook ingestion and search."""
import json
import logging
from pathlib import Path
from typing import Any, Dict

from elasticsearch import NotFoundError
from fastapi import APIRouter, Depends, HTTPException

from services.auth_service import get_current_user
from services.bulk_index_service import create_index_if_not_exists, bulk_index_documents
from core.config import config_manager
from services.gitbook_service import (
    crawl_gitbook_documents,
    index_mapping,
    prepare_document_chunks,
    search_documents,
)
from modules.models import GitBookIngestRequest, GitBookSearchRequest
from services.search_service import es_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/gitbook", tags=["gitbook"])

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
JSONL_SNAPSHOT = WORKSPACE_ROOT / "gitbook_docs.jsonl"
JSON_SNAPSHOT = WORKSPACE_ROOT / "gitbook_docs.json"


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

        documents = crawl_gitbook_documents(
            start_path=payload.start_path,
            max_pages=effective_max
        )

        if not documents:
            raise HTTPException(status_code=500, detail="Crawl finished but returned no documents")

        chunked_documents = []
        for raw_doc in documents:
            chunked_documents.extend(prepare_document_chunks(raw_doc))

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

        target_index = (
            payload.index_name or config_manager.config.gitbook_processor.index_name
        ).strip().lower()
        if not target_index:
            raise HTTPException(status_code=400, detail="Invalid target index name")

        if payload.force_reindex and es_client.indices.exists(index=target_index):
            logger.info("Force reindex enabled, deleting existing index '%s'", target_index)
            es_client.indices.delete(index=target_index)

        create_index_if_not_exists(
            index_name=target_index,
            mapping=index_mapping()
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
        result = search_documents(payload.query, payload.limit)
        return result.model_dump()
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="GitBook index not found. Please ingest first.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("GitBook search failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="GitBook search failed") from exc

