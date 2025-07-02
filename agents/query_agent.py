"""Simple query agent using clean 2-step workflow."""
import logging
import json
import dspy

from core.exceptions import DSPyAgentException
from core.interfaces import IQueryAgent, ProcessedResult, QueryResult, DatabaseType
from modules.signatures import (
    ThinkingSignature, QueryWorkflowPlanner,
    EsQueryProcessor, VectorQueryProcessor, SummarySignature,
    ChartGenerator
)
from services.metadata_search_service import search_vector_metadata
from services.search_service import convert_json_to_markdown
from components.chart_generator import generate_highchart_config
from util.chart_utils import generate_chart_from_config
from util.performance import monitor_performance

logger = logging.getLogger(__name__)

class QueryAgent(IQueryAgent):
    """Query agent with clean workflow: Think -> Metadata Search -> Plan & Execute."""

    def __init__(self, database_selector, query_executor, result_processor):
        """Initialize with existing components."""
        self.database_selector = database_selector
        self.query_executor = query_executor
        self.result_processor = result_processor

        # Clean workflow signatures
        self.thinking = dspy.ChainOfThought(ThinkingSignature)
        self.workflow_planner = dspy.Predict(QueryWorkflowPlanner)
        self.chart_generator = dspy.Predict(ChartGenerator)

        # Config
        from core.config import config_manager
        self.config = config_manager.config

    def _parse_history(self, conversation_history):
        """Parse conversation history."""
        if not conversation_history:
            return None
        try:
            if isinstance(conversation_history, str):
                return json.loads(conversation_history)
            return conversation_history
        except:
            return None

    @monitor_performance("query_processing")
    def process_query(self, user_query: str, conversation_history=None) -> ProcessedResult:
        """Process query using clean workflow: Think -> Metadata Search -> Plan & Execute."""
        try:
            parsed_history = self._parse_history(conversation_history)

            # Step 1: Think - Analyze user intent
            thinking_result = self.thinking(
                user_query=user_query,
                conversation_history=parsed_history
            )

            # Step 2: Metadata Search - Check vector metadata directly
            metadata_search_result = search_vector_metadata(
                search_terms=thinking_result.search_terms,
                key_concepts=thinking_result.key_concepts
            )

            # Step 3: Plan Complete Workflow - QueryWorkflowPlanner decides everything
            workflow_plan = self.workflow_planner(
                user_query=user_query,
                detailed_analysis=thinking_result.detailed_analysis,
                metadata_found=metadata_search_result["metadata_found"],
                metadata_summary=metadata_search_result["metadata_summary"],
                es_schema=self.config.es_schema,
                conversation_history=parsed_history
            )

            # Execute the planned workflow with markdown conversion
            query_result = self._execute_workflow(
                workflow_plan.workflow_plan,
                user_query,
                parsed_history,
                thinking_result.detailed_analysis
            )

            # Generate summary with detailed_analysis
            summary_result = self._generate_summary(
                query_result, user_query, thinking_result.detailed_analysis, conversation_history
            )

            # Only generate chart if ChartGenerator is in the workflow plan
            chart_config, chart_html = None, None
            if 'ChartGenerator' in workflow_plan.workflow_plan:
                chart_config, chart_html = self._generate_chart(
                    query_result, user_query, thinking_result.detailed_analysis
                )

            return ProcessedResult(
                query_result=query_result,
                summary=summary_result,
                chart_config=chart_config,
                chart_html=chart_html
            )

        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            raise DSPyAgentException(f"Query processing failed: {e}")

    def _execute_workflow(self, workflow_plan: list, user_query: str, parsed_history, detailed_analysis: str) -> QueryResult:
        """Execute the planned workflow sequence."""
        query_result = None

        for signature_name in workflow_plan:
            if signature_name == 'EsQueryProcessor':
                query_result = self.query_executor.execute_query(
                    database_type=DatabaseType.ELASTIC,
                    user_query=user_query,
                    schema=self.config.es_schema,
                    instructions=self.config.es_instructions,
                    conversation_history=parsed_history
                )
                # Convert ES results to markdown
                if query_result and query_result.data:
                    markdown_content = convert_json_to_markdown(query_result.data, "Elasticsearch Query Results")
                    query_result.markdown_content = markdown_content

            elif signature_name == 'VectorQueryProcessor':
                query_result = self.query_executor.execute_query(
                    database_type=DatabaseType.VECTOR,
                    user_query=user_query,
                    schema=self.config.es_schema,
                    instructions=self.config.es_instructions,
                    conversation_history=parsed_history
                )
                # Convert Vector results to markdown
                if query_result and query_result.data:
                    markdown_content = convert_json_to_markdown(query_result.data, "Vector Search Results")
                    query_result.markdown_content = markdown_content

        # Return empty result if no query execution happened
        if query_result is None:
            query_result = QueryResult(
                database_type=DatabaseType.ELASTIC,
                data=[],
                raw_result={}
            )

        return query_result

    def _generate_summary(self, query_result: QueryResult, user_query: str, detailed_analysis: str, conversation_history) -> str:
        """Generate summary using SummarySignature with detailed_analysis."""
        try:
            # Use result processor's summary generator but pass detailed_analysis
            json_data = json.dumps(query_result.data) if query_result.data else "[]"

            # Create a simple DSPy summary signature instance
            summary_signature = dspy.ChainOfThought(SummarySignature)
            result = summary_signature(
                user_query=user_query,
                detailed_user_query=detailed_analysis,
                conversation_history=conversation_history,
                json_results=json_data
            )
            return result.summary
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Summary generation failed"

    def _generate_chart(self, query_result: QueryResult, user_query: str, detailed_analysis: str) -> tuple:
        """Generate chart using simplified ChartGenerator signature and chart_generator.py."""
        try:
            json_data = json.dumps(query_result.data) if query_result.data else "[]"

            if not query_result.data or json_data == "[]":
                return None, None

            # Use the ChartGenerator signature to decide chart parameters
            chart_result = self.chart_generator(
                user_query=user_query,
                detailed_user_query=detailed_analysis,
                json_results=json_data
            )

            if not chart_result.needs_chart:
                return None, None

            # Use the existing chart_generator.py to create the actual chart
            chart_config = generate_highchart_config(
                chart_type=chart_result.chart_type,
                x_axis_column=chart_result.x_axis_column,
                y_axis_column=chart_result.y_axis_column,
                x_axis_label=chart_result.x_axis_column.title(),
                y_axis_label=chart_result.y_axis_column.title(),
                chart_title=chart_result.chart_title,
                json_data=json_data
            )

            # Generate HTML from config
            chart_html = generate_chart_from_config(chart_config)

            return chart_config, chart_html

        except Exception as e:
            logger.error(f"Error generating chart: {e}")
            return None, None

    async def process_query_async(self, user_query: str, conversation_history=None, session_id=None, message_id=None):
        """Async version of the clean workflow with markdown conversion."""
        try:
            parsed_history = self._parse_history(conversation_history)

            # Step 1: Think
            yield "current_step", "thinking"
            thinking_result = self.thinking(
                user_query=user_query,
                conversation_history=parsed_history
            )
            yield "thinking_analysis", thinking_result.detailed_analysis

            # Step 2: Metadata Search - Direct function call
            yield "current_step", "metadata_search"
            metadata_search_result = search_vector_metadata(
                search_terms=thinking_result.search_terms,
                key_concepts=thinking_result.key_concepts
            )
            yield "metadata_found", metadata_search_result["metadata_found"]
            yield "metadata_summary", metadata_search_result["metadata_summary"]

            # Step 3: Plan Complete Workflow - QueryWorkflowPlanner decides everything
            yield "current_step", "planning"
            workflow_plan = self.workflow_planner(
                user_query=user_query,
                detailed_analysis=thinking_result.detailed_analysis,
                metadata_found=metadata_search_result["metadata_found"],
                metadata_summary=metadata_search_result["metadata_summary"],
                es_schema=self.config.es_schema,
                conversation_history=parsed_history
            )
            yield "workflow_plan", workflow_plan.workflow_plan
            yield "workflow_reasoning", workflow_plan.reasoning
            yield "primary_data_source", workflow_plan.primary_data_source

            # Step 4: Execute the planned workflow with markdown conversion
            query_result = self._execute_workflow(
                workflow_plan.workflow_plan,
                user_query,
                parsed_history,
                thinking_result.detailed_analysis
            )
            yield "data", query_result.data

            # Push markdown content to frontend if available
            if hasattr(query_result, 'markdown_content') and query_result.markdown_content:
                yield "markdown_results", query_result.markdown_content

            # Step 5: Generate summary with detailed_analysis
            yield "current_step", "generating_summary"
            summary_result = self._generate_summary(
                query_result, user_query, thinking_result.detailed_analysis, conversation_history
            )
            yield "summary", summary_result

            # Step 6: Only generate chart if ChartGenerator is in the workflow plan
            if 'ChartGenerator' in workflow_plan.workflow_plan:
                yield "current_step", "generating_chart"
                chart_config, chart_html = self._generate_chart(
                    query_result, user_query, thinking_result.detailed_analysis
                )
                if chart_config:
                    yield "chart_config", chart_config
                if chart_html:
                    yield "chart_html", chart_html

            yield "completed", True

        except Exception as e:
            logger.error(f"Async query processing failed: {e}")
            yield "error", str(e)
