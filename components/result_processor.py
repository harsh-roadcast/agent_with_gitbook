"""Result processing implementation."""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, Tuple, AsyncGenerator, List

from core.interfaces import IResultProcessor, QueryResult, ProcessedResult
from util.performance import monitor_performance

logger = logging.getLogger(__name__)


class ResultProcessor(IResultProcessor):
    """Implementation for processing query results."""

    def __init__(self, summary_generator=None, chart_generator=None):
        """Initialize with optional dependency injection."""
        self.summary_generator = summary_generator
        self.chart_generator = chart_generator

    @monitor_performance("result_processing")
    def process_results(self, query_result: QueryResult, user_query: str, conversation_history: Optional[str] = None) -> ProcessedResult:
        """
        Process query results into final format.

        Args:
            query_result: The query result to process
            user_query: The user's original query
            conversation_history: Optional conversation history

        Returns:
            ProcessedResult with all components
        """
        try:
            # Parse conversation history if provided
            parsed_history = self._parse_conversation_history(conversation_history)

            # Generate summary
            summary = None
            if query_result.raw_result and self.summary_generator:
                try:
                    summary = self.summary_generator.generate_summary(
                        user_query, query_result.raw_result, conversation_history
                    )
                except Exception as e:
                    logger.warning(f"Summary generation failed: {e}")

            # Generate chart
            chart_config, chart_html = None, None
            if query_result.raw_result and self.chart_generator:
                try:
                    chart_config = self.chart_generator.generate_chart_config(
                        query_result.data, user_query
                    )
                    if chart_config:
                        chart_html = self.chart_generator.generate_chart_html(chart_config)
                except Exception as e:
                    logger.warning(f"Chart generation failed: {e}")

            return ProcessedResult(
                query_result=query_result,
                summary=summary,
                chart_config=chart_config,
                chart_html=chart_html
            )

        except Exception as e:
            logger.error(f"Error processing results: {e}")
            return ProcessedResult(
                query_result=query_result,
                summary=f"Error processing results: {e}",
                chart_config=None,
                chart_html=None
            )

    async def process_results_async(self, query_result: QueryResult, user_query: str, conversation_history: Optional[str] = None) -> AsyncGenerator[Tuple[str, Any], None]:
        """
        Process results asynchronously, yielding intermediate results.

        Args:
            query_result: The query result to process
            user_query: The user's original query
            conversation_history: Optional conversation history

        Yields:
            Tuples of (field_name, value) for each processed component
        """
        try:
            # Yield the raw query result first
            yield ("data", query_result.data)

            if query_result.elastic_query:
                yield ("elastic_query", query_result.elastic_query)

            # Process summary if generator is available
            if query_result.raw_result and self.summary_generator:
                try:
                    summary = await self._generate_summary_async(
                        user_query, query_result.raw_result, conversation_history
                    )
                    if summary:
                        yield ("summary", summary)
                except Exception as e:
                    logger.warning(f"Async summary generation failed: {e}")
                    yield ("error", f"Summary generation failed: {e}")

            # Process chart if generator is available
            if query_result.raw_result and self.chart_generator:
                try:
                    chart_config = await self._generate_chart_config_async(
                        query_result.data, user_query
                    )
                    if chart_config:
                        yield ("chart_config", chart_config)

                        chart_html = await self._generate_chart_html_async(chart_config)
                        if chart_html:
                            yield ("chart_html", chart_html)
                except Exception as e:
                    logger.warning(f"Async chart generation failed: {e}")

            # Mark processing as completed
            yield ("completed", True)

        except Exception as e:
            logger.error(f"Error in async result processing: {e}")
            yield ("error", f"Error processing results: {e}")

    def _parse_conversation_history(self, conversation_history: Optional[str]) -> Optional[List[Dict]]:
        """Parse conversation history from string to list of dicts."""
        if not conversation_history:
            return None

        try:
            if isinstance(conversation_history, str):
                return json.loads(conversation_history)
            return conversation_history
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse conversation history: {e}")
            return None

    async def _generate_summary_async(self, user_query: str, raw_result: Any, conversation_history: Optional[str] = None) -> Optional[str]:
        """Generate summary asynchronously."""
        if not self.summary_generator:
            return None

        try:
            # If the summary generator has an async method, use it
            if hasattr(self.summary_generator, 'generate_summary_async'):
                return await self.summary_generator.generate_summary_async(
                    user_query, raw_result, conversation_history
                )
            else:
                # Run synchronous method in executor
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    self.summary_generator.generate_summary,
                    user_query, raw_result, conversation_history
                )
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None

    async def _generate_chart_config_async(self, data: List[Dict[str, Any]], user_query: str) -> Optional[Dict]:
        """Generate chart config asynchronously."""
        if not self.chart_generator:
            return None

        try:
            # If the chart generator has an async method, use it
            if hasattr(self.chart_generator, 'generate_chart_config_async'):
                return await self.chart_generator.generate_chart_config_async(data, user_query)
            else:
                # Run synchronous method in executor
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    self.chart_generator.generate_chart_config,
                    data, user_query
                )
        except Exception as e:
            logger.error(f"Error generating chart config: {e}")
            return None

    async def _generate_chart_html_async(self, chart_config: Dict) -> Optional[str]:
        """Generate chart HTML asynchronously."""
        if not self.chart_generator:
            return None

        try:
            # If the chart generator has an async method, use it
            if hasattr(self.chart_generator, 'generate_chart_html_async'):
                return await self.chart_generator.generate_chart_html_async(chart_config)
            else:
                # Run synchronous method in executor
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    self.chart_generator.generate_chart_html,
                    chart_config
                )
        except Exception as e:
            logger.error(f"Error generating chart HTML: {e}")
            return None



