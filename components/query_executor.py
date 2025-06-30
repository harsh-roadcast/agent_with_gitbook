"""Query execution implementation using DSPy agents."""
import json
import logging
from typing import Any, Optional, List, Dict

import dspy

from core.exceptions import QueryExecutionError, DataParsingError
from core.interfaces import IQueryExecutor, DatabaseType, QueryResult
from modules.signatures import EsQueryProcessor, VectorQueryProcessor
from services.search_service import execute_query, execute_vector_query
from util.performance import monitor_performance

logger = logging.getLogger(__name__)


class DSPyQueryExecutor(IQueryExecutor):
    """DSPy-based query executor implementation."""

    def __init__(self):
        """Initialize the query executor with DSPy agents."""
        self.vector_agent = dspy.ReAct(VectorQueryProcessor, tools=[execute_vector_query])
        self.es_agent = dspy.ReAct(EsQueryProcessor, tools=[execute_query])

    @monitor_performance("query_execution")
    def execute_query(self, database_type: DatabaseType, user_query: str, schema: str, instructions: str, conversation_history: Optional[List[Dict]] = None) -> QueryResult:
        """
        Execute query on the specified database.

        Args:
            database_type: Type of database to query
            user_query: The user's query string
            schema: Database schema information
            instructions: Query execution instructions
            conversation_history: Optional conversation history for context

        Returns:
            QueryResult with parsed data and metadata

        Raises:
            QueryExecutionError: If query execution fails
        """
        try:
            if database_type == DatabaseType.VECTOR:
                return self._execute_vector_query(user_query, schema, instructions, conversation_history)
            elif database_type == DatabaseType.ELASTIC:
                return self._execute_elastic_query(user_query, schema, instructions, conversation_history)
            else:
                raise QueryExecutionError(f"Unsupported database type: {database_type}")

        except Exception as e:
            logger.error(f"Error executing query on {database_type}: {e}", exc_info=True)
            raise QueryExecutionError(f"Failed to execute query: {e}") from e

    def _execute_vector_query(self, user_query: str, schema: str, instructions: str, conversation_history: Optional[List[Dict]] = None) -> QueryResult:
        """Execute vector search query."""
        logger.info(f"Processing Vector query for: {user_query}")

        result = self.vector_agent(
            user_query=user_query,
            es_schema=schema,
            es_instructions=instructions,
            conversation_history=conversation_history
        )

        return self._parse_query_result(result, DatabaseType.VECTOR)

    def _execute_elastic_query(self, user_query: str, schema: str, instructions: str, conversation_history: Optional[List[Dict]] = None) -> QueryResult:
        """Execute Elasticsearch query."""
        logger.info(f"Processing Elasticsearch query for: {user_query}")

        result = self.es_agent(
            user_query=user_query,
            es_schema=schema,
            es_instructions=instructions,
            conversation_history=conversation_history
        )

        return self._parse_query_result(result, DatabaseType.ELASTIC)

    def _parse_query_result(self, result: Any, database_type: DatabaseType) -> QueryResult:
        """Parse query result into standardized format."""

        try:
            if not hasattr(result, 'data_json'):
                raise DataParsingError("Result missing data_json attribute")

            # Parse JSON data
            if isinstance(result.data_json, str):
                data_json = json.loads(result.data_json)
            else:
                data_json = result.data_json

            # Extract source data
            try:
                data = [item['_source'] for item in data_json['hits']['hits']]
            except (KeyError, TypeError) as e:
                logger.warning(f"Could not extract source data: {e}")
                data = []

            # Get elastic query if available
            elastic_query = getattr(result, 'elastic_query', None)

            return QueryResult(
                database_type=database_type,
                data=data,
                raw_result=data_json,
                elastic_query=elastic_query
            )

        except json.JSONDecodeError as e:
            raise DataParsingError(f"Could not parse result data: {e}") from e
        except Exception as e:
            raise DataParsingError(f"Error processing result data: {e}") from e
