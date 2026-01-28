"""Simplified document processing routes - single endpoint with background processing."""

import logging
from pathlib import Path
from typing import Dict, Any, List

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form

from services.auth_service import get_current_user
from services.bulk_index_service import create_index_if_not_exists

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

# Maximum file size (50MB for background processing)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf"}


import re


INDEX_NAME_PATTERN = re.compile(r"^[a-z0-9._-]+$")


def _normalize_index_name(raw_name: str) -> str:
    normalized = (raw_name or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Index name is required")
    if not INDEX_NAME_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=400,
            detail="Index name can only contain lowercase letters, numbers, dots, underscores, or hyphens"
        )
    if normalized in {"_all", "_doc", "_alias"}:
        raise HTTPException(status_code=400, detail="Index name is reserved")
    return normalized


@router.post("/documents/process")
async def process_pdf_document(
    index_name: str = Form(..., description="Name of the index to store the vectorized document data"),
    files: List[UploadFile] = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Queue PDF documents for background processing with vectorization and DSPy metadata extraction.
    Takes in compulsory index name to index the vector data in that index.
    If index doesn't exist, creates it.

    This endpoint returns immediately with task IDs. The actual processing happens asynchronously
    in Celery worker. Use the status endpoint to check progress.

    Args:
        index_name: Required name of the Elasticsearch index to store document vectors
        files: PDF files to process
        current_user: Authenticated user information

    Returns:
        JSON response with task IDs and status URLs for tracking background processing
    """
    # Validate index name
    index_name = _normalize_index_name(index_name)

    # Create index if it doesn't exist
    try:
        index_result = create_index_if_not_exists(
            index_name=index_name,
            mapping={
                "properties": {
                    "filename": {"type": "keyword"},
                    "chunk_id": {"type": "integer"},
                    "text": {"type": "text", "analyzer": "standard"},
                    "embedding": {"type": "dense_vector", "dims": 384},
                    "metadata": {"type": "object"} 
                }
            
            }
        )
        logger.info(f"Index preparation result: {index_result['message']}")
    except Exception as e:
        logger.error(f"Failed to create/check index {index_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Index creation failed: {str(e)}")

    # Validate file
    results = []
    for file in files:
        file_ext = Path(file.filename).suffix.lower() if file.filename else ""
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Read file content
        file_content = await file.read()
        file_size_mb = len(file_content) / (1024 * 1024)

        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        # Queue for background processing with DSPy metadata extraction
        import tempfile
        import os   
        from tasks.document_tasks import process_pdf_document as process_pdf_task

        # Create temporary file for background task
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            logger.info(f"User {current_user.get('username')} queueing PDF {file.filename} ({file_size_mb:.1f}MB) for background processing in index '{index_name}'")

            # Queue the PDF for background processing (returns immediately)
            # Background task will handle the actual processing and temp file cleanup
            result = process_pdf_task.delay(temp_file_path, file.filename, index_name)

            
            logger.info(f"Successfully queued PDF {file.filename} for user {current_user.get('username')} in index '{index_name}'")

            # Get the extracted metadata

            results.append({
                "message": "Processing started",
                "filename": file.filename,
                "task_id": result.id,
                "status_url": f"/documents/status/{result.id}"
            })
            

        except Exception as e:
            logger.error(f"Error queueing PDF {file.filename}: {e}", exc_info=True)
            # Clean up temp file on error
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            raise HTTPException(
                status_code=500,
                detail=f"PDF processing failed: {str(e)}"
            )

    return results

@router.get("/documents/status/{task_id}")
async def get_document_processing_status(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get status of PDF processing task."""
    from celery_app import celery_app

    task = celery_app.AsyncResult(task_id)

    return {
        "task_id": task_id,
        "status": task.state.lower(),
        "progress": task.info.get("progress", 0) if task.state == "PROGRESS" else (100 if task.state == "SUCCESS" else 0),
        "message": task.info.get("status", f"Task is {task.state.lower()}") if hasattr(task, 'info') else f"Task is {task.state.lower()}",
        "result": task.result if task.state == "SUCCESS" else None,
        "error": str(task.result) if task.state == "FAILURE" else None
    }
