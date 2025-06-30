"""Query execution implementation using DSPy agents."""
import json
import logging
import time
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
        # Replace ReAct with simple Predict for ES queries - ReAct is causing 60+ second delays
        self.es_agent = dspy.Predict(EsQueryProcessor)

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
        start_time = time.time()
        logger.info(f"🚀 [TIMING] Starting DSPy ES agent processing at {start_time}")
        logger.info(f"Processing Elasticsearch query for: {user_query}")

        agent_start = time.time()
        # Use Predict to generate query parameters
        result = self.es_agent(
            user_query=user_query,
            es_schema=schema,
            es_instructions=instructions,
            conversation_history=conversation_history
        )
        agent_end = time.time()
        logger.info(f"🤖 [TIMING] DSPy ES agent completed in {(agent_end - agent_start) * 1000:.2f}ms")

        # Manually execute the query since we're not using ReAct anymore
        exec_start = time.time()
        try:
            # Extract query and index from the result
            elastic_query = result.elastic_query
            index_name = result.index_name

            logger.info(f"📝 Generated query for index '{index_name}': {elastic_query}")

            # Call execute_query manually
            query_result = execute_query(elastic_query, index_name)

            if query_result.get('success'):
                # Extract the actual response data from ObjectApiResponse
                es_response = query_result['result']

                # Convert ObjectApiResponse to dict if needed
                if hasattr(es_response, 'body'):
                    response_dict = es_response.body
                elif hasattr(es_response, 'to_dict'):
                    response_dict = es_response.to_dict()
                else:
                    # If it's already a dict, use it directly
                    response_dict = dict(es_response)

                # Manually populate data_json with the extracted dict
                result.data_json = json.dumps(response_dict)
                logger.info(f"✅ Successfully extracted {len(response_dict.get('hits', {}).get('hits', []))} records from ES response")
            else:
                logger.error(f"Query execution failed: {query_result}")
                result.data_json = json.dumps({"hits": {"hits": []}})

        except Exception as e:
            logger.error(f"Error executing query manually: {e}", exc_info=True)
            result.data_json = json.dumps({"hits": {"hits": []}})

        exec_end = time.time()
        logger.info(f"⚡ [TIMING] Manual query execution completed in {(exec_end - exec_start) * 1000:.2f}ms")

        parse_start = time.time()
        parsed_result = self._parse_query_result(result, DatabaseType.ELASTIC)
        parse_end = time.time()

        logger.info(f"📊 [TIMING] Result parsing completed in {(parse_end - parse_start) * 1000:.2f}ms")

        end_time = time.time()
        logger.info(f"🏁 [TIMING] Total _execute_elastic_query took {(end_time - start_time) * 1000:.2f}ms")

        return parsed_result

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
