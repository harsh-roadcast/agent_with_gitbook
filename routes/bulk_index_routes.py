"""Bulk indexing routes for Elasticsearch operations."""
import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field, validator

from services.auth_service import get_current_user
from services.bulk_index_service import (
    bulk_index_documents,
    create_index_if_not_exists,
    get_index_info
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bulk-indexing"])


class BulkIndexRequest(BaseModel):
    """Request model for bulk indexing documents."""
    index_name: str = Field(..., description="Name of the Elasticsearch index", min_length=1)
    documents: List[Dict[str, Any]] = Field(..., description="List of documents to index (max 500)")
    create_index: bool = Field(default=True, description="Whether to create index if it doesn't exist")
    mapping: Optional[Dict[str, Any]] = Field(default=None, description="Optional index mapping")
    settings: Optional[Dict[str, Any]] = Field(default=None, description="Optional index settings")

    @validator('documents')
    def validate_documents(cls, v):
        if not v:
            raise ValueError("Documents list cannot be empty")
        if len(v) > 500:
            raise ValueError("Maximum 500 documents allowed per request")
        return v

    @validator('index_name')
    def validate_index_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Index name cannot be empty")
        # Basic index name validation (Elasticsearch naming rules)
        if not v.islower():
            raise ValueError("Index name must be lowercase")
        if any(char in v for char in [' ', '/', '\\', '*', '?', '"', '<', '>', '|']):
            raise ValueError("Index name contains invalid characters")
        return v.strip()


class IndexCreationRequest(BaseModel):
    """Request model for creating an index."""
    index_name: str = Field(..., description="Name of the Elasticsearch index", min_length=1)
    mapping: Optional[Dict[str, Any]] = Field(default=None, description="Index mapping configuration")
    settings: Optional[Dict[str, Any]] = Field(default=None, description="Index settings configuration")

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
async def bulk_index_endpoint(
    request: BulkIndexRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Bulk index documents into Elasticsearch."""
    logger.info(f"User {current_user.get('username', 'unknown')} requesting bulk index to '{request.index_name}'")

    # Create index if requested and it doesn't exist
    if request.create_index:
        index_result = create_index_if_not_exists(
            request.index_name,
            mapping=request.mapping,
            settings=request.settings
        )

        if not index_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create index: {index_result['error']}"
            )

    # Perform bulk indexing
    result = bulk_index_documents(
        index_name=request.index_name,
        documents=request.documents,
        max_docs=500
    )

    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"Bulk indexing failed: {result['error']}"
        )

    logger.info(f"Bulk indexing completed: {result['indexed_count']} documents indexed")

    return {
        "message": "Bulk indexing completed successfully",
        "result": result,
        "user": current_user.get('username', 'unknown')
    }


@router.post("/create-index")
async def create_index_endpoint(
    request: IndexCreationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new Elasticsearch index with optional mapping and settings."""
    logger.info(f"User {current_user.get('username', 'unknown')} requesting index creation: '{request.index_name}'")

    result = create_index_if_not_exists(
        request.index_name,
        mapping=request.mapping,
        settings=request.settings
    )

    return {
        "message": "Index operation completed",
        "result": result,
        "user": current_user.get('username', 'unknown')
    }


@router.get("/index-info/{index_name}")
async def get_index_info_endpoint(
    index_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get information about an Elasticsearch index."""
    logger.info(f"User {current_user.get('username', 'unknown')} requesting info for index: '{index_name}'")

    result = get_index_info(index_name.strip())

    return {
        "message": "Index information retrieved successfully",
        "result": result,
        "user": current_user.get('username', 'unknown')
    }


@router.post("/bulk-index-simple")
async def bulk_index_simple_endpoint(
    index_name: str = Body(..., description="Name of the Elasticsearch index"),
    documents: List[Dict[str, Any]] = Body(..., description="List of documents to index (max 500)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Simple bulk index endpoint with minimal parameters."""
    index_name = index_name.strip().lower()

    logger.info(f"User {current_user.get('username', 'unknown')} requesting simple bulk index to '{index_name}'")

    # Create index if it doesn't exist
    create_result = create_index_if_not_exists(index_name)

    # Perform bulk indexing
    result = bulk_index_documents(
        index_name=index_name,
        documents=documents,
        max_docs=500
    )

    return {
        "message": "Simple bulk indexing completed successfully",
        "indexed_count": result["indexed_count"],
        "failed_count": result["failed_count"],
        "index_name": result["index_name"],
        "user": current_user.get('username', 'unknown')
    }
