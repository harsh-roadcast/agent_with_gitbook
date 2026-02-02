"""Embedding generation for GitBook chunks."""
from __future__ import annotations

import logging
from typing import Dict, List

from services.search_service import generate_embedding

logger = logging.getLogger(__name__)


class GitBookEmbedder:
    """Generates embeddings for text chunks."""

    def __init__(self, embedding_dim: int = 3072):
        """
        Initialize embedder.
        
        Args:
            embedding_dim: Dimension of embedding vectors (default: 3072 for text-embedding-3-large)
        """
        self.embedding_dim = embedding_dim

    def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Add embeddings to chunk documents.
        
        Args:
            chunks: List of chunk dictionaries
            
        Returns:
            List of chunk dictionaries with embeddings added
        """
        embedded_chunks = []
        
        for chunk in chunks:
            try:
                embedding = generate_embedding(chunk["text"])
                chunk_with_embedding = {**chunk, "embedding": embedding}
                embedded_chunks.append(chunk_with_embedding)
            except Exception as exc:
                logger.warning(
                    "Failed to embed chunk %s: %s",
                    chunk.get("id", "unknown"),
                    exc
                )
                continue

        logger.info("Successfully embedded %s/%s chunks", len(embedded_chunks), len(chunks))
        return embedded_chunks

    def get_index_mapping(self) -> Dict:
        """
        Return Elasticsearch mapping for embedded documents.
        
        Returns:
            Elasticsearch mapping dictionary
        """
        return {
            "properties": {
                "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "slug": {"type": "keyword"},
                "url": {"type": "keyword"},
                "path": {"type": "keyword"},
                "headings": {"type": "keyword"},
                "text": {"type": "text"},
                "excerpt": {"type": "text"},
                "source": {"type": "keyword"},
                "space": {"type": "keyword"},
                "last_fetched_at": {"type": "date"},
                "word_count": {"type": "integer"},
                "reading_time_minutes": {"type": "float"},
                "page_id": {"type": "keyword"},
                "chunk_id": {"type": "integer"},
                "chunk_count": {"type": "integer"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": self.embedding_dim,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        }
