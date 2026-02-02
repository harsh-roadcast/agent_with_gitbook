"""Text chunking for GitBook documents."""
from __future__ import annotations
from langchain_text_splitters import RecursiveCharacterTextSplitter

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class GitBookChunker:
    """Splits documents into word-based chunks."""

    def __init__(self, chunk_size: int = 200, min_chunk_length: int = 20):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Number of words per chunk (converted to ~characters internally)
            min_chunk_length: Minimum character length for a chunk
        """
        
        self.chunk_size_chars = chunk_size * 6
        self.chunk_overlap = int(self.chunk_size_chars * 0.15)  
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

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size_chars,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
            length_function=len,
        )

        chunks = splitter.split_text(text)
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

    
