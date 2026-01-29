"""DSPy signatures for the query processing system."""
# This file now only contains the DSPy signatures
# The ActionDecider class has been removed as it was redundant with the query agent
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
import jwt
from datetime import datetime, timedelta, timezone

from core.config import config_manager

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
    
class GitBookIngestRequest(BaseModel):
    force_reindex: bool = Field(False, description="Drop and recreate the index before ingesting")
    max_pages: int | None = Field(
        default=None,
        ge=1,
        le=500,
        description="Optional hard limit for number of pages to ingest"
    )
    start_path: str = Field("/documentation", description="GitBook path to start crawling from")
    index_name: str | None = Field(
        default=None,
        description="Optional override for the Elasticsearch index name"
    )


class GitBookSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query text")
    limit: int = Field(5, ge=1, le=25, description="Maximum number of results to return")

class JWTAuthenticator:
    """JWT token authenticator."""

    def __init__(self):
        """Initialize with configuration."""
        self.config = config_manager.config
        self.secret_key = self.config.auth.jwt_secret_key or "dev-secret-key-change-in-production"
        self.algorithm = self.config.auth.jwt_algorithm

    def create_token(self, user_id: str = "admin", username: str = "admin") -> str:
        """Create a JWT access token."""
        expire = datetime.now(timezone.utc) + timedelta(days=365)  # 24 hour token

        payload = {
            "user_id": user_id,
            "username": username,
            "sub": username,
            "exp": expire,
            "iat": datetime.now(timezone.utc)
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate and decode JWT token."""
        payload = jwt.decode(
            token,
            self.secret_key,
            algorithms=[self.algorithm],
            options={"verify_exp": True}
        )

        return {
            'user_id': payload.get('user_id'),
            'username': payload.get('username', payload.get('sub')),
            'issued_at': payload.get('iat'),
            'expires_at': payload.get('exp')
        }

# Global authenticator instance
authenticator = JWTAuthenticator()