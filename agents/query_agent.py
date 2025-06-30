"""Main query agent implementation orchestrating all components."""
import logging
from typing import Optional, List, Dict, Any
import json
import time
import dspy

from core.config import config_manager
from core.exceptions import DSPyAgentException
from core.interfaces import (
    IQueryAgent, IDatabaseSelector, IQueryExecutor, IResultProcessor,
    ProcessedResult, QueryResult, DatabaseType
)
from modules.signatures import (
    QueryWorkflowPlanner, DatabaseSelectionSignature,
    SummarySignature, ChartAxisSelector
)
from services.search_service import convert_json_to_markdown
from util.performance import monitor_performance
from components.chart_generator import generate_chart_from_config

logger = logging.getLogger(__name__)



class QueryAgent(IQueryAgent):
    """Main query agent that orchestrates all components using QueryWorkflowPlanner."""

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

        # Initialize workflow planner
        self.workflow_planner = dspy.Predict(QueryWorkflowPlanner)

        # Initialize signature predictors for direct execution
        self.db_selector = dspy.Predict(DatabaseSelectionSignature)

        # Remove duplicate processors - delegate to injected query_executor instead
        # self.es_processor and self.vector_processor are handled by query_executor

        self.summary_generator = dspy.ChainOfThought(SummarySignature)  # Use ChainOfThought for reasoning

        # Import the chart generation function and use simple Predict instead of complex ReAct
        self.chart_generator = dspy.Predict(ChartAxisSelector)

    def _parse_conversation_history(self, conversation_history: Optional[str]) -> Optional[List[Dict]]:
        """Parse conversation history string to list of dictionaries."""
        if not conversation_history:
            return None

        try:
            # If it's already a list, return as is
            if isinstance(conversation_history, list):
                return conversation_history
            # If it's a string that looks like JSON, parse it
            elif isinstance(conversation_history, str):
                return json.loads(conversation_history)
            else:
                return None
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse conversation history: {conversation_history}, error: {e}")
            return None

    @monitor_performance("query_processing")
    def process_query(self, user_query: str, conversation_history: Optional[str] = None) -> ProcessedResult:
        """
        Process a user query using QueryWorkflowPlanner to orchestrate the workflow.

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

            # Step 1: Plan the workflow using QueryWorkflowPlanner
            workflow_plan = self.workflow_planner(
                user_query=user_query,
                conversation_history=parsed_history
            )

            logger.info(f"Workflow plan: {workflow_plan.workflow_steps}")
            logger.info(f"Expected output: {workflow_plan.expected_final_output}")
            logger.info(f"Plan explanation: {workflow_plan.explanation}")

            # Step 2: Execute the planned workflow
            return self._execute_workflow(workflow_plan, user_query, parsed_history, conversation_history)

        except Exception as e:
            logger.error(f"Error in QueryAgent.process_query: {e}", exc_info=True)
            raise DSPyAgentException(f"Query processing failed: {e}") from e

    def _execute_workflow(self, workflow_plan, user_query: str, parsed_history: Optional[List[Dict]], conversation_history: Optional[str]) -> ProcessedResult:
        """
        Execute the planned workflow steps sequentially.

        Args:
            workflow_plan: The workflow plan from QueryWorkflowPlanner
            user_query: The user's query string
            parsed_history: Parsed conversation history
            conversation_history: Raw conversation history string

        Returns:
            ProcessedResult with all components
        """
        try:
            # Initialize workflow state
            workflow_state = {
                'database_type': None,
                'query_result': None,
                'summary': None,
                'chart_config': None,
                'chart_html': None,
                'json_data': None,
                'data_markdown': None,
                'elastic_query': None,  # Store the generated ES query
                'workflow_plan': workflow_plan  # Store the workflow plan for reference
            }

            # Check if this is a follow-up visualization request
            is_followup_viz = getattr(workflow_plan, 'is_followup_visualization', False)

            if is_followup_viz:
                # Extract previous data from conversation history for visualization
                previous_data = self._extract_previous_query_data(parsed_history)
                if previous_data:
                    workflow_state['json_data'] = previous_data
                    workflow_state['query_result'] = QueryResult(
                        database_type=DatabaseType.ELASTIC,  # Default, actual type doesn't matter for visualization
                        data=json.loads(previous_data) if isinstance(previous_data, str) else previous_data,
                        raw_result=previous_data
                    )
                    logger.info("Using previous query data for follow-up visualization")
                else:
                    logger.warning("Follow-up visualization requested but no previous data found")

            # Execute workflow steps in order
            for step in workflow_plan.workflow_steps:
                logger.info(f"Executing workflow step: {step}")

                if step == 'DatabaseSelectionSignature':
                    workflow_state = self._execute_database_selection(workflow_state, user_query, parsed_history)

                elif step == 'EsQueryProcessor':
                    workflow_state = self._execute_es_query(workflow_state, user_query, parsed_history)
                    # ALWAYS push markdown to frontend when ES query completes
                    if workflow_state.get('data_markdown'):
                        logger.info("📤 Markdown elastic result being pushed to frontend (sync)")

                elif step == 'VectorQueryProcessor':
                    workflow_state = self._execute_vector_query(workflow_state, user_query, parsed_history)
                    # ALWAYS push markdown to frontend when Vector query completes
                    if workflow_state.get('data_markdown'):
                        logger.info("📤 Markdown vector result being pushed to frontend (sync)")

                elif step == 'SummarySignature':
                    workflow_state = self._execute_summary_generation(workflow_state, user_query, conversation_history)

                elif step == 'ChartAxisSelector':
                    workflow_state = self._execute_chart_generation(workflow_state, user_query, parsed_history)

                else:
                    logger.warning(f"Unknown workflow step: {step}")

            # If database was selected but no query processor was explicitly called, route based on database type
            if workflow_state.get('database_type') and not workflow_state.get('query_result'):
                logger.info(f"Database selected ({workflow_state['database_type']}) but no query processor called. Auto-routing...")

                if workflow_state['database_type'] == DatabaseType.VECTOR:
                    logger.info("Auto-routing to VectorQueryProcessor")
                    workflow_state = self._execute_vector_query(workflow_state, user_query, parsed_history)
                elif workflow_state['database_type'] == DatabaseType.ELASTIC:
                    logger.info("Auto-routing to EsQueryProcessor")
                    workflow_state = self._execute_es_query(workflow_state, user_query, parsed_history)

            # Create final ProcessedResult
            return ProcessedResult(
                query_result=workflow_state['query_result'] or QueryResult(
                    database_type=DatabaseType.ELASTIC,
                    data=[],
                    raw_result={}
                ),
                summary=workflow_state['summary'],
                chart_config=workflow_state['chart_config'],
                chart_html=workflow_state['chart_html']
            )

        except Exception as e:
            logger.error(f"Error executing workflow: {e}", exc_info=True)
            # Fallback to original implementation
            return self._fallback_to_original_process_query(user_query, parsed_history, conversation_history)

    def _execute_database_selection(self, workflow_state: Dict[str, Any], user_query: str, parsed_history: Optional[List[Dict]]) -> Dict[str, Any]:
        """Execute database selection step."""
        try:
            db_result = self.db_selector(
                user_query=user_query,
                es_schema=self.config.es_schema,
                conversation_history=parsed_history
            )

            # Map string result to DatabaseType enum
            if db_result.database == 'Elastic':
                workflow_state['database_type'] = DatabaseType.ELASTIC
            elif db_result.database == 'Vector':
                workflow_state['database_type'] = DatabaseType.VECTOR
            else:
                workflow_state['database_type'] = DatabaseType.ELASTIC  # Default fallback

            logger.info(f"Selected database: {workflow_state['database_type']}")
            return workflow_state

        except Exception as e:
            logger.error(f"Error in database selection: {e}")
            workflow_state['database_type'] = DatabaseType.ELASTIC  # Default fallback
            return workflow_state

    def _execute_es_query(self, workflow_state: Dict[str, Any], user_query: str, parsed_history: Optional[List[Dict]],
                         session_id: Optional[str] = None, message_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute Elasticsearch query step using LLM signatures."""
        try:
            logger.info(f"Executing Elasticsearch query: {user_query}")

            # Pass the follow-up visualization flag to the workflow state for the signature to use
            is_followup_viz = getattr(workflow_state.get('workflow_plan', {}), 'is_followup_visualization', False)
            workflow_state['is_followup_visualization'] = is_followup_viz

            # Use the query executor with LLM signatures to handle everything
            query_result = self.query_executor.execute_query(
                DatabaseType.ELASTIC, user_query, self.config.es_schema,
                self.config.es_instructions, parsed_history
            )

            workflow_state['query_result'] = query_result
            workflow_state['json_data'] = json.dumps(query_result.data)

            # Store the generated Elasticsearch query for history
            if hasattr(query_result, 'elastic_query') and query_result.elastic_query:
                workflow_state['elastic_query'] = query_result.elastic_query

            logger.info(f"Query result: {len(query_result.data)} records, session_id: {session_id}, message_id: {message_id}")

            # Store ES query in Redis if we have session and message IDs
            if session_id and message_id and hasattr(query_result, 'elastic_query') and query_result.elastic_query:
                from util.redis_client import store_message_query
                store_success = store_message_query(session_id, message_id, query_result.elastic_query)
                if store_success:
                    logger.info(f"Stored ES query for session {session_id}, message {message_id}")
                else:
                    logger.warning(f"Failed to store ES query for session {session_id}, message {message_id}")

            # Generate markdown formatted data
            workflow_state['data_markdown'] = convert_json_to_markdown(query_result.data, "Elasticsearch Query Results")

            logger.info("Elasticsearch query executed successfully")
            return workflow_state

        except Exception as e:
            logger.error(f"Error in Elasticsearch query: {e}")
            return workflow_state

    def _execute_vector_query(self, workflow_state: Dict[str, Any], user_query: str, parsed_history: Optional[List[Dict]]) -> Dict[str, Any]:
        """Execute vector query step by directly calling execute_vector_query."""
        try:
            from services.search_service import execute_vector_query

            logger.info(f"Executing vector search for: {user_query}")

            # Simple direct call to execute_vector_query
            query_result = execute_vector_query({'query_text': user_query})

            if query_result.get('error'):
                logger.error(f"Vector search failed: {query_result['error']}")
                workflow_state['query_result'] = QueryResult(
                    database_type=DatabaseType.VECTOR,
                    data=[],
                    raw_result={"error": query_result['error']}
                )
                workflow_state['json_data'] = json.dumps([])
            else:
                # Extract data from the vector search result
                result_data = query_result.get('result', {})
                hits = result_data.get('hits', {}).get('hits', [])
                data = [hit.get('_source', {}) for hit in hits]

                workflow_state['query_result'] = QueryResult(
                    database_type=DatabaseType.VECTOR,
                    data=data,
                    raw_result=result_data
                )
                workflow_state['json_data'] = json.dumps(data)
                logger.info(f"Vector search successful: {len(data)} chunks retrieved")

            # Generate markdown formatted data
            workflow_state['data_markdown'] = convert_json_to_markdown(
                workflow_state['query_result'].data,
                "Vector Search Results"
            )

            return workflow_state

        except Exception as e:
            logger.error(f"Error in vector query execution: {e}")
            workflow_state['query_result'] = QueryResult(
                database_type=DatabaseType.VECTOR,
                data=[],
                raw_result={"error": str(e)}
            )
            workflow_state['json_data'] = json.dumps([])
            workflow_state['data_markdown'] = "# Vector Search Results\n\nError occurred during vector search."
            return workflow_state

    def _execute_summary_generation(self, workflow_state: Dict[str, Any], user_query: str, conversation_history: Optional[str]) -> Dict[str, Any]:
        """Execute summary generation step."""
        try:
            logger.info("🔄 Starting summary generation")

            summary_result = self.summary_generator(
                user_query=user_query,
                conversation_history=self._parse_conversation_history(conversation_history),
                json_results=workflow_state.get('json_data', '')
            )

            workflow_state['summary'] = summary_result.summary
            logger.info("✅ Summary generation completed successfully")
            return workflow_state

        except Exception as e:
            logger.error(f"❌ Summary generation failed: {e}")
            return workflow_state

    def _execute_chart_generation(self, workflow_state: Dict[str, Any], user_query: str, parsed_history: Optional[List[Dict]]) -> Dict[str, Any]:
        """Execute chart generation step - simplified approach."""
        try:
            logger.info("🔄 Starting chart generation")

            json_data = workflow_state.get('json_data', '{}')
            logger.info(f"📊 Data available for charting: {len(str(json_data))} characters")

            # Step 1: Use DSPy to determine chart parameters
            chart_result = self.chart_generator(
                json_data=json_data,
                user_query=user_query,
                conversation_history=parsed_history
            )

            logger.info(f"✅ Chart parameters determined: {chart_result.chart_type}")

            # Step 2: Call the simple chart generation function directly
            from components.chart_generator import generate_highchart_config

            chart_config = generate_highchart_config(
                chart_type=chart_result.chart_type,
                x_axis_column=chart_result.x_axis_column,
                y_axis_column=chart_result.y_axis_column,
                x_axis_label=chart_result.x_axis_label,
                y_axis_label=chart_result.y_axis_label,
                chart_title=chart_result.chart_title,
                json_data=json_data,
                z_axis_column=getattr(chart_result, 'z_axis_column', None),
                z_axis_label=getattr(chart_result, 'z_axis_label', None)
            )

            # Step 3: Store chart config results (no HTML generation)
            workflow_state['chart_config'] = chart_config
            # Remove chart_html generation - only keep JSON config
            workflow_state['chart_html'] = None

            logger.info("✅ Chart generation completed successfully")
            return workflow_state

        except Exception as e:
            logger.error(f"❌ Chart generation failed: {e}")
            workflow_state['chart_config'] = None
            workflow_state['chart_html'] = None
            return workflow_state

    def _fallback_to_original_process_query(self, user_query: str, parsed_history: Optional[List[Dict]], conversation_history: Optional[str]) -> ProcessedResult:
        """Fallback to the original process_query implementation."""
        logger.info("Falling back to original process_query implementation")

        # Use the existing components for fallback
        database_type = self.database_selector.select_database(
            user_query, self.config.es_schema, parsed_history
        )

        # Handle enhanced result format
        if hasattr(database_type, 'database'):
            database_type = getattr(database_type, 'database')
            if database_type == 'Elastic':
                database_type = DatabaseType.ELASTIC
            elif database_type == 'Vector':
                database_type = DatabaseType.VECTOR

        query_result = self.query_executor.execute_query(
            database_type, user_query, self.config.es_schema, self.config.es_instructions, parsed_history
        )

        return self.result_processor.process_results(
            query_result, user_query, conversation_history
        )

    @monitor_performance("query_processing_async")
    async def process_query_async(self, user_query: str, conversation_history: Optional[str] = None,
                                session_id: Optional[str] = None, message_id: Optional[str] = None):
        """
        Process query asynchronously, yielding results as they become available.
        This implementation uses the QueryWorkflowPlanner to orchestrate the workflow.

        Args:
            user_query: The user's query string
            conversation_history: Optional conversation history for context
            session_id: Optional session identifier for storing ES queries
            message_id: Optional message identifier for storing ES queries

        Yields:
            Tuples of (field_name, field_value) as results are generated

        Raises:
            DSPyAgentException: If processing fails
        """
        try:
            # Parse conversation history
            parsed_history = self._parse_conversation_history(conversation_history)

            # Step 1: Plan the workflow using QueryWorkflowPlanner
            workflow_plan = self.workflow_planner(
                user_query=user_query,
                conversation_history=parsed_history
            )

            logger.info(f"Workflow plan: {workflow_plan.workflow_steps}")
            yield "workflow_plan", workflow_plan.workflow_steps
            yield "expected_output", workflow_plan.expected_final_output
            yield "explanation", workflow_plan.explanation

            # Step 2: Execute the planned workflow asynchronously
            async for field_name, field_value in self._execute_workflow_async(
                workflow_plan, user_query, parsed_history, conversation_history, session_id, message_id
            ):
                yield field_name, field_value

        except Exception as e:
            logger.error(f"Error in QueryAgent.process_query_async: {e}", exc_info=True)
            yield "error", str(e)

    async def _execute_workflow_async(self, workflow_plan, user_query: str, parsed_history: Optional[List[Dict]], conversation_history: Optional[str], session_id: Optional[str] = None, message_id: Optional[str] = None):
        """
        Execute the planned workflow steps sequentially with async yielding.
        Results are yielded immediately when ready, without waiting for subsequent steps.

        Args:
            workflow_plan: The workflow plan from QueryWorkflowPlanner
            user_query: The user's query string
            parsed_history: Parsed conversation history
            conversation_history: Raw conversation history string
            session_id: Optional session identifier for storing ES queries
            message_id: Optional message identifier for storing ES queries

        Yields:
            Tuples of (field_name, field_value) as results are generated
        """
        try:
            # Initialize workflow state
            workflow_state = {
                'database_type': None,
                'query_result': None,
                'summary': None,
                'chart_config': None,
                'chart_html': None,
                'json_data': None,
                'data_markdown': None
            }

            # Check if this is a follow-up visualization request
            is_followup_viz = getattr(workflow_plan, 'is_followup_visualization', False)

            if is_followup_viz:
                # Extract previous data from conversation history for visualization
                previous_data = self._extract_previous_query_data(parsed_history)
                if previous_data:
                    workflow_state['json_data'] = previous_data
                    workflow_state['query_result'] = QueryResult(
                        database_type=DatabaseType.ELASTIC,  # Default, actual type doesn't matter for visualization
                        data=json.loads(previous_data) if isinstance(previous_data, str) else previous_data,
                        raw_result=previous_data
                    )
                    logger.info("Using previous query data for follow-up visualization")

            # Execute workflow steps in order
            for step in workflow_plan.workflow_steps:
                logger.info(f"Executing workflow step: {step}")
                yield "current_step", step

                if step == 'DatabaseSelectionSignature':
                    workflow_state = self._execute_database_selection(workflow_state, user_query, parsed_history)
                    yield "database_selected", workflow_state['database_type'].value if workflow_state['database_type'] else None

                elif step == 'EsQueryProcessor':
                    # Pass session_id and message_id to ES query execution
                    es_start = time.time()
                    logger.info(f"🚀 [TIMING] Starting EsQueryProcessor step at {es_start}")

                    workflow_state = self._execute_es_query(workflow_state, user_query, parsed_history, session_id, message_id)

                    es_end = time.time()
                    logger.info(f"🏁 [TIMING] EsQueryProcessor step completed in {(es_end - es_start) * 1000:.2f}ms")

                    # Immediately yield ALL ES data when query completes - don't wait for summary
                    if workflow_state.get('query_result'):
                        yield_start = time.time()

                        # Yield raw JSON data first
                        if workflow_state['json_data']:
                            yield "data", json.loads(workflow_state['json_data']) if isinstance(workflow_state['json_data'], str) else workflow_state['json_data']
                            logger.info("🚀 [TIMING] ES query raw data yielded immediately to frontend")

                        # Yield markdown formatted data
                        if workflow_state.get('data_markdown'):
                            yield "data_markdown", workflow_state['data_markdown']
                            logger.info("🚀 [TIMING] ES query markdown data yielded immediately to frontend")

                        # Yield database type for frontend reference
                        yield "database", workflow_state['query_result'].database_type.value

                        yield_end = time.time()
                        logger.info(f"✅ [TIMING] ES data yielding completed in {(yield_end - yield_start) * 1000:.2f}ms - ES data pushed to frontend before summary processing")

                elif step == 'VectorQueryProcessor':
                    workflow_state = self._execute_vector_query(workflow_state, user_query, parsed_history)
                    # Immediately yield markdown data when Vector query completes - don't wait for summary
                    if workflow_state.get('data_markdown'):
                        yield "data_markdown", workflow_state['data_markdown']
                        logger.info("Vector query markdown data yielded immediately to frontend")

                elif step == 'SummarySignature':
                    # Summary is processed separately and yielded when ready
                    workflow_state = self._execute_summary_generation(workflow_state, user_query, conversation_history)
                    if workflow_state['summary']:
                        yield "summary", workflow_state['summary']
                        logger.info("Summary yielded separately to frontend")

                elif step == 'ChartAxisSelector':
                    workflow_state = self._execute_chart_generation(workflow_state, user_query, parsed_history)
                    if workflow_state['chart_config']:
                        yield "chart_config", workflow_state['chart_config']
                    if workflow_state['chart_html']:
                        yield "chart_html", workflow_state['chart_html']
                        logger.info("Chart data yielded to frontend")

                else:
                    logger.warning(f"Unknown workflow step: {step}")
                    yield "warning", f"Unknown workflow step: {step}"

            # Yield final completed status
            yield "completed", True

        except Exception as e:
            logger.error(f"Error executing workflow async: {e}", exc_info=True)
            yield "error", str(e)

    def _extract_previous_query_data(self, parsed_history: Optional[List[Dict]]) -> Optional[str]:
        """
        Extract the most recent query data from conversation history for follow-up visualizations.

        Args:
            parsed_history: Parsed conversation history

        Returns:
            JSON string of previous query data or None if not found
        """
        if not parsed_history:
            return None

        # Look for the most recent message with query results
        for message in reversed(parsed_history):
            if isinstance(message, dict):
                # Check for various possible data fields that might contain query results
                for data_field in ['data_json', 'json_data', 'query_result', 'raw_result', 'result', 'data']:
                    if data_field in message and message[data_field]:
                        data = message[data_field]
                        # If it's already a string, return as is
                        if isinstance(data, str):
                            logger.info(f"Found previous query data in field: {data_field}")
                            return data
                        # If it's a dict, convert to JSON string
                        elif isinstance(data, dict):
                            logger.info(f"Found previous query data in field: {data_field}, converting to JSON")
                            return json.dumps(data)

                # Also check if the message itself contains query result structure
                if 'hits' in message:
                    logger.info("Found previous query data in message structure")
                    return json.dumps(message)

        logger.warning("No previous query data found in conversation history")
        return None

    def _extract_previous_elasticsearch_query(self, parsed_history: Optional[List[Dict]]) -> Optional[Dict]:
        """
        Extract the most recent Elasticsearch query from conversation history.

        Args:
            parsed_history: Parsed conversation history

        Returns:
            Dictionary representing the Elasticsearch query or None if not found
        """
        if not parsed_history:
            return None

        # Look for the most recent message with an Elasticsearch query
        for message in reversed(parsed_history):
            if isinstance(message, dict):
                # Check for the 'elastic_query' field which contains the original query
                if 'elastic_query' in message and message['elastic_query']:
                    query = message['elastic_query']
                    logger.info("Found previous Elasticsearch query in message structure")
                    return query

        logger.warning("No previous Elasticsearch query found in conversation history")
        return None

