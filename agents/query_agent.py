"""Main query agent implementation orchestrating all components."""
import logging
from typing import Optional, List, Dict
import json
import dspy

from core.config import config_manager
from core.exceptions import DSPyAgentException
from core.interfaces import (
    IQueryAgent, IDatabaseSelector, IQueryExecutor, IResultProcessor,
    ProcessedResult, QueryResult, DatabaseType
)
from modules.signatures import (
    QueryWorkflowPlanner, DatabaseSelectionSignature, EsQueryProcessor,
    VectorQueryProcessor, SummarySignature, ChartAxisSelector
)
from services.search_service import execute_query, execute_vector_query, convert_json_to_markdown
from util.performance import monitor_performance

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

        # Configure ReAct processors with tools for function calling
        self.es_processor = dspy.ReAct(EsQueryProcessor, tools=[execute_query, convert_json_to_markdown])
        self.vector_processor = dspy.ReAct(VectorQueryProcessor, tools=[execute_vector_query])

        self.summary_generator = dspy.ChainOfThought(SummarySignature)  # Use ChainOfThought for reasoning
        self.chart_generator = dspy.Predict(ChartAxisSelector)

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
                else:
                    logger.warning("Follow-up visualization requested but no previous data found")

            # Execute workflow steps in order
            for step in workflow_plan.workflow_steps:
                logger.info(f"Executing workflow step: {step}")

                if step == 'DatabaseSelectionSignature':
                    workflow_state = self._execute_database_selection(workflow_state, user_query, parsed_history)

                elif step == 'EsQueryProcessor':
                    workflow_state = self._execute_es_query(workflow_state, user_query, parsed_history)

                elif step == 'VectorQueryProcessor':
                    workflow_state = self._execute_vector_query(workflow_state, user_query, parsed_history)

                elif step == 'SummarySignature':
                    workflow_state = self._execute_summary_generation(workflow_state, user_query, conversation_history)

                elif step == 'ChartAxisSelector':
                    workflow_state = self._execute_chart_generation(workflow_state, user_query, parsed_history)

                else:
                    logger.warning(f"Unknown workflow step: {step}")

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

    def _execute_database_selection(self, workflow_state: Dict, user_query: str, parsed_history: Optional[List[Dict]]) -> Dict:
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

    def _execute_es_query(self, workflow_state: Dict, user_query: str, parsed_history: Optional[List[Dict]]) -> Dict:
        """Execute Elasticsearch query step."""
        try:
            es_result = self.es_processor(
                user_query=user_query,
                es_schema=self.config.es_schema,
                conversation_history=parsed_history,
                es_instructions=self.config.es_instructions
            )

            # Parse the JSON result for data processing
            raw_data = json.loads(es_result.data_json) if es_result.data_json else {}

            # Convert to QueryResult format
            workflow_state['query_result'] = QueryResult(
                database_type=DatabaseType.ELASTIC,
                data=raw_data,
                raw_result=es_result.data_json,
                elastic_query=es_result.elastic_query
            )
            workflow_state['json_data'] = es_result.data_json

            # Generate markdown formatted data if not provided by the processor
            if hasattr(es_result, 'data_markdown') and es_result.data_markdown:
                workflow_state['data_markdown'] = es_result.data_markdown
            else:
                # Fallback: convert JSON to markdown using our utility function
                workflow_state['data_markdown'] = convert_json_to_markdown(raw_data, "Elasticsearch Query Results")

            logger.info("Elasticsearch query executed successfully")
            return workflow_state

        except Exception as e:
            logger.error(f"Error in Elasticsearch query: {e}")
            # Fallback to using existing query executor
            if workflow_state.get('database_type'):
                workflow_state['query_result'] = self.query_executor.execute_query(
                    workflow_state['database_type'], user_query, self.config.es_schema,
                    self.config.es_instructions, parsed_history
                )
                workflow_state['json_data'] = json.dumps(workflow_state['query_result'].data)
                # Generate markdown for fallback data
                workflow_state['data_markdown'] = convert_json_to_markdown(
                    workflow_state['query_result'].data, "Elasticsearch Query Results"
                )
            return workflow_state

    def _execute_vector_query(self, workflow_state: Dict, user_query: str, parsed_history: Optional[List[Dict]]) -> Dict:
        """Execute vector query step."""
        try:
            vector_result = self.vector_processor(
                user_query=user_query,
                es_schema=self.config.es_schema,
                conversation_history=parsed_history,
                es_instructions=self.config.es_instructions
            )

            # Parse the JSON result for data processing
            raw_data = json.loads(vector_result.data_json) if vector_result.data_json else {}

            # Convert to QueryResult format
            workflow_state['query_result'] = QueryResult(
                database_type=DatabaseType.VECTOR,
                data=raw_data,
                raw_result=vector_result.data_json,
                elastic_query=vector_result.elastic_query
            )
            workflow_state['json_data'] = vector_result.data_json

            # Generate markdown formatted data
            workflow_state['data_markdown'] = convert_json_to_markdown(raw_data, "Vector Search Results")

            logger.info("Vector query executed successfully")
            return workflow_state

        except Exception as e:
            logger.error(f"Error in vector query: {e}")
            # Fallback to using existing query executor
            if workflow_state.get('database_type'):
                workflow_state['query_result'] = self.query_executor.execute_query(
                    workflow_state['database_type'], user_query, self.config.es_schema,
                    self.config.es_instructions, parsed_history
                )
                workflow_state['json_data'] = json.dumps(workflow_state['query_result'].data)
                # Generate markdown for fallback data
                workflow_state['data_markdown'] = convert_json_to_markdown(
                    workflow_state['query_result'].data, "Vector Search Results"
                )
            return workflow_state

    def _execute_summary_generation(self, workflow_state: Dict, user_query: str, conversation_history: Optional[str]) -> Dict:
        """Execute summary generation step."""
        try:
            summary_result = self.summary_generator(
                user_query=user_query,
                conversation_history=self._parse_conversation_history(conversation_history),
                json_results=workflow_state.get('json_data', '')
            )

            workflow_state['summary'] = summary_result.summary
            logger.info("Summary generated successfully")
            return workflow_state

        except Exception as e:
            logger.error(f"Error in summary generation: {e}")
            return workflow_state

    def _execute_chart_generation(self, workflow_state: Dict, user_query: str, parsed_history: Optional[List[Dict]]) -> Dict:
        """Execute chart generation step."""
        try:
            chart_result = self.chart_generator(
                json_data=workflow_state.get('json_data', '{}'),
                user_query=user_query,
                conversation_history=parsed_history
            )

            workflow_state['chart_config'] = chart_result.highchart_config
            # Generate HTML from chart config if needed
            workflow_state['chart_html'] = self._generate_chart_html(chart_result.highchart_config)

            logger.info("Chart generated successfully")
            return workflow_state

        except Exception as e:
            logger.error(f"Error in chart generation: {e}")
            return workflow_state

    def _generate_chart_html(self, chart_config: Dict) -> Optional[str]:
        """Generate HTML from chart configuration."""
        if not chart_config:
            return None

        # Simple HTML template for Highcharts
        html_template = f"""
        <div id="chartContainer" style="width: 100%; height: 400px;"></div>
        <script src="https://code.highcharts.com/highcharts.js"></script>
        <script>
            Highcharts.chart('chartContainer', {json.dumps(chart_config)});
        </script>
        """
        return html_template

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
    async def process_query_async(self, user_query: str, conversation_history: Optional[str] = None):
        """
        Process query asynchronously, yielding results as they become available.
        This implementation uses the QueryWorkflowPlanner to orchestrate the workflow.

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
            async for field_name, field_value in self._execute_workflow_async(workflow_plan, user_query, parsed_history, conversation_history):
                yield field_name, field_value

        except Exception as e:
            logger.error(f"Error in QueryAgent.process_query_async: {e}", exc_info=True)
            yield "error", str(e)

    async def _execute_workflow_async(self, workflow_plan, user_query: str, parsed_history: Optional[List[Dict]], conversation_history: Optional[str]):
        """
        Execute the planned workflow steps sequentially with async yielding.
        Results are yielded immediately when ready, without waiting for subsequent steps.

        Args:
            workflow_plan: The workflow plan from QueryWorkflowPlanner
            user_query: The user's query string
            parsed_history: Parsed conversation history
            conversation_history: Raw conversation history string

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
                    workflow_state = self._execute_es_query(workflow_state, user_query, parsed_history)
                    # Immediately yield markdown data when ES query completes - don't wait for summary
                    if workflow_state.get('data_markdown'):
                        yield "data_markdown", workflow_state['data_markdown']
                        logger.info("ES query markdown data yielded immediately to frontend")

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

