"""Main query agent implementation orchestrating all components."""
import logging
from typing import Optional, AsyncGenerator, Tuple, Any

from core.config import config_manager
from core.exceptions import DSPyAgentException
from core.interfaces import (
    IQueryAgent, IDatabaseSelector, IQueryExecutor, IResultProcessor,
    ProcessedResult
)
from util.performance import monitor_performance

logger = logging.getLogger(__name__)


class QueryAgent(IQueryAgent):
    """Main query agent that orchestrates all components."""

    def __init__(
        self,
        database_selector: IDatabaseSelector,
        query_executor: IQueryExecutor,
        result_processor: IResultProcessor
    ):
        """Initialize with dependency injection."""
        self.database_selector = database_selector
        self.query_executor = query_executor
        self.result_processor = result_processor
        self.config = config_manager.config

    @monitor_performance("query_processing")
    def process_query(self, user_query: str, conversation_history: Optional[str] = None) -> ProcessedResult:
        """
        Process a user query and return complete results.

        Args:
            user_query: The user's query string
            conversation_history: Optional conversation history for context

        Returns:
            ProcessedResult with all components

        Raises:
            DSPyAgentException: If processing fails
        """
        try:
            # Step 1: Select the appropriate database
            database_type = self.database_selector.select_database(
                user_query, self.config.es_schema
            )

            # Step 2: Execute the query
            query_result = self.query_executor.execute_query(
                database_type, user_query, self.config.es_schema, self.config.es_instructions
            )

            # Step 3: Process results
            processed_result = self.result_processor.process_results(
                query_result, user_query, conversation_history
            )

            return processed_result

        except Exception as e:
            logger.error(f"Error in QueryAgent.process_query: {e}", exc_info=True)
            raise DSPyAgentException(f"Query processing failed: {e}") from e

    @monitor_performance("query_processing_async")
    async def process_query_async(self, user_query: str, conversation_history: Optional[str] = None) -> AsyncGenerator[Tuple[str, Any], None]:
        """
        Process query asynchronously, yielding results as they become available.

        Args:
            user_query: The user's query string
            conversation_history: Optional conversation history for context

        Yields:
            Tuples of (field_name, field_value) as results are generated

        Raises:
            DSPyAgentException: If processing fails
        """
        try:
            # Step 1: Select the appropriate database
            database_type = self.database_selector.select_database(
                user_query, self.config.es_schema
            )

            # Step 2: Execute the query
            query_result = self.query_executor.execute_query(
                database_type, user_query, self.config.es_schema, self.config.es_instructions
            )

            # Step 3: Process results asynchronously
            async for field_name, field_value in self.result_processor.process_results_async(
                query_result, user_query, conversation_history
            ):
                yield field_name, field_value

        except Exception as e:
            logger.error(f"Error in QueryAgent.process_query_async: {e}", exc_info=True)
            yield "error", str(e)
