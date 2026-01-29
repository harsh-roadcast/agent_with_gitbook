"""Refactored GitBook service - facade for modular components."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, List, Optional

from core.config import config_manager
from services.models import QueryResult

from .gitbook.crawler import GitBookCrawler
from .gitbook.indexer import GitBookIndexer
from .gitbook.search import GitBookSearchService

logger = logging.getLogger(__name__)


class GitBookService:
    """Facade service that delegates to modular GitBook components."""
    
    def __init__(self):
        """Initialize GitBook service facade."""
        self._crawler: Optional[GitBookCrawler] = None
        self._indexer: Optional[GitBookIndexer] = None
        self._search: Optional[GitBookSearchService] = None

    @property
    def crawler(self) -> GitBookCrawler:
        """Lazy-load crawler instance."""
        if self._crawler is None:
            gitbook_cfg = config_manager.config.gitbook
            self._crawler = GitBookCrawler(
                base_url=gitbook_cfg.base_url,
                allowed_path_prefixes=gitbook_cfg.allowed_path_prefixes,
                auth_token=gitbook_cfg.auth_token,
                timeout=gitbook_cfg.request_timeout,
            )
        return self._crawler

    @property
    def indexer(self) -> GitBookIndexer:
        """Lazy-load indexer instance."""
        if self._indexer is None:
            gitbook_cfg = config_manager.config.gitbook
            processor_cfg = config_manager.config.gitbook_processor
            self._indexer = GitBookIndexer(
                base_url=gitbook_cfg.base_url,
                chunk_size=processor_cfg.chunk_size,
                auth_token=gitbook_cfg.auth_token,
                timeout=gitbook_cfg.request_timeout,
                allowed_path_prefixes=gitbook_cfg.allowed_path_prefixes,
            )
        return self._indexer

    @property
    def search(self) -> GitBookSearchService:
        """Lazy-load search instance."""
        if self._search is None:
            processor_cfg = config_manager.config.gitbook_processor
            self._search = GitBookSearchService(index_name=processor_cfg.index_name)
        return self._search

    # -------------------------------------------------------------------------
    # Public API methods - delegate to specialized components
    # -------------------------------------------------------------------------

    def crawl_gitbook_documents(
        self, 
        start_path: str = "/documentation", 
        max_pages: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Crawl GitBook documents using the crawler component."""
        gitbook_cfg = config_manager.config.gitbook
        limit = max_pages if max_pages is not None else gitbook_cfg.max_pages
        return self.crawler.crawl(start_path, limit)

    def save_documents_as_jsonl(self, documents: List[Dict[str, str]], output_path: str) -> None:
        """Save documents to JSONL file."""
        self.indexer.save_documents_as_jsonl(documents, output_path)

    def ingest_space(
        self, 
        max_pages: Optional[int] = None, 
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """Ingest GitBook space into Elasticsearch."""
        processor_cfg = config_manager.config.gitbook_processor
        return self.indexer.ingest_and_index(
            index_name=processor_cfg.index_name,
            max_pages=max_pages,
            force_reindex=force_reindex,
        )

    def search_documents(
        self, 
        query: str, 
        limit: int = 5, 
        use_vector: bool = True
    ) -> QueryResult:
        """Search GitBook documents."""
        return self.search.search(query, limit, use_vector)

    def generate_gitbook_answer(self, query: str, limit: int = 4) -> Dict[str, Any]:
        """Generate AI-powered answer from GitBook documents."""
        return self.search.generate_answer(query, limit)

    def stream_gitbook_answer(self, query: str, limit: int = 4) -> Iterator[Dict[str, Any]]:
        """Stream AI-powered answer from GitBook documents."""
        return self.search.stream_answer(query, limit)


# Singleton instance for backward compatibility
gitbook_service_manager = GitBookService()