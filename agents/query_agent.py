"""Main query agent implementation orchestrating all components."""
import logging
from typing import Optional, AsyncGenerator, Tuple, Any, List, Dict
import json

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

    def _parse_conversation_history(self, conversation_history: Optional[str]) -> Optional[List[Dict]]:
        """Parse conversation history string to list of dictionaries."""
        if not conversation_history:
            return None

        try:
            # If it's already a string that looks like JSON, parse it
            if isinstance(conversation_history, str):
                return json.loads(conversation_history)
            # If it's already a list, return as is
            elif isinstance(conversation_history, list):
                return conversation_history
            else:
                return None
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to parse conversation history: {conversation_history}")
            return None

    @monitor_performance("query_processing")
    def process_query(self, user_query: str, conversation_history: Optional[str] = None) -> ProcessedResult:
        """
        Process a user query and return complete results.
        Handles both new queries and follow-up queries that reference previous conversation context.

        Args:
            user_query: The user's query string
            conversation_history: Optional conversation history for context

        Returns:
            ProcessedResult with all components

        Raises:
            DSPyAgentException: If processing fails
        """
        try:
            # Parse conversation history
            parsed_history = self._parse_conversation_history(conversation_history)

            # Step 1: Select the appropriate database and detect follow-up queries
            db_selection_result = self.database_selector.select_database(
                user_query, self.config.es_schema, parsed_history
            )

            # Handle the result based on whether it's a simple database type or enhanced result
            if hasattr(db_selection_result, 'database'):
                # Enhanced result with follow-up detection
                database_type = db_selection_result.database
                is_followup = getattr(db_selection_result, 'is_followup_query', False)
                followup_action = getattr(db_selection_result, 'followup_action', None)
            else:
                # Simple database type result (backward compatibility)
                database_type = db_selection_result
                is_followup = False
                followup_action = None

            logger.info(f"Database selection: {database_type}, Follow-up: {is_followup}, Action: {followup_action}")

            # Handle follow-up queries
            if is_followup and followup_action == 'visualization':
                return self._handle_visualization_followup(user_query, parsed_history, conversation_history)
            elif is_followup and followup_action == 'reuse_data':
                return self._handle_data_reuse_followup(user_query, parsed_history, conversation_history, database_type)

            # Step 2: Execute the query (normal flow or modified query)
            query_result = self.query_executor.execute_query(
                database_type, user_query, self.config.es_schema, self.config.es_instructions, parsed_history
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
            # Parse conversation history
            parsed_history = self._parse_conversation_history(conversation_history)

            # Step 1: Select the appropriate database
            database_type = self.database_selector.select_database(
                user_query, self.config.es_schema, parsed_history
            )

            # Step 2: Execute the query
            query_result = self.query_executor.execute_query(
                database_type, user_query, self.config.es_schema, self.config.es_instructions, parsed_history
            )

            # Step 3: Process results asynchronously
            async for field_name, field_value in self.result_processor.process_results_async(
                query_result, user_query, conversation_history
            ):
                yield field_name, field_value

        except Exception as e:
            logger.error(f"Error in QueryAgent.process_query_async: {e}", exc_info=True)
            yield "error", str(e)

    def _handle_visualization_followup(self, user_query: str, parsed_history: Optional[List[Dict]], conversation_history: Optional[str]) -> ProcessedResult:
        """
        Handle follow-up queries that are requesting visualization of previous data.

        Args:
            user_query: The current visualization request
            parsed_history: Parsed conversation history
            conversation_history: Raw conversation history string

        Returns:
            ProcessedResult with chart generated from previous data
        """
        try:
            logger.info("Handling visualization follow-up query")

            # Extract previous data from conversation history
            previous_data = self._extract_previous_data(parsed_history)
            if not previous_data:
                logger.warning("No previous data found for visualization")
                # Fall back to normal query processing
                return self._fallback_to_normal_query(user_query, parsed_history, conversation_history)

            # Create a mock query result with the previous data
            from core.interfaces import QueryResult, DatabaseType
            query_result = QueryResult(
                database_type=DatabaseType.ELASTIC,  # Default to Elastic
                data=previous_data.get('data', []) if isinstance(previous_data, dict) else [],
                raw_result=previous_data,
                elastic_query=previous_data.get('elastic_query') if isinstance(previous_data, dict) else None
            )

            # Process results with emphasis on chart generation
            processed_result = self.result_processor.process_results(
                query_result, user_query, conversation_history
            )

            logger.info("Successfully processed visualization follow-up")
            return processed_result

        except Exception as e:
            logger.error(f"Error handling visualization follow-up: {e}")
            # Fall back to normal query processing
            return self._fallback_to_normal_query(user_query, parsed_history, conversation_history)

    def _handle_data_reuse_followup(self, user_query: str, parsed_history: Optional[List[Dict]], conversation_history: Optional[str], database_type) -> ProcessedResult:
        """
        Handle follow-up queries that need to reuse previous data with modifications.

        Args:
            user_query: The current query
            parsed_history: Parsed conversation history
            conversation_history: Raw conversation history string
            database_type: Selected database type

        Returns:
            ProcessedResult with reused/modified data
        """
        try:
            logger.info("Handling data reuse follow-up query")

            # Execute the query normally but with conversation context
            # The query executor should handle the reuse logic based on conversation history
            query_result = self.query_executor.execute_query(
                database_type, user_query, self.config.es_schema, self.config.es_instructions, parsed_history
            )

            # Process results
            processed_result = self.result_processor.process_results(
                query_result, user_query, conversation_history
            )

            return processed_result

        except Exception as e:
            logger.error(f"Error handling data reuse follow-up: {e}")
            # Fall back to normal query processing
            return self._fallback_to_normal_query(user_query, parsed_history, conversation_history)

    def _extract_previous_data(self, parsed_history: Optional[List[Dict]]) -> Optional[Dict]:
        """
        Extract the most recent query data from conversation history.

        Args:
            parsed_history: Parsed conversation history

        Returns:
            Previous data dict or None
        """
        if not parsed_history:
            return None

        # Look for the most recent message with query results
        for message in reversed(parsed_history):
            if isinstance(message, dict):
                # Check various possible data fields
                for data_field in ['query_result', 'raw_result', 'data', 'result']:
                    if data_field in message and message[data_field]:
                        logger.info(f"Found previous data in field: {data_field}")
                        return message[data_field]

        logger.warning("No previous data found in conversation history")
        return None

    def _fallback_to_normal_query(self, user_query: str, parsed_history: Optional[List[Dict]], conversation_history: Optional[str]) -> ProcessedResult:
        """
        Fallback to normal query processing when follow-up handling fails.
        """
        logger.info("Falling back to normal query processing")

        # Use default database selection (Elastic as fallback)
        from core.interfaces import DatabaseType
        query_result = self.query_executor.execute_query(
            DatabaseType.ELASTIC, user_query, self.config.es_schema, self.config.es_instructions, parsed_history
        )

        return self.result_processor.process_results(
            query_result, user_query, conversation_history
        )
