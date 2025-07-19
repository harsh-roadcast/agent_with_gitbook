"""Pydantic models for service functions."""
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class QueryResult(BaseModel):
    """Pydantic model for Elasticsearch query results."""
    success: bool = Field(True, description="Whether the query was successful")
    result: List[Dict[str, Any]] = Field(default_factory=list, description="The clean document data without ES metadata")
    total_count: int = Field(0, description="Total number of hits from the query")
    query_type: str = Field("standard", description="Type of query executed (standard or vector)")
    markdown_content: Optional[str] = Field(None, description="Optional markdown representation of the results")


class VectorQueryResult(BaseModel):
    """Pydantic model for vector query results."""
    success: bool = Field(True, description="Whether the query was successful")
    result: List[Dict[str, Any]] = Field(default_factory=dict, description="Raw vector search results")
    query_type: str = Field("vector", description="Type of query executed (always vector)")


class QueryError(BaseModel):
    """Pydantic model for query errors."""
    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
