"""Keyword extraction for query enhancement."""
from __future__ import annotations

import logging
from typing import List

import dspy

from modules.signatures import KeywordExtractionSignature

logger = logging.getLogger(__name__)


class KeywordExtractor:
    """Extracts keywords from queries to enhance vector search.
    
     Uses DSPy to extract keywords from user queries in multiple languages."""
    
    def __init__(self, max_keywords: int = 10):
        """
        Initialize keyword extractor with DSPy predictor.
        
        Args:
            max_keywords: Maximum number of keywords to extract (default: 10)
        """
        self.predictor = dspy.Predict(KeywordExtractionSignature)
        self.max_keywords = max_keywords
    
    def extract_keywords(self, query: str) -> List[str]:
        """
        Extract keywords from a user query.
        
        The OpenAI embedding model handles multilingual understanding,
        so no manual translation is needed for Hinglish or other languages.
        
        Args:
            query: User's natural language query in any language
            
        Returns:
            List of extracted keywords
        """
        if not query or not query.strip():
            logger.debug("Empty query provided, returning empty keywords")
            return []
        
        try:
            response = self.predictor(query=query.strip())
            keywords_str = response.keywords if hasattr(response, 'keywords') else ""
            
            if not keywords_str:
                logger.warning("No keywords extracted from query: '%s'", query[:100])
                return []
            
            # Parse comma-separated keywords and filter empty strings
            keywords = [
                kw.strip() 
                for kw in keywords_str.split(',') 
                if kw.strip()
            ]
            
            # Limit to max_keywords
            keywords = keywords[:self.max_keywords]
            
            logger.info("Extracted %d keywords: %s", len(keywords), keywords)
            return keywords
            
        except Exception as exc:
            logger.error("Failed to extract keywords from query '%s': %s", 
                        query[:100], exc, exc_info=True)
            return []


# Global instance
keyword_extractor = KeywordExtractor()

