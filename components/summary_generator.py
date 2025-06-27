"""Summary generation implementation using DSPy."""
import asyncio
import json
import logging
from typing import Dict, Optional

import dspy

from core.exceptions import SummaryGenerationError
from core.interfaces import ISummaryGenerator
from modules.signatures import SummarySignature
from util.performance import monitor_performance

logger = logging.getLogger(__name__)


class DSPySummaryGenerator(ISummaryGenerator):
    """DSPy-based summary generator implementation."""

    def __init__(self):
        """Initialize the summary generator with DSPy components."""
        self.summarizer = dspy.ChainOfThought(SummarySignature)

    @monitor_performance("summary_generation")
    def generate_summary(self, user_query: str, data: Dict, conversation_history: Optional[str] = None) -> Optional[str]:
        """
        Generate a summary of the query results.

        Args:
            user_query: The user's query string
            data: Parsed JSON data from query results
            conversation_history: Optional conversation history for context

        Returns:
            Generated summary string or None if generation fails

        Raises:
            SummaryGenerationError: If summary generation fails
        """
        try:
            logger.info(f"Generating summary for: {user_query}")

            result = self.summarizer(
                user_query=user_query,
                conversation_history=conversation_history,
                json_results=json.dumps(data)
            )

            return result.summary if hasattr(result, 'summary') else None

        except Exception as e:
            logger.error(f"Error generating summary: {e}", exc_info=True)
            raise SummaryGenerationError(f"Failed to generate summary: {e}") from e

    @monitor_performance("summary_generation_async")
    async def generate_summary_async(self, user_query: str, data: Dict, conversation_history: Optional[str] = None) -> Optional[str]:
        """
        Asynchronously generate a summary of the query results.

        Args:
            user_query: The user's query string
            data: Parsed JSON data from query results
            conversation_history: Optional conversation history for context

        Returns:
            Generated summary string or None if generation fails

        Raises:
            SummaryGenerationError: If summary generation fails
        """
        try:
            logger.info(f"Generating summary asynchronously for: {user_query}")

            # Use asyncio.to_thread for CPU-bound operations
            return await asyncio.to_thread(
                self.generate_summary,
                user_query,
                data,
                conversation_history
            )

        except Exception as e:
            logger.error(f"Error generating summary asynchronously: {e}", exc_info=True)
            raise SummaryGenerationError(f"Failed to generate summary asynchronously: {e}") from e
