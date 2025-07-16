"""Simple query agent that executes workflow plan dynamically."""
import json
import logging

import dspy

from components.query_executor import DSPyQueryExecutor
from components.result_processor import ResultProcessor
from core.exceptions import DSPyAgentException
from core.interfaces import IQueryAgent, ProcessedResult, QueryResult, DatabaseType
from modules.query_models import QueryRequest
from modules.signatures import ThinkingSignature, QueryWorkflowPlanner, SummarySignature, ChartGenerator
from util.chart_utils import generate_chart_from_config
from util.performance import monitor_performance

logger = logging.getLogger(__name__)

class QueryAgent(IQueryAgent):
    """Simple query agent that uses existing components."""

    def __init__(self):
        """Initialize QueryAgent with existing components."""
        # Use existing components instead of duplicating functionality
        self.thinking = dspy.ChainOfThought(ThinkingSignature)
        self.workflow_planner = dspy.Predict(QueryWorkflowPlanner)
        self.query_executor = DSPyQueryExecutor()
        self.result_processor = ResultProcessor()

        # For summary and chart generation, we'll use the DSPy signatures directly
        self.summary_processor = dspy.ChainOfThought(SummarySignature)
        self.chart_processor = dspy.Predict(ChartGenerator)

        # Config
        from core.config import config_manager
        self.config = config_manager.config

    def _parse_history(self, conversation_history):
        """Parse conversation history and return only last 3 messages."""
        if not conversation_history:
            return None
        try:
            if isinstance(conversation_history, str):
                parsed = json.loads(conversation_history)
            else:
                parsed = conversation_history

            # Return only the last 3 messages to limit context size
            if isinstance(parsed, list) and len(parsed) > 3:
                return parsed[-3:]
            return parsed
        except:
            return None

    @monitor_performance("query_processing")
    def process_query(self, request: QueryRequest) -> ProcessedResult:
        """Process query using existing components."""
        try:
            parsed_history = self._parse_history(request.conversation_history)

            # Step 1: Think
            thinking_result = self.thinking(
                system_prompt=request.system_prompt,
                user_query=request.user_query,
                conversation_history=parsed_history
            )

            # Check if query is within context - stop execution if not
            if not thinking_result.is_within_context:
                logger.info(f"Query out of context at thinking stage, stopping execution: {request.user_query}")
                return ProcessedResult(
                    query_result=self._empty_query_result(),
                    summary=f"I'm sorry, but your query is outside my area of expertise. {thinking_result.detailed_analysis}",
                    chart_config=None,
                    chart_html=None
                )

            # Step 2: Plan Workflow
            es_schema = request.es_schemas
            workflow_plan = self.workflow_planner(
                system_prompt=request.system_prompt,
                user_query=request.user_query,
                es_schema_available=request.es_schemas is not None,
                vector_index_available= request.vector_db_index is not None,
                detailed_analysis=thinking_result.detailed_analysis,
                context_summary=thinking_result.context_summary,
                es_schema=es_schema
            )

            # Check if workflow is within context - stop execution if not
            if not workflow_plan.is_within_context:
                logger.info(f"Workflow out of context at planning stage, stopping execution: {request.user_query}")
                return ProcessedResult(
                    query_result=self._empty_query_result(),
                    summary=f"I'm sorry, but the required workflow for your query is outside my capabilities. {workflow_plan.reasoning}",
                    chart_config=None,
                    chart_html=None
                )

            # Step 3: Execute workflow plan
            return self._execute_workflow_plan(
                workflow_plan.workflow_plan,
                request,
                thinking_result.detailed_analysis,
                thinking_result.context_summary
            )

        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            raise DSPyAgentException(f"Query processing failed: {e}")

    def _execute_workflow_plan(self, plan: list, request: QueryRequest, detailed_analysis: str, context_summary: str) -> ProcessedResult:
        """Execute workflow plan using existing components."""
        query_result = None
        summary = None
        chart_config = None
        chart_html = None

        for signature_name in plan:
            logger.info(f"Executing signature: {signature_name}")

            if signature_name == 'EsQueryProcessor':
                es_schema = request.es_schemas
                query_result = self.query_executor.execute_query(
                    database_type=DatabaseType.ELASTIC,
                    user_query=request.user_query,
                    schema=es_schema,
                    instructions=self.config.es_instructions,
                    conversation_history=request.conversation_history,
                    detailed_analysis=detailed_analysis,
                    vector_db_index=request.vector_db_index,
                )

            elif signature_name == 'VectorQueryProcessor':
                query_result = self.query_executor.execute_query(
                    database_type=DatabaseType.VECTOR,
                    user_query=request.user_query,
                    vector_index=request.vector_index,
                    schema=None,
                    instructions=None,
                    conversation_history=request.conversation_history,
                    detailed_analysis=detailed_analysis,
                    vector_db_index=request.vector_db_index,
                )

            elif signature_name == 'SummarySignature':
                if query_result:
                    json_data = json.dumps(query_result.data) if query_result.data else "[]"
                    summary_result = self.summary_processor(
                        user_query=request.user_query,
                        detailed_analysis=detailed_analysis,
                        context_summary=context_summary,
                        json_results=json_data
                    )
                    summary = summary_result.summary

            elif signature_name == 'ChartGenerator':
                if query_result and query_result.data:
                    json_data = json.dumps(query_result.data)
                    chart_result = self.chart_processor(
                        user_query=request.user_query,
                        detailed_analysis=detailed_analysis,
                        context_summary=context_summary,
                        json_results=json_data
                    )

                    if chart_result.needs_chart:
                        from components.chart_generator import generate_highchart_config
                        chart_config = generate_highchart_config(
                            chart_type=chart_result.chart_type,
                            x_axis_column=chart_result.x_axis_column,
                            y_axis_column=chart_result.y_axis_column,
                            x_axis_label=chart_result.x_axis_column.title(),
                            y_axis_label=chart_result.y_axis_column.title(),
                            chart_title=chart_result.chart_title,
                            json_data=json_data
                        )
                        chart_html = generate_chart_from_config(chart_config)

        return ProcessedResult(
            query_result=query_result or self._empty_query_result(),
            summary=summary or "No summary generated",
            chart_config=chart_config,
            chart_html=chart_html
        )

    def _empty_query_result(self) -> QueryResult:
        """Return empty query result."""
        return QueryResult(
            database_type=DatabaseType.ELASTIC,
            data=[],
            raw_result={}
        )

    async def process_query_async(self, request: QueryRequest, session_id=None, message_id=None):
        """Async version using existing components."""
        try:
            parsed_history = self._parse_history(request.conversation_history)

            # Step 1: Think
            yield "current_step", "thinking"
            thinking_result = self.thinking(
                system_prompt=request.system_prompt,
                user_query=request.user_query,
                conversation_history=parsed_history
            )
            yield "thinking_analysis", thinking_result.detailed_analysis

            # Check if query is within context at thinking stage - stop execution if not
            if not thinking_result.is_within_context:
                logger.info(f"Query out of context at thinking stage, stopping async execution: {request.user_query}")
                yield "summary", f"I'm sorry, but your query is outside my area of expertise. {thinking_result.detailed_analysis}"
                yield "completed", True
                return

            # Step 2: Plan Workflow
            yield "current_step", "planning"
            es_schema = request.es_schemas
            workflow_plan = self.workflow_planner(
                system_prompt=request.system_prompt,
                user_query=request.user_query,
                es_schema_available=request.es_schemas is not None,
                vector_index_available=request.vector_db_index is not None,
                detailed_analysis=thinking_result.detailed_analysis,
                context_summary=thinking_result.context_summary,
                es_schema=es_schema
            )
            yield "workflow_plan", workflow_plan.workflow_plan
            yield "workflow_reasoning", workflow_plan.reasoning

            # Check if workflow is within context at planning stage - stop execution if not
            if not workflow_plan.is_within_context:
                logger.info(f"Workflow out of context at planning stage, stopping async execution: {request.user_query}")
                yield "summary", f"I'm sorry, but the required workflow for your query is outside my capabilities. {workflow_plan.reasoning}"
                yield "completed", True
                return

            # Step 3: Execute workflow plan
            query_result = None

            for signature_name in workflow_plan.workflow_plan:
                yield "current_step", f"executing_{signature_name.lower()}"

                if signature_name == 'EsQueryProcessor':
                    query_result = self.query_executor.execute_query(
                        database_type=DatabaseType.ELASTIC,
                        user_query=request.user_query,
                        schema=es_schema,
                        instructions=self.config.es_instructions,
                        conversation_history=request.conversation_history,
                        detailed_analysis=thinking_result.detailed_analysis,
                        context_summary=thinking_result.context_summary,  # Added missing parameter
                        vector_db_index=request.vector_db_index,
                    )
                    yield "data", query_result.data
                    if hasattr(query_result, 'markdown_content'):
                        yield "markdown_results", query_result.markdown_content

                elif signature_name == 'VectorQueryProcessor':
                    query_result = self.query_executor.execute_query(
                        database_type=DatabaseType.VECTOR,
                        user_query=request.user_query,
                        schema=None,
                        instructions=None,
                        conversation_history=request.conversation_history,
                        detailed_analysis=thinking_result.detailed_analysis,
                        context_summary=thinking_result.context_summary,  # Added missing parameter
                        vector_db_index=request.vector_db_index,
                    )
                    yield "data", query_result.data

                elif signature_name == 'SummarySignature':
                    if query_result:
                        json_data = json.dumps(query_result.data) if query_result.data else "[]"
                        summary_result = self.summary_processor(
                            user_query=request.user_query,
                            detailed_analysis=thinking_result.detailed_analysis,
                            context_summary=thinking_result.context_summary,
                            json_results=json_data
                        )
                        yield "summary", summary_result.summary

                elif signature_name == 'ChartGenerator':
                    if query_result and query_result.data:
                        json_data = json.dumps(query_result.data)
                        chart_result = self.chart_processor(
                            user_query=request.user_query,
                            detailed_analysis=thinking_result.detailed_analysis,
                            context_summary=thinking_result.context_summary,
                            json_results=json_data
                        )

                        if chart_result.needs_chart:
                            from components.chart_generator import generate_highchart_config
                            chart_config = generate_highchart_config(
                                chart_type=chart_result.chart_type,
                                x_axis_column=chart_result.x_axis_column,
                                y_axis_column=chart_result.y_axis_column,
                                x_axis_label=chart_result.x_axis_column.title(),
                                y_axis_label=chart_result.y_axis_column.title(),
                                chart_title=chart_result.chart_title,
                                json_data=json_data
                            )
                            chart_html = generate_chart_from_config(chart_config)
                            yield "chart_config", chart_config
                            yield "chart_html", chart_html

            yield "completed", True

        except Exception as e:
            logger.error(f"Async query processing failed: {e}")
            yield "error", str(e)
