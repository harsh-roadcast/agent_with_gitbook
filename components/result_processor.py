"""Result processing implementation."""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, Tuple, AsyncGenerator, Union

from core.interfaces import IResultProcessor, ISummaryGenerator, IChartGenerator, QueryResult, ProcessedResult
from util.performance import monitor_performance

logger = logging.getLogger(__name__)


class ResultProcessor(IResultProcessor):
    """Implementation for processing query results."""

    def __init__(self, summary_generator: ISummaryGenerator, chart_generator: IChartGenerator):
        """Initialize with dependency injection."""
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
            # Generate summary
            summary = None
            if query_result.raw_result:
                try:
                    summary = self.summary_generator.generate_summary(
                        user_query, query_result.raw_result, conversation_history
                    )
                except Exception as e:
                    logger.warning(f"Summary generation failed: {e}")

            # Generate chart
            chart_config, chart_html = None, None
            if query_result.raw_result:
                try:
                    chart_config, chart_html = self.chart_generator.generate_chart(
                        query_result.raw_result, user_query
                    )
                except Exception as e:
                    logger.warning(f"Chart generation failed: {e}")

            return ProcessedResult(
                query_result=query_result,
                summary=summary,
                chart_config=chart_config,
                chart_html=chart_html
            )

        except Exception as e:
            logger.error(f"Error processing results: {e}", exc_info=True)
            # Return partial result with error
            query_result.error = str(e)
            return ProcessedResult(query_result=query_result)

    @monitor_performance("result_processing_async")
    async def process_results_async(self, query_result: QueryResult, user_query: str, conversation_history: Optional[str] = None) -> AsyncGenerator[Tuple[str, Any], None]:
        """
        Process results asynchronously, yielding intermediate results.

        Args:
            query_result: The query result to process
            user_query: The user's original query
            conversation_history: Optional conversation history

        Yields:
            Tuples of (field_name, field_value) as results are generated
        """
        try:
            # Yield basic query result information
            yield "database", query_result.database_type.value
            yield "data", query_result.data

            # Format and yield elastic query if available
            if query_result.elastic_query:
                elastic_query_formatted = self._format_elastic_query_as_code_block(query_result.elastic_query)
                yield "elastic_query", elastic_query_formatted

            # Generate summary and chart in parallel if we have data
            if query_result.raw_result:
                # Create tasks for parallel execution
                summary_task = asyncio.create_task(
                    self._generate_summary_safe(user_query, query_result.raw_result, conversation_history)
                )
                chart_task = asyncio.create_task(
                    self._generate_chart_safe(query_result.raw_result, user_query)
                )

                # Yield results as they become available
                summary = await summary_task
                if summary:
                    yield "summary", summary

                chart_config, chart_html = await chart_task
                if chart_config:
                    yield "chart_config", chart_config
                if chart_html:
                    yield "chart_html", chart_html

        except Exception as e:
            logger.error(f"Error in async result processing: {e}", exc_info=True)
            yield "error", str(e)

    async def _generate_summary_safe(self, user_query: str, data: Dict, conversation_history: Optional[str] = None) -> Optional[str]:
        """Safely generate summary with error handling."""
        try:
            return await self.summary_generator.generate_summary_async(user_query, data, conversation_history)
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            return None

    async def _generate_chart_safe(self, data: Dict, user_query: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Safely generate chart with error handling."""
        try:
            return await self.chart_generator.generate_chart_async(data, user_query)
        except Exception as e:
            logger.warning(f"Chart generation failed: {e}")
            return None, None

    def _format_elastic_query_as_code_block(self, elastic_query: Union[dict, str]) -> str:
        """Format the Elasticsearch query as a Markdown code block."""
        try:
            if isinstance(elastic_query, dict):
                query_str = json.dumps(elastic_query, indent=2, ensure_ascii=False)
            else:
                query_str = str(elastic_query)

            return f"```json\n{query_str}\n```"
        except Exception as e:
            logger.error(f"Error formatting elastic query: {e}")
            return f"```\n{str(elastic_query)}\n```"
