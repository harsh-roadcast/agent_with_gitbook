"""Text chunking for GitBook documents."""
from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class GitBookChunker:
    """Splits documents into word-based chunks."""

    def __init__(self, chunk_size: int = 200, min_chunk_length: int = 20):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Number of words per chunk
            min_chunk_length: Minimum character length for a chunk
        """
        self.chunk_size = chunk_size
        self.min_chunk_length = min_chunk_length

    def chunk_document(self, document: Dict) -> List[Dict]:
        """
        Split document into chunks with metadata.
        
        Args:
            document: Document dictionary with 'text' and metadata
            
        Returns:
            List of chunk dictionaries (without embeddings)
        """
        text = document.get("text", "")
        if not text:
            return []

        chunks = self._split_text(text)
        if not chunks:
            return []

        chunk_documents: List[Dict] = []
        chunk_count = len(chunks)
        
        for chunk_id, chunk_text in enumerate(chunks):
            chunk_documents.append({
                "id": f"{document['id']}_chunk_{chunk_id}",
                "page_id": document["id"],
                "chunk_id": chunk_id,
                "chunk_count": chunk_count,
                "title": document["title"],
                "slug": document["slug"],
                "url": document["url"],
                "path": document["path"],
                "headings": document.get("headings", []),
                "text": chunk_text,
                "excerpt": chunk_text[:500],
                "source": document["source"],
                "space": document["space"],
                "last_fetched_at": document["last_fetched_at"],
                "word_count": document.get("word_count", 0),
                "reading_time_minutes": document.get("reading_time_minutes", 0.0),
            })

        return chunk_documents

    def _split_text(self, text: str) -> List[str]:
        """
        Split text into word-based chunks.
        
        Args:
            text: Full text content
            
        Returns:
            List of text chunks
        """
        if not text:
            return []

        words = text.split()
        chunks: List[str] = []
        
        for start in range(0, len(words), self.chunk_size):
            chunk_words = words[start : start + self.chunk_size]
            chunk = " ".join(chunk_words).strip()
            
            if len(chunk) >= self.min_chunk_length:
                chunks.append(chunk)
        
        return chunks
