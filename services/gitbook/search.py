"""GitBook search and agent service."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterator, List

import dspy
from elasticsearch import NotFoundError

from agents.agent_config import get_agent_by_name
from modules.keyword_extractor import keyword_extractor
from modules.signatures import GitBookAnswerSignature
from services.models import QueryErrorException, QueryResult
from services.search_service import (
    convert_vector_results_to_markdown,
    execute_query,
    execute_vector_query,
)

logger = logging.getLogger(__name__)


class GitBookSearchService:
    """Handles GitBook search and AI-powered answer generation."""

    AGENT_NAME = "gitbook_rag_copilot"
    
    LONG_FORM_KEYWORDS = (
        "detailed", "long", "longer", "full", "comprehensive",
        "in depth", "in-depth", "deep dive", "extensive", "elaborate",
        "explain in detail", "more detail", "dive deep",
    )

    VECTOR_SOURCE_FIELDS = [
        "title", "slug", "url", "path", "headings", "text", "excerpt",
        "source", "space", "last_fetched_at", "word_count",
        "reading_time_minutes", "page_id", "chunk_id", "chunk_count",
    ]

    def __init__(self, index_name: str):
        """
        Initialize GitBook search service.
        
        Args:
            index_name: Elasticsearch index name for GitBook documents
        """
        self.index_name = index_name

    def search(self, query: str, limit: int = 5, use_vector: bool = True) -> QueryResult:
        """
        Execute semantic search across GitBook documents.
        
        Args:
            query: Search query
            limit: Maximum number of results
            use_vector: Whether to use vector search
            
        Returns:
            QueryResult with documents and metadata
        """
        if not query or not query.strip():
            raise ValueError("Query must not be empty")

        size = min(max(limit, 1), 25)

        # Try vector search first
        if use_vector:
            try:
                # Extract keywords to enhance search
                keywords = keyword_extractor.extract_keywords(query)
                
                vector_payload = {
                    "query_text": query,
                    "index": self.index_name,
                    "size": size,
                    "_source": self.VECTOR_SOURCE_FIELDS,
                    "keywords": keywords,  # Add keywords for hybrid search
                }
                vector_result = execute_vector_query(vector_payload)
                documents = vector_result.result
                
                if documents:
                    markdown = convert_vector_results_to_markdown(
                        documents,
                        f"Vector results from {self.index_name}",
                    )
                    return QueryResult(
                        success=True,
                        result=documents,
                        total_count=len(documents),
                        query_type="vector",
                        markdown_content=markdown,
                    )
            except QueryErrorException as exc:
                logger.warning(
                    "Vector search failed for '%s': %s. Falling back to keyword.",
                    query,
                    exc.query_error.error,
                )
            except Exception as exc:
                logger.warning(
                    "Unexpected vector search error for '%s': %s",
                    query,
                    exc,
                    exc_info=True,
                )

        # Fallback to keyword search
        body = {
            "size": size,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "headings^2", "text"],
                    "type": "best_fields",
                }
            },
            "highlight": {
                "fields": {
                    "text": {"fragment_size": 120, "number_of_fragments": 3}
                }
            },
        }

        try:
            return execute_query(body, self.index_name)
        except NotFoundError as exc:
            logger.error("GitBook index '%s' missing: %s", self.index_name, exc)
            raise

    def generate_answer(self, query: str, limit: int = 4) -> Dict[str, Any]:
        """
        Generate AI-powered answer using GitBook documents.
        
        Args:
            query: User question
            limit: Number of documents to use for context
            
        Returns:
            Dictionary with answer and references
        """
        if not query or not query.strip():
            raise ValueError("Query must not be empty")

        agent_config = get_agent_by_name(self.AGENT_NAME)
        search_result = self.search(query, limit)
        documents = search_result.result

        if not documents:
            return {
                "answer": (
                    "## Direct Answer\n"
                    "I couldn't find anything for that question.\n\n"
                    "## Key Details\n"
                    "- No GitBook passages matched the query."
                ),
                "references": [],
            }

        snippets = self._prepare_snippets(documents)
        references = self._build_references(documents)

        # Build instructions
        instructions = "\n".join(
            agent_config.query_instructions + [
                "CRITICAL CONSTRAINTS:",
                "- MAXIMUM 100-120 WORDS for entire response",
                "- Use ONLY this exact format:",
                "",
                "## Direct Answer",
                "<1-2 concise sentences summarizing the answer>",
                "",
                "## Key Details",
                "- First key point with citation [1]",
                "- Second key point with citation [2]",
                "- Third key point with citation [3]",
                "",
                "DO NOT write paragraphs. DO NOT write long explanations.",
                "DO NOT include the References section - it will be added automatically.",
                "Be extremely concise and direct. Cite sources using [number].",
                "If user asks for 'detailed', 'comprehensive', or 'in-depth' answer, "
                "you may use up to 200 words.",
            ]
        )

        # Generate answer
        predictor = dspy.Predict(GitBookAnswerSignature)
        response = predictor(
            system_prompt=agent_config.system_prompt,
            user_question=query,
            snippets=snippets,
            format_instructions=instructions,
        )

        answer_text = (
            response.answer_markdown.strip()
            if response and getattr(response, "answer_markdown", None)
            else ""
        )
        
        if not answer_text:
            answer_text = (
                "## Direct Answer\n"
                "I'm unable to draft a summary right now.\n\n"
                "## Key Details\n"
                "- Try again shortly."
            )

        # Remove any References section from LLM output
        if "## References" in answer_text:
            answer_text = answer_text.split("## References", 1)[0].strip()

        # Enforce word limit
        word_limit = 200 if self._wants_detailed_answer(query) else 120
        answer_text = self._enforce_word_limit(answer_text, word_limit)

        return {
            "answer": answer_text,
            "references": references,
        }

    def stream_answer(self, query: str, limit: int = 4) -> Iterator[Dict[str, Any]]:
        """
        Stream GitBook answer incrementally.
        
        Args:
            query: User question
            limit: Number of documents to use for context
            
        Yields:
            Event dictionaries for streaming response
        """
        yield {"type": "status", "message": "Collecting GitBook passages"}
        
        result = self.generate_answer(query, limit)
        answer_text = result.get("answer", "")
        references = result.get("references", [])

        has_chunk = False
        for chunk in self._chunk_answer_text(answer_text):
            has_chunk = True
            yield {"type": "answer_chunk", "delta": chunk}

        if not has_chunk:
            yield {"type": "answer_chunk", "delta": "I couldn't find anything for that query."}

        yield {"type": "references", "references": references}
        yield {"type": "done"}

    def _wants_detailed_answer(self, query: str) -> bool:
        """Check if query requests detailed/comprehensive answer."""
        if not query:
            return False

        normalized = query.lower()
        for keyword in self.LONG_FORM_KEYWORDS:
            if keyword in normalized or re.search(rf"\b{re.escape(keyword)}\b", normalized):
                return True
        
        return False

    @staticmethod
    def _enforce_word_limit(markdown: str, limit: int = 150) -> str:
        """Enforce word limit on markdown text."""
        if limit <= 0:
            return markdown

        words_used = 0
        lines = []
        
        for line in markdown.splitlines():
            stripped = line.strip()
            
            if not stripped:
                lines.append(line)
                continue

            # Keep section headers
            if stripped.startswith("## "):
                lines.append(line)
                continue

            # Handle list items
            prefix = ""
            body = stripped
            if stripped.startswith("- "):
                prefix = "- "
                body = stripped[2:].strip()

            tokens = body.split()
            available = limit - words_used
            
            if available <= 0:
                break

            if len(tokens) <= available:
                lines.append(f"{prefix}{body}")
                words_used += len(tokens)
            else:
                truncated = " ".join(tokens[:available]) + "…"
                lines.append(f"{prefix}{truncated}")
                words_used = limit
                break

        return "\n".join(lines).strip()

    @staticmethod
    def _prepare_snippets(documents: List[Dict], max_chars: int = 600) -> List[str]:
        """Prepare document snippets for context."""
        snippets = []
        
        for idx, doc in enumerate(documents, 1):
            title = doc.get("title") or "Untitled"
            url = doc.get("url") or ""
            text = (doc.get("text") or "").replace("\r", " ")
            excerpt = text[:max_chars].strip()
            
            snippets.append(f"[{idx}] Title: {title}\nURL: {url}\nExcerpt: {excerpt}")
        
        return snippets

    @staticmethod
    def _build_references(documents: List[Dict]) -> List[str]:
        """Build reference list from documents."""
        references = []
        
        for idx, doc in enumerate(documents, 1):
            title = doc.get("title") or "Untitled"
            url = doc.get("url") or ""
            references.append(f"[{idx}] {title} — {url}")
        
        return references

    @staticmethod
    def _chunk_answer_text(answer: str, chunk_size: int = 280) -> Iterator[str]:
        """Chunk answer text for streaming."""
        sanitized = (answer or "").strip()
        if not sanitized:
            return

        start = 0
        length = len(sanitized)
        
        while start < length:
            end = min(start + chunk_size, length)
            yield sanitized[start:end]
            start = end
