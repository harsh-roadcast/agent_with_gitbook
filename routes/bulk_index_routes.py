"""Simplified bulk indexing routes - single endpoint with background processing."""
import logging

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from services.auth_service import get_current_user
from modules.models import BulkIndexRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["bulk-indexing"])


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
    from celery_app import celery_app

    task = celery_app.AsyncResult(task_id)
    state = (task.state or "PENDING").upper()
    task_info = task.info if isinstance(task.info, dict) else {}

    if state == "PROGRESS":
        progress = task_info.get("progress", 0)
        message = task_info.get("status", "Task is in progress")
    elif state == "SUCCESS":
        progress = 100
        message = task_info.get("status", "Task completed")
    elif state == "FAILURE":
        progress = task_info.get("progress", 0)
        message = task_info.get("status", "Task failed")
    else:
        progress = 0
        message = f"Task is {state.lower()}"

    return {
        "task_id": task_id,
        "status": state.lower(),
        "progress": progress,
        "message": message,
        "result": task.result if state == "SUCCESS" else None,
        "error": str(task.result) if state == "FAILURE" else None
    }


@router.post("/tasks/bulk-index")
async def bulk_index_documents_alias(
    request: BulkIndexRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Compatibility alias for /bulk-index."""
    return await bulk_index_documents_endpoint(request, current_user)


@router.get("/tasks/{task_id}/status")
async def get_task_status_alias(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Compatibility alias for /bulk-index/status/{task_id}."""
    return await get_bulk_index_status(task_id, current_user)


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

    except Exception as e:
        logger.error(f"Failed to delete index '{index_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete index: {str(e)}")
