"""Simple query agent that executes workflow plan dynamically."""
import json
import logging

import dspy

from components.chart_generator import generate_highchart_config
from core.exceptions import DSPyAgentException
from core.interfaces import IQueryAgent, ProcessedResult, QueryResult, DatabaseType
from modules.signatures import (
    ThinkingSignature, QueryWorkflowPlanner, SummarySignature, ChartGenerator, DocumentMetadataExtractor,
    EsQueryProcessor, VectorQueryProcessor
)
from services.search_service import convert_json_to_markdown, execute_query, execute_vector_query
from util.chart_utils import generate_chart_from_config
from util.performance import monitor_performance

logger = logging.getLogger(__name__)

class QueryAgent(IQueryAgent):
    """Query agent that dynamically executes workflow plan."""

    def __init__(self):
        """Initialize QueryAgent with all processors directly."""
        # Initialize all signature processors directly
        self.thinking = dspy.ChainOfThought(ThinkingSignature)
        self.workflow_planner = dspy.Predict(QueryWorkflowPlanner)
        self.es_processor = dspy.Predict(EsQueryProcessor)
        self.vector_processor = dspy.Predict(VectorQueryProcessor)
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
    def process_query(self, user_query: str, conversation_history=None) -> ProcessedResult:
        """Process query by dynamically executing workflow plan."""
        try:
            parsed_history = self._parse_history(conversation_history)

            # Step 1: Think
            thinking_result = self.thinking(
                user_query=user_query,
                conversation_history=parsed_history
            )

            # Step 2: Plan Workflow (removed metadata search step)
            workflow_plan = self.workflow_planner(
                user_query=user_query,
                detailed_analysis=thinking_result.detailed_analysis,
                context_summary=thinking_result.context_summary,
                es_schema=self.config.es_schema
            )

            # Step 3: Execute workflow plan dynamically
            results = self._execute_workflow_plan(
                workflow_plan.workflow_plan,
                user_query,
                thinking_result.detailed_analysis,
                thinking_result.context_summary
            )

            return results

        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            raise DSPyAgentException(f"Query processing failed: {e}")

    def _execute_workflow_plan(self, plan: list, user_query: str, detailed_analysis: str, context_summary: str) -> ProcessedResult:
        """Execute the workflow plan by looping over signatures."""
        query_result = None
        summary = None
        chart_config = None
        chart_html = None

        for signature_name in plan:
            logger.info(f"Executing signature: {signature_name}")

            if signature_name == 'EsQueryProcessor':
                query_result = self._execute_es_query(user_query, detailed_analysis, context_summary)

            elif signature_name == 'VectorQueryProcessor':
                query_result = self._execute_vector_query(user_query, detailed_analysis, context_summary)

            elif signature_name == 'SummarySignature':
                print(f"Generating summary for query: {user_query}")
                print(f"Generating summary for query: {query_result}")
                json_data = json.dumps(query_result.data) if query_result and query_result.data else "[]"
                summary = self._execute_summary(user_query, detailed_analysis, context_summary, json_data)

            elif signature_name == 'ChartGenerator':
                json_data = json.dumps(query_result.data) if query_result and query_result.data else "[]"
                chart_config, chart_html = self._execute_chart_generation(user_query, detailed_analysis, context_summary, json_data)

        return ProcessedResult(
            query_result=query_result or self._empty_query_result(),
            summary=summary or "No summary generated",
            chart_config=chart_config,
            chart_html=chart_html
        )

    def _execute_es_query(self, user_query: str, detailed_analysis: str, context_summary: str) -> QueryResult:
        """Execute Elasticsearch query using DSPy processor directly."""
        try:
            # Use DSPy processor to generate ES query
            es_result = self.es_processor(
                user_query=user_query,
                detailed_analysis=detailed_analysis,
                context_summary=context_summary,
                es_schema=self.config.es_schema,
                es_instructions=self.config.es_instructions
            )

            # Execute the actual ES query
            query_response = execute_query(es_result.elastic_query, es_result.elastic_index)

            if query_response.get('success'):
                # Extract data from ES response
                es_data = query_response['result']
                if hasattr(es_data, 'body'):
                    response_dict = es_data.body
                elif hasattr(es_data, 'to_dict'):
                    response_dict = es_data.to_dict()
                else:
                    response_dict = dict(es_data)

                # Create QueryResult
                query_result = QueryResult(
                    database_type=DatabaseType.ELASTIC,
                    data=response_dict.get('hits', {}).get('hits', []),
                    raw_result=response_dict
                )

                # Convert to markdown
                if query_result.data:
                    markdown_content = convert_json_to_markdown(query_result.data, "Elasticsearch Query Results")
                    query_result.markdown_content = markdown_content

                logger.info(f"✅ ES query completed successfully with {len(query_result.data)} results")
                return query_result
            else:
                logger.error(f"ES query failed: {query_response}")
                return self._empty_query_result()

        except Exception as e:
            logger.error(f"ES query execution failed: {e}")
            return self._empty_query_result()

    def _execute_vector_query(self, user_query: str, detailed_analysis: str, context_summary: str) -> QueryResult:
        """Execute vector query using DSPy processor directly."""
        try:
            # Use DSPy processor to generate vector query
            vector_result = self.vector_processor(
                user_query=user_query,
                detailed_analysis=detailed_analysis,
                context_summary=context_summary
            )

            # Execute the actual vector search
            vector_search_params = {
                'query_text': vector_result.vector_query,
                'index': 'docling_documents',
                'size': 25
            }

            vector_response = execute_vector_query(vector_search_params)

            if vector_response.get('success'):
                # Extract data from vector response
                vector_data = vector_response['result']
                if hasattr(vector_data, 'body'):
                    response_dict = vector_data.body
                elif hasattr(vector_data, 'to_dict'):
                    response_dict = vector_data.to_dict()
                else:
                    response_dict = dict(vector_data)

                # Create QueryResult
                query_result = QueryResult(
                    database_type=DatabaseType.VECTOR,
                    data=response_dict.get('hits', {}).get('hits', []),
                    raw_result=response_dict
                )

                # Do NOT convert vector results to markdown - keep as raw data only
                logger.info(f"✅ Vector query completed successfully with {len(query_result.data)} results")
                return query_result
            else:
                logger.error(f"Vector query failed: {vector_response}")
                return self._empty_query_result()

        except Exception as e:
            logger.error(f"Vector query execution failed: {e}")
            return self._empty_query_result()

    def _execute_summary(self, user_query: str, detailed_analysis: str, context_summary: str, json_data: str) -> str:
        """Execute summary generation."""
        try:
            print(f"JSON Data for Summary: {json_data[:500]}...")  # Debugging output
            result = self.summary_processor(
                user_query=user_query,
                detailed_analysis=detailed_analysis,
                context_summary=context_summary,
                json_results=json_data
            )
            return result.summary
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return "Summary generation failed"

    def _execute_chart_generation(self, user_query: str, detailed_analysis: str, context_summary: str, json_data: str) -> tuple:
        """Execute chart generation using existing chart_generator.py."""
        try:
            if not json_data or json_data == "[]":
                return None, None

            # Use DSPy to decide chart parameters
            chart_result = self.chart_processor(
                user_query=user_query,
                detailed_analysis=detailed_analysis,
                context_summary=context_summary,
                json_results=json_data
            )

            if not chart_result.needs_chart:
                return None, None

            # Generate chart using existing components
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
            return chart_config, chart_html

        except Exception as e:
            logger.error(f"Chart generation failed: {e}")
            return None, None

    def _empty_query_result(self) -> QueryResult:
        """Return empty query result."""
        return QueryResult(
            database_type=DatabaseType.ELASTIC,
            data=[],
            raw_result={}
        )

    async def process_query_async(self, user_query: str, conversation_history=None, session_id=None, message_id=None):
        """Async version that loops over workflow plan."""
        try:
            parsed_history = self._parse_history(conversation_history)

            # Step 1: Think
            yield "current_step", "thinking"
            thinking_result = self.thinking(
                user_query=user_query,
                conversation_history=parsed_history
            )
            yield "thinking_analysis", thinking_result.detailed_analysis

            # Step 2: Plan Workflow (removed metadata search step)
            yield "current_step", "planning"
            workflow_plan = self.workflow_planner(
                user_query=user_query,
                detailed_analysis=thinking_result.detailed_analysis,
                context_summary=thinking_result.context_summary,
                es_schema=self.config.es_schema
            )
            yield "workflow_plan", workflow_plan.workflow_plan
            yield "workflow_reasoning", workflow_plan.reasoning

            # Step 3: Execute workflow plan dynamically
            query_result = None

            for signature_name in workflow_plan.workflow_plan:
                yield "current_step", f"executing_{signature_name.lower()}"

                if signature_name == 'EsQueryProcessor':
                    query_result = self._execute_es_query(user_query, thinking_result.detailed_analysis, thinking_result.context_summary)
                    yield "data", query_result.data
                    if hasattr(query_result, 'markdown_content'):
                        yield "markdown_results", query_result.markdown_content

                elif signature_name == 'VectorQueryProcessor':
                    query_result = self._execute_vector_query(user_query, thinking_result.detailed_analysis, thinking_result.context_summary)
                    yield "data", query_result.data
                    # No markdown conversion for vector query results

                elif signature_name == 'SummarySignature':
                    json_data = json.dumps(query_result.data) if query_result and query_result.data else "[]"
                    summary = self._execute_summary(user_query, thinking_result.detailed_analysis, thinking_result.context_summary, json_data)
                    yield "summary", summary

                elif signature_name == 'ChartGenerator':
                    json_data = json.dumps(query_result.data) if query_result and query_result.data else "[]"
                    chart_config, chart_html = self._execute_chart_generation(user_query, thinking_result.detailed_analysis, thinking_result.context_summary, json_data)
                    if chart_config:
                        yield "chart_config", chart_config
                    if chart_html:
                        yield "chart_html", chart_html

            yield "completed", True

        except Exception as e:
            logger.error(f"Async query processing failed: {e}")
            yield "error", str(e)
