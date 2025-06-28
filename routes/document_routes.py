"""Simplified document processing routes - single endpoint with background processing."""

import logging
from typing import Dict, Any
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends

from services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

# Maximum file size (50MB for background processing)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf"}


@router.post("/documents/process")
async def process_pdf_document(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Process PDF document with vectorization using background processing.

    Args:
        file: PDF file to process
        current_user: Authenticated user information

    Returns:
        JSON response with processing results
    """
    # Validate file
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

    # Submit to background processing
    from tasks.document_tasks import process_pdf_document

    task = process_pdf_document.delay(file_content, file.filename, current_user.get('user_id'))

    logger.info(f"User {current_user.get('username')} submitted PDF {file.filename} ({file_size_mb:.1f}MB) for processing")

    return {
        "message": "PDF processing task submitted for background processing",
        "task_id": task.id,
        "filename": file.filename,
        "file_size_mb": round(file_size_mb, 2)
    }


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
