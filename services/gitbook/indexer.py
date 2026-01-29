"""GitBook document indexing orchestration."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from services.bulk_index_service import bulk_index_documents, create_index_if_not_exists

from .chunker import GitBookChunker
from .embedder import GitBookEmbedder
from .ingester import GitBookIngester

logger = logging.getLogger(__name__)


class GitBookIndexer:
    """Orchestrates GitBook ingestion, chunking, embedding, and indexing."""

    def __init__(
        self,
        base_url: str,
        chunk_size: int = 200,
        auth_token: Optional[str] = None,
        timeout: int = 30,
        allowed_path_prefixes: Optional[List[str]] = None,
    ):
        """
        Initialize GitBook indexer.
        
        Args:
            base_url: Base URL of the GitBook site
            chunk_size: Number of words per chunk
            auth_token: Optional authentication token
            timeout: Request timeout in seconds
            allowed_path_prefixes: Path prefixes for crawler
        """
        self.base_url = base_url.rstrip("/")
        
        # Initialize specialized components
        self.ingester = GitBookIngester(
            base_url=base_url,
            auth_token=auth_token,
            timeout=timeout,
            allowed_path_prefixes=allowed_path_prefixes,
        )
        
        self.chunker = GitBookChunker(chunk_size=chunk_size)
        self.embedder = GitBookEmbedder()

    def ingest_and_index(
        self,
        index_name: str,
        max_pages: Optional[int] = None,
        force_reindex: bool = False,
    ) -> Dict[str, Any]:
        """
        Ingest GitBook pages and index them into Elasticsearch.
        
        Args:
            index_name: Target Elasticsearch index name
            max_pages: Maximum number of pages to ingest
            force_reindex: Whether to delete and recreate the index
            
        Returns:
            Dictionary with ingestion statistics
        """
        from services.search_service import es_client
        
        start_time = time.time()

        # Collect and prepare documents
        collection = self.collect_documents(max_pages)
        documents = collection["documents"]
        pages_discovered = collection["pages_discovered"]
        pages_processed = collection["pages_processed"]
        chunks_generated = collection["chunks_generated"]

        logger.info(
            "Preparing to index %s GitBook chunks from %s pages",
            len(documents),
            pages_processed,
        )

        # Handle force reindex
        if force_reindex and es_client.indices.exists(index=index_name):
            logger.warning("Force reindex requested. Deleting index '%s'", index_name)
            es_client.indices.delete(index=index_name)

        # Create index if needed
        create_index_if_not_exists(
            index_name=index_name,
            mapping=self.get_index_mapping(),
        )

        # Bulk index documents
        indexing_result = bulk_index_documents(
            index_name,
            documents,
            max_docs=len(documents) or 1,
        )
        
        elapsed = round(time.time() - start_time, 2)

        return {
            "success": True,
            "space": self._get_space_name(),
            "index_name": index_name,
            "documents_indexed": indexing_result.get("indexed_count", 0),
            "failed_documents": indexing_result.get("failed_count", 0),
            "pages_discovered": pages_discovered,
            "pages_ingested": pages_processed,
            "chunks_indexed": chunks_generated,
            "duration_seconds": elapsed,
        }

    def collect_documents(self, max_pages: Optional[int] = None) -> Dict[str, Any]:
        """
        Collect GitBook pages and convert to chunk-level documents.
        
        Args:
            max_pages: Maximum number of pages to collect
            
        Returns:
            Dictionary with documents and statistics
        """
        # Step 1: Discover pages using ingester
        pages = self.ingester.discover_pages()
        
        if not pages:
            raise RuntimeError("Unable to discover any GitBook pages to ingest")

        documents: List[Dict[str, Any]] = []
        pages_processed = 0
        limit = max_pages or len(pages)

        for page in pages:
            if pages_processed >= limit:
                break

            # Step 2: Fetch page content
            document = self.ingester.fetch_page_content(page)
            if not document:
                continue

            # Step 3: Chunk the document
            chunks = self.chunker.chunk_document(document)
            if not chunks:
                continue

            # Step 4: Embed each chunk
            chunk_documents = self.embedder.embed_chunks(chunks)
            if not chunk_documents:
                continue

            documents.extend(chunk_documents)
            pages_processed += 1

        if not documents:
            raise RuntimeError("GitBook ingestion produced zero documents")

        return {
            "documents": documents,
            "pages_discovered": len(pages),
            "pages_processed": pages_processed,
            "chunks_generated": len(documents),
        }

    def _get_space_name(self) -> str:
        """Extract space name from base URL."""
        return self.base_url.rstrip("/").split("/")[-1] or "gitbook-space"

    def get_index_mapping(self) -> Dict[str, Any]:
        """Return Elasticsearch index mapping."""
        return self.embedder.get_index_mapping()

    @staticmethod
    def save_documents_as_jsonl(documents: List[Dict[str, str]], output_path: str) -> None:
        """Save documents to JSONL file."""
        with open(output_path, "w", encoding="utf-8") as handle:
            for doc in documents:
                payload = {**doc, "text": doc.get("text", "").strip()}
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def close(self) -> None:
        """Close HTTP client resources."""
        self.ingester.close()