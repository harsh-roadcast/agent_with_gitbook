"""Query execution implementation using DSPy agents."""
import json
import logging
import time
from typing import Any, Optional, List, Dict

import dspy

from core.exceptions import QueryExecutionError, DataParsingError
from core.interfaces import IQueryExecutor, DatabaseType, QueryResult
from modules.keyword_extractor import keyword_extractor
from modules.signatures import EsQueryProcessor, VectorQueryProcessor
from services.search_service import execute_query, execute_vector_query
from util.performance import monitor_performance

logger = logging.getLogger(__name__)


class DSPyQueryExecutor(IQueryExecutor):
    """DSPy-based query executor implementation."""

    def __init__(self):
        """Initialize the query executor with DSPy agents."""
        self.vector_agent = dspy.Predict(VectorQueryProcessor)  # Changed from ReAct to Predict since we're calling execute_vector_query manually
        # Replace ReAct with simple Predict for ES queries - ReAct is causing 60+ second delays
        self.es_agent = dspy.Predict(EsQueryProcessor)

    @monitor_performance("query_execution")
    def execute_query(self, database_type: DatabaseType, user_query: str, schema: List[Dict[str, Any]] | None,
                      instructions: str | None, conversation_history: Optional[List[Dict]] = None,
                      detailed_analysis: Optional[str] = None, vector_db_index: str = None,
                      context_summary: Optional[str] = None) -> QueryResult:
        """
        Execute query on the specified database.

        Args:
            :param context_summary:
            :param database_type:
            :param user_query:
            :param schema:
            :param conversation_history:
            :param instructions:
            :param detailed_analysis:
            :param vector_db_index:

        Returns:
            QueryResult with parsed data and metadata

        Raises:
            QueryExecutionError: If query execution fails

        """
        try:
            if database_type == DatabaseType.VECTOR:
                return self._execute_vector_query(user_query, conversation_history, detailed_analysis, vector_db_index, context_summary)
            elif database_type == DatabaseType.ELASTIC:
                return self._execute_elastic_query(user_query, schema, instructions, conversation_history, detailed_analysis, context_summary)
            else:
                raise QueryExecutionError(f"Unsupported database type: {database_type}")

        except Exception as e:
            logger.error(f"Error executing query on {database_type}: {e}", exc_info=True)
            raise QueryExecutionError(f"Failed to execute query: {e}") from e

    def _execute_vector_query(self, user_query: str, conversation_history: Optional[List[Dict]] = None,
                             detailed_analysis: Optional[str] = None, vector_db_index: str = None,
                             context_summary: Optional[str] = None) -> QueryResult:
        """Execute vector search query."""
        logger.info(f"Processing Vector query for: {user_query}")

        # Use the VectorQueryProcessor to generate proper search string
        result = self.vector_agent(
            user_query=user_query,
            detailed_analysis=detailed_analysis or "No detailed analysis provided",  # Fixed parameter name
            context_summary=context_summary or "No context summary available"  # Added missing required parameter
        )
        print(f"🤖 Generated vector query result: {result}")
        # Extract the generated vector query string and pass to execute_vector_query
        vector_query_string = result.vector_query if hasattr(result, 'vector_query') else user_query
        print(f"🔍 Generated vector query string: {vector_query_string}")
        # Call execute_vector_query with proper parameters
        try:
            # Extract keywords for hybrid search
            keywords = keyword_extractor.extract_keywords(vector_query_string)
            logger.info(f"Extracted {len(keywords)} keywords for vector search: {keywords}")
            
            vector_search_params = {
                'query_text': vector_query_string,
                'index': vector_db_index,  # Your vector index
                'size': 25,
                'keywords': keywords  # Add keywords for hybrid search
            }

            # Execute the actual vector search
            vector_result = execute_vector_query(vector_search_params)

            if vector_result.get('success'):
                # Extract the actual response data from ObjectApiResponse (same as ES handling)
                es_response = vector_result['result']

                # Convert ObjectApiResponse to dict if needed
                if hasattr(es_response, 'body'):
                    response_dict = es_response.body
                elif hasattr(es_response, 'to_dict'):
                    response_dict = es_response.to_dict()
                else:
                    # If it's already a dict, use it directly
                    response_dict = dict(es_response)

                # Update the result with actual search data
                result.data_json = json.dumps(response_dict)
                logger.info(f"✅ Vector search completed successfully with query: '{vector_query_string}'")
                logger.info(f"✅ Successfully extracted {len(response_dict.get('hits', {}).get('hits', []))} vector search results")
            else:
                logger.error(f"Vector search failed: {vector_result}")
                result.data_json = json.dumps({"hits": {"hits": []}})

        except Exception as e:
            logger.error(f"Error executing vector search: {e}", exc_info=True)
            result.data_json = json.dumps({"hits": {"hits": []}})

        return self._parse_query_result(result, DatabaseType.VECTOR)

    def _execute_elastic_query(self, user_query: str, schema: List[Dict[str, Any]], instructions: str, conversation_history: Optional[List[Dict]] = None, detailed_analysis: Optional[str] = None, context_summary: Optional[str] = None) -> QueryResult:
        """Execute Elasticsearch query."""
        start_time = time.time()
        logger.info(f"🚀 [TIMING] Starting DSPy ES agent processing at {start_time}")
        logger.info(f"Processing Elasticsearch query for: {user_query}")

        agent_start = time.time()
        # Use Predict to generate query parameters
        result = self.es_agent(
            user_query=user_query,
            detailed_analysis=detailed_analysis or user_query,  # Use actual detailed_analysis or fallback to user_query
            context_summary=context_summary or "No context summary available",  # Added missing required parameter
            es_schema=schema,
            es_instructions=instructions
        )
        agent_end = time.time()
        logger.info(f"🤖 [TIMING] DSPy ES agent completed in {(agent_end - agent_start) * 1000:.2f}ms")

        # Manually execute the query since we're not using ReAct anymore
        exec_start = time.time()
        try:
            # Extract query and index from the result
            elastic_query = result.elastic_query
            index_name = result.elastic_index  # Changed from index_name to elastic_index

            # Add fallback if index_name is None or empty
            if not index_name or index_name in [None, '', 'None']:
                logger.warning(f"⚠️  Index name is missing or empty: '{index_name}', using fallback")
                # Try common index names as fallback
                index_name = "docling_documents"  # or whatever your main index is
                logger.info(f"🔄 Using fallback index: {index_name}")

            logger.info(f"📝 Generated query for index '{index_name}': {elastic_query}")

            # Call execute_query manually
            query_result = execute_query(elastic_query, index_name)

            if query_result.get('success'):
                # Extract clean documents directly from response
                clean_documents = query_result['result']  # This is now a list of clean documents
                total_count = query_result.get('total_count', len(clean_documents))

                # Create a compatible response structure for data_json
                response_dict = {
                    'hits': {
                        'hits': [{'_source': doc} for doc in clean_documents],  # Wrap documents in _source for compatibility
                        'total': {'value': total_count}
                    }
                }

                # Manually populate data_json with the extracted dict
                result.data_json = json.dumps(response_dict)
                logger.info(f"✅ Successfully extracted {len(clean_documents)} clean records from ES response")
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

            # Get elastic query and index name directly from result - LLM always provides these
            elastic_query = result.elastic_query if hasattr(result, 'elastic_query') else None
            index_name = result.elastic_index if hasattr(result, 'elastic_index') else None

            return QueryResult(
                database_type=database_type,
                data=data,
                raw_result=data_json,
                elastic_query=elastic_query,
                index_name=index_name
            )

        except json.JSONDecodeError as e:
            raise DataParsingError(f"Could not parse result data: {e}") from e
        except Exception as e:
            raise DataParsingError(f"Error processing result data: {e}") from e
