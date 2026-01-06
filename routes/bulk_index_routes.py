"""Simplified bulk indexing routes - single endpoint with background processing."""
import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, validator

from services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["bulk-indexing"])


class BulkIndexRequest(BaseModel):
    """Request model for bulk indexing documents."""
    index_name: str = Field(..., description="Name of the Elasticsearch index", min_length=1)
    documents: List[Dict[str, Any]] = Field(..., description="List of documents to index")
    mapping: Optional[Dict[str, Any]] = Field(default=None, description="Optional index mapping")
    settings: Optional[Dict[str, Any]] = Field(default=None, description="Optional index settings")

    @validator('index_name')
    def validate_index_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Index name cannot be empty")
        if not v.islower():
            raise ValueError("Index name must be lowercase")
        if any(char in v for char in [' ', '/', '\\', '*', '?', '"', '<', '>', '|']):
            raise ValueError("Index name contains invalid characters")
        return v.strip()


@router.post("/bulk-index")
async def bulk_index_documents_endpoint(
    request: BulkIndexRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Bulk index documents using background processing for large datasets."""
    from tasks.bulk_index_tasks import bulk_index_documents_async

    logger.info(f"User {current_user.get('username')} requesting bulk index to '{request.index_name}' with {len(request.documents)} documents")

    # Submit to background processing
    task = bulk_index_documents_async.delay(
        request.index_name,
        request.documents,
        current_user.get('user_id'),
        True  # create_index
    )

    return {
        "message": "Bulk indexing task submitted for background processing",
        "task_id": task.id,
        "document_count": len(request.documents),
        "index_name": request.index_name
    }


@router.get("/bulk-index/status/{task_id}")
async def get_bulk_index_status(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get status of bulk indexing task."""
    try:
        from celery_app import celery_app

        task = celery_app.AsyncResult(task_id)
        
        # Extract actual result from meta dict if available
        actual_result = None
        if task.state == "SUCCESS" and isinstance(task.result, dict):
            # Result is nested in meta['result'] due to update_state()
            actual_result = task.result.get('result', task.result)

        return {
            "task_id": task_id,
            "status": task.state.lower(),
            "progress": task.info.get("progress", 0) if task.state == "PROGRESS" else (100 if task.state == "SUCCESS" else 0),
            "message": task.info.get("status", f"Task is {task.state.lower()}") if hasattr(task, 'info') and isinstance(task.info, dict) else f"Task is {task.state.lower()}",
            "result": actual_result,
            "error": str(task.result) if task.state == "FAILURE" else None
        }
    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


@router.post("/bulk-index/gitbook")
async def bulk_index_gitbook_endpoint(
    request_data: dict,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Ingest GitBook documentation, chunk, embed, and bulk index to Elasticsearch."""
    from tasks.bulk_index_tasks import bulk_index_gitbook_async
    
    gitbook_jsonl_path = request_data.get("gitbook_jsonl_path", "")
    logger.info(f"User {current_user.get('username')} requesting GitBook ingestion from {gitbook_jsonl_path}")
    
    # Submit to background processing
    task = bulk_index_gitbook_async.delay(
        gitbook_jsonl_path,
        current_user.get('user_id')
    )
    
    return {
        "message": "GitBook ingestion task submitted for background processing",
        "task_id": task.id,
        "gitbook_path": gitbook_jsonl_path
    }


@router.delete("/index/{index_name}")
async def delete_index(
    index_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete an Elasticsearch index."""
    try:
        from services.search_service import get_es_client

        es_client = get_es_client()

        # Check if index exists
        if not es_client.indices.exists(index=index_name):
            raise HTTPException(status_code=404, detail=f"Index '{index_name}' not found")

        # Delete the index
        es_client.indices.delete(index=index_name)

        logger.info(f"User {current_user.get('username')} deleted index '{index_name}'")

        return {
            "message": f"Index '{index_name}' deleted successfully",
            "index_name": index_name
        }

    except HTTPException:
        # Re-raise HTTPException to preserve status code
        raise
    except Exception as e:
        logger.error(f"Failed to delete index '{index_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete index: {str(e)}")
