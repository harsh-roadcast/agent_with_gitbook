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


@router.post("/documents/process")
async def process_pdf_document(
    index_name: str = Form(..., description="Name of the index to store the vectorized document data"),
    files: List[UploadFile] = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Process PDF document with vectorization using foreground processing and DSPy metadata extraction.
    Takes in compulsory index name to index the vector data in that index.
    If index doesn't exist, creates it.

    Args:
        index_name: Required name of the Elasticsearch index to store document vectors
        files: PDF files to process
        current_user: Authenticated user information

    Returns:
        JSON response with processing results and extracted metadata
    """
    # Validate index name
    if not index_name or not index_name.strip():
        raise HTTPException(status_code=400, detail="Index name is required")

    index_name = index_name.strip().lower()

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
                    "metadata": {
                        "properties": {
                            "upload_timestamp": {"type": "date"},
                            "processing_method": {"type": "keyword"},
                            "document_title": {"type": "text"},
                            "document_type": {"type": "keyword"},
                            "main_topics": {"type": "keyword"},
                            "key_entities": {"type": "keyword"},
                            "language": {"type": "keyword"},
                            "summary": {"type": "text"},
                            "keywords": {"type": "keyword"}
                        }
                    }
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

        # Process in foreground with DSPy metadata extraction
        import tempfile
        import os
        from services.document_service import document_processor

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            logger.info(f"User {current_user.get('username')} processing PDF {file.filename} ({file_size_mb:.1f}MB) in foreground with index '{index_name}'")

            # Process the PDF with DSPy metadata extraction and custom index
            result = document_processor.process_pdf_file(temp_file_path, file.filename, index_name)

            if result["status"] == "success":
                logger.info(f"Successfully processed PDF {file.filename} for user {current_user.get('username')} in index '{index_name}'")

                # Get the extracted metadata
                metadata = result.get("extracted_metadata", {})

                results.append({
                    "message": "PDF processing completed successfully",
                    "filename": file.filename,
                    "file_size_mb": round(file_size_mb, 2),
                    "processing_method": "foreground_with_dspy",
                    "index_name": index_name,
                    "index_created": index_result.get("created", False),
                    "total_chunks": result["total_chunks"],
                    "indexed_chunks": result["indexed_chunks"],
                    "failed_chunks": result.get("failed_chunks", 0),
                    "extracted_metadata": {
                        "document_title": metadata.get("document_title", ""),
                        "document_type": metadata.get("document_type", ""),
                        "main_topics": metadata.get("main_topics", []),
                        "key_entities": metadata.get("key_entities", []),
                        "language": metadata.get("language", ""),
                        "summary": metadata.get("summary", ""),
                        "keywords": metadata.get("keywords", [])
                    },
                    "processing_details": {
                        "extraction_method": "docling_markdown",
                        "metadata_extraction": "dspy_ai_powered",
                        "indexing_status": "completed" if result["indexed_chunks"] > 0 else "failed",
                        "target_index": result.get("target_index", index_name)
                    }
                })
            else:
                logger.error(f"Failed to process PDF {file.filename}: {result.get('error', 'Unknown error')}")
                raise HTTPException(
                    status_code=500,
                    detail=f"PDF processing failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            logger.error(f"Error processing PDF {file.filename}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"PDF processing failed: {str(e)}"
            )
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

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
