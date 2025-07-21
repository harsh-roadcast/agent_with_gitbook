"""Pydantic models for query processing parameters."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Pydantic model for query processing parameters."""

    user_query: str = Field(..., description="The user's query to process")
    system_prompt: str = Field(..., description="System prompt to guide the query processing")
    conversation_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional conversation history for context"
    )
    es_schemas: List[Dict[str, Any]] = Field(
        default_factory=lambda: [],
        description="List of Elasticsearch schemas to use for query processing"
    )
    vector_db_index: str = Field(
        default="docling_documents",
        description="Vector database index name to use for vector queries"
    )
    query_instructions: List[str] = Field(..., description="Instructions for processing the query")
    goal: str = Field(..., description="High-level goal or objective of the query processing")
    success_criteria: str = Field(..., description="Criteria for determining if the query processing was successful")
    dsl_rules: List[Dict[str, Any]] = Field(..., description="List of rules in Domain-Specific Language (DSL) format that the query processing should follow")

    @classmethod
    def create_with_config(cls, user_query: str, system_prompt: str,
                          conversation_history: Optional[List[Dict[str, Any]]] = None,
                          es_schemas: Optional[List[Dict[str, Any]]] = None,
                          vector_db_index: Optional[str] = None) -> 'QueryRequest':
        """Create QueryRequest with config defaults."""
        from core.config import config_manager

        # Use provided schemas or default from config
        if es_schemas is None:
            # Convert string schema to list of dict format
            config_schema = config_manager.config.es_schema
            es_schemas = [{"schema": config_schema}] if config_schema else []

        return cls(
            user_query=user_query,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            es_schemas=es_schemas,
            vector_db_index=vector_db_index or "docling_documents"
        )

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            # Add any custom encoders if needed
        }
        validate_assignment = True
