"""Document upload and processing routes."""

import os
import tempfile
import logging
from typing import List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import JSONResponse

from services.auth_service import get_current_user
from services.document_service import document_processor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf"}


def validate_file(file: UploadFile) -> None:
    """Validate uploaded file."""
    # Check file extension
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Supported types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check file size (this is a basic check, actual size validation happens during upload)
    if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )


@router.post("/v1/documents/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Upload and process a PDF file for vectorization and storage in Elasticsearch.

    Args:
        file: PDF file to upload
        current_user: Authenticated user information

    Returns:
        JSON response with processing results
    """
    try:
        # Validate file
        validate_file(file)

        user_id = current_user.get('user_id', 'anonymous_user')
        filename = file.filename or "unknown.pdf"

        logger.info(f"Processing PDF upload from user {user_id}: {filename}")

        # Create temporary file
        temp_file = None
        try:
            # Read file content and check size
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
                )

            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf",
                prefix=f"upload_{user_id}_"
            )
            temp_file.write(content)
            temp_file.close()

            # Process the PDF file
            result = document_processor.process_pdf_file(temp_file.name, filename)

            # Add user information to result
            result["user_id"] = user_id
            result["original_filename"] = filename

            if result["status"] == "success":
                logger.info(f"Successfully processed PDF {filename} for user {user_id}")
                return JSONResponse(content=result, status_code=200)
            else:
                logger.error(f"Failed to process PDF {filename}: {result.get('error')}")
                return JSONResponse(content=result, status_code=500)

        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                    logger.debug(f"Cleaned up temporary file: {temp_file.name}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file: {cleanup_error}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in PDF upload endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/v1/documents/search")
async def search_documents(
    query: str = Query(..., description="Search query text"),
    size: int = Query(10, ge=1, le=50, description="Number of results to return"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Search through uploaded documents using vector similarity.

    Args:
        query: Text to search for
        size: Number of results to return (1-50)
        current_user: Authenticated user information

    Returns:
        JSON response with search results
    """
    try:
        user_id = current_user.get('user_id', 'anonymous_user')
        logger.info(f"Document search from user {user_id}: {query[:100]}...")

        # Search documents
        results = document_processor.search_documents(query, size)

        response = {
            "query": query,
            "results": results,
            "total_results": len(results),
            "user_id": user_id
        }

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error in document search endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@router.get("/v1/documents/list")
async def list_documents(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List all uploaded and indexed documents.

    Args:
        current_user: Authenticated user information

    Returns:
        JSON response with list of documents
    """
    try:
        user_id = current_user.get('user_id', 'anonymous_user')
        logger.info(f"Listing documents for user {user_id}")

        # Get document list
        documents = document_processor.list_documents()

        response = {
            "documents": documents,
            "total_documents": len(documents),
            "user_id": user_id
        }

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error in list documents endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"List error: {str(e)}")


@router.delete("/v1/documents/{filename}")
async def delete_document(
    filename: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete a document and all its chunks from Elasticsearch.

    Args:
        filename: Name of the document to delete
        current_user: Authenticated user information

    Returns:
        JSON response with deletion results
    """
    try:
        user_id = current_user.get('user_id', 'anonymous_user')
        logger.info(f"Deleting document {filename} for user {user_id}")

        # Delete documents by filename
        es_client = document_processor.es_client
        delete_query = {
            "query": {
                "term": {"filename": filename}
            }
        }

        result = es_client.delete_by_query(
            index=document_processor.index_name,
            body=delete_query
        )

        deleted_count = result.get('deleted', 0)

        response = {
            "filename": filename,
            "deleted_chunks": deleted_count,
            "status": "success" if deleted_count > 0 else "not_found",
            "user_id": user_id
        }

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} chunks for document {filename}")
            return JSONResponse(content=response, status_code=200)
        else:
            logger.warning(f"No chunks found for document {filename}")
            return JSONResponse(content=response, status_code=404)

    except Exception as e:
        logger.error(f"Error deleting document {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")


@router.get("/v1/documents/status")
async def get_processing_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get the status of the document processing system.

    Args:
        current_user: Authenticated user information

    Returns:
        JSON response with system status
    """
    try:
        user_id = current_user.get('user_id', 'anonymous_user')

        # Check Elasticsearch connection
        es_client = document_processor.es_client
        es_health = es_client.cluster.health()

        # Get index statistics
        try:
            index_stats = es_client.indices.stats(index=document_processor.index_name)
            total_docs = index_stats['indices'][document_processor.index_name]['total']['docs']['count']
            index_size = index_stats['indices'][document_processor.index_name]['total']['store']['size_in_bytes']
        except Exception:
            total_docs = 0
            index_size = 0

        response = {
            "elasticsearch": {
                "status": es_health['status'],
                "cluster_name": es_health['cluster_name'],
                "number_of_nodes": es_health['number_of_nodes']
            },
            "index": {
                "name": document_processor.index_name,
                "total_documents": total_docs,
                "size_bytes": index_size
            },
            "supported_formats": list(ALLOWED_EXTENSIONS),
            "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
            "user_id": user_id
        }

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error getting processing status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Status error: {str(e)}")
