"""Redesigned query agent with structured JSON output and improved workflow."""
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
import time

import dspy

from core.interfaces import ProcessedResult, QueryResult, DatabaseType
from modules.query_models import QueryRequest
from modules.signatures import ThinkingSignature, QueryWorkflowPlanner, EsQueryProcessor, VectorQueryProcessor, SummarySignature, ChartGenerator
from services.search_service import execute_query, execute_vector_query, convert_vector_results_to_markdown
from services.llm_service import set_mlflow_trace_name

logger = logging.getLogger(__name__)

class QueryAgent(dspy.Module):
    """Redesigned query agent with structured workflow and JSON output."""

    def __init__(self):
        """Initialize QueryAgent with DSPy components."""
        super().__init__()

        # Initialize all DSPy signatures
        self.thinking = dspy.ChainOfThought(ThinkingSignature)
        self.workflow_planner = dspy.Predict(QueryWorkflowPlanner)
        self.es_query_processor = dspy.Predict(EsQueryProcessor)
        self.vector_query_processor = dspy.Predict(VectorQueryProcessor)
        self.summary_processor = dspy.ChainOfThought(SummarySignature)
        self.chart_processor = dspy.Predict(ChartGenerator)

        # Storage for outputs from executed signatures
        self.signature_outputs = {}
        self.temperature = 0.0
        self.frequency_penalty = 0.0

        logger.info("QueryAgent initialized with redesigned workflow")

    def _parse_history(self, conversation_history):
        """Parse conversation history and return only last 5 user messages."""
        if not conversation_history:
            return []

        try:
            if isinstance(conversation_history, str):
                parsed = json.loads(conversation_history)
            else:
                parsed = conversation_history

            if not isinstance(parsed, list):
                logger.warning("Conversation history is not a list, returning empty history")
                return []

            # Filter to get only user messages and return last 5
            user_messages = [msg for msg in parsed if isinstance(msg, dict) and msg.get('role') == 'user']
            return user_messages[-5:] if len(user_messages) > 5 else user_messages

        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            logger.error(f"Failed to parse conversation history: {e}")
            return []

    def _convert_to_json_serializable(self, obj: Any) -> Any:
        """Convert any object to JSON serializable format."""
        if obj is None:
            return None
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        elif isinstance(obj, dict):
            return {k: self._convert_to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json_serializable(item) for item in obj]
        elif hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return {k: self._convert_to_json_serializable(v) for k, v in obj.__dict__.items()}
        else:
            try:
                json.dumps(obj)  # Test if it's JSON serializable
                return obj
            except (TypeError, ValueError):
                return str(obj)

    def _create_message(self, message_type, content, render_type="text"):
        """Helper method to create standardized message objects."""
        return "message", {
            "type": message_type,
            "content": self._convert_to_json_serializable(content),
            "render_type": render_type,
            "timestamp": time.time()
        }

    def _create_debug_message(self, debug_type, content):
        """Helper method to create debug messages."""
        return self._create_message("debug", {"type": debug_type, **content}, "debug")

    def _create_error_message(self, error_message, error_type="error"):
        """Helper method to create error messages."""
        return self._create_message("error", error_message, "error")

    def _prepare_json_data(self, query_result):
        """Convert query results to JSON string."""
        if query_result is None or not query_result.result:
            return "[]"
        return json.dumps(query_result.result)

    async def _execute_es_query_processor(self, request: QueryRequest, detailed_query: str):
        """Execute Elasticsearch query processor step with retry logic for failed queries."""
        max_retries = 2

        for attempt in range(max_retries + 1):
            try:
                # Generate ES query with temperature and frequency penalty that increase with each retry
                es_query_result = self.es_query_processor(
                    detailed_user_query=detailed_query,
                    es_schema=request.es_schemas,
                    es_instructions=request.query_instructions,
                    config={
                        "temperature": self.temperature + attempt * 0.2,
                        "frequency_penalty": self.frequency_penalty + attempt * 0.2,
                    }
                )

                logger.info(f"ES query generation result on attempt {attempt + 1}: {es_query_result}")

                elastic_query = es_query_result.elastic_query
                elastic_index = es_query_result.elastic_index
                self.signature_outputs['EsQueryProcessor'] = {'elastic_query': elastic_query, 'elastic_index': elastic_index}

                try:
                    # Execute query
                    query_result = execute_query(query_body=elastic_query, index=elastic_index)
                    rows_count = len(query_result.result) if query_result.result else 0
                    logger.info(f"ES query executed successfully, returned {rows_count} results")

                    debug_info = {
                        "elastic_query": elastic_query,
                        "elastic_index": elastic_index,
                        "rows_count": rows_count,
                        "attempts": attempt + 1,
                        "status": "success_no_data" if rows_count == 0 else "success"
                    }

                    if not query_result.result:
                        # No results found
                        # Not sending raw JSON results to frontend
                        yield self._create_message("markdown_table", "No data found.", "markdown")
                        yield "debug", {**debug_info, "timestamp": time.time()}
                        yield self._create_debug_message("es_execution", debug_info)
                    else:
                        # Results found - yield them
                        markdown_table = getattr(query_result, 'markdown_content',
                                              "Results found but no formatted display available.")
                        # Not sending raw JSON results to frontend
                        yield self._create_message("markdown_table", markdown_table, "markdown")
                        yield self._create_debug_message("es_execution", debug_info)

                    yield "query_result", query_result
                    return  # Success - exit retry loop

                except Exception as es_exec_error:
                    logger.error(f"ES execution exception: {es_exec_error}")

                    # If this was the last attempt, report the error
                    if attempt == max_retries:
                        error_message = f"Elasticsearch query failed after {max_retries + 1} attempts: {str(es_exec_error)}"
                        yield self._create_error_message(error_message)
                        yield self._create_debug_message("es_execution", {
                            "elastic_query": elastic_query,
                            "elastic_index": elastic_index,
                            "error": str(es_exec_error),
                            "attempts": attempt + 1,
                            "status": "error"
                        })
                        return

                    # Continue to next retry attempt
                    logger.info(f"Retrying ES query generation (attempt {attempt + 2}/{max_retries + 1})")
                    continue

            except Exception as es_gen_error:
                logger.error(f"ES query generation failed on attempt {attempt + 1}: {es_gen_error}")

                # If this was the last attempt, report the error
                if attempt == max_retries:
                    yield self._create_debug_message("es_generation_error", {
                        "error": str(es_gen_error),
                        "attempts": attempt + 1
                    })
                    return

                # Continue to next retry attempt
                logger.info(f"Retrying ES query generation (attempt {attempt + 2}/{max_retries + 1})")
                continue

    async def _execute_vector_query_processor(self, request: QueryRequest, detailed_query: str):
        """Execute Vector query processor step."""
        try:
            # Generate vector query
            vector_query_result = self.vector_query_processor(
                detailed_user_query=detailed_query,
                config={"temperature": self.temperature, "frequency_penalty": self.frequency_penalty}
            )

            logger.info(f"Vector query generation result: {vector_query_result}")
            vector_query = vector_query_result.vector_query
            self.signature_outputs['VectorQueryProcessor'] = {'vector_query': vector_query}

            try:
                # Execute vector query
                vector_query_dict = {
                    "query_text": vector_query,
                    "index": request.vector_db_index,
                    "size": 100
                }
                query_result = execute_vector_query(vector_query_dict)
                rows_count = len(query_result.result) if query_result.result else 0
                logger.info(f"Vector query executed successfully, returned {rows_count} results")

                # Generate markdown and yield results

                # Not sending raw JSON results to frontend
                # Debug information
                yield self._create_debug_message("vector_execution", {
                    "vector_query": vector_query,
                    "vector_index": request.vector_db_index,
                    "rows_count": rows_count,
                    "status": "success"
                })

                yield "query_result", query_result

            except Exception as vector_exec_error:
                logger.error(f"Vector execution exception: {vector_exec_error}")
                error_message = f"Vector search failed: {str(vector_exec_error)}"
                yield self._create_error_message(error_message)

                # Ensure all values are properly handled for JSON serialization
                debug_info = {
                    "vector_query": str(vector_query),
                    "vector_index": str(request.vector_db_index) if request.vector_db_index else None,
                    "error": str(vector_exec_error),
                    "status": "error"
                }
                yield self._create_debug_message("vector_execution", debug_info)

        except Exception as vector_gen_error:
            logger.error(f"Vector query generation failed: {vector_gen_error}")
            yield self._create_debug_message("vector_generation_error", {
                "error": str(vector_gen_error)
            })

    async def _execute_summary_signature(self, request: QueryRequest, detailed_query: str, query_result):
        """Execute summary signature step."""
        try:
            # Convert query results to JSON string
            json_data = self._prepare_json_data(query_result)

            if query_result is None or not query_result.result:
                logger.info("No data available for summary generation")
            else:
                logger.info(f"Generating summary from {len(query_result.result)} results")

            # Generate summary
            summary_result = self.summary_processor(
                detailed_user_query=detailed_query,
                json_results=json_data,
                config={"temperature": self.temperature, "frequency_penalty": self.frequency_penalty}
            )

            # Store summary in signature outputs
            self.signature_outputs['SummarySignature'] = {'summary': summary_result.summary}

            # Yield summary with standardized format
            yield self._create_message("summary", summary_result.summary, "text")

        except Exception as summary_error:
            logger.error(f"Summary generation failed: {summary_error}")
            yield self._create_debug_message("summary_error", {"error": str(summary_error)})

    async def _execute_chart_generator(self, request: QueryRequest, detailed_query: str, query_result):
        """Execute chart generator step."""
        try:
            # Convert query results to JSON string
            json_data = self._prepare_json_data(query_result)

            # Generate chart configuration
            chart_result = self.chart_processor(
                detailed_user_query=detailed_query,
                json_results=json_data,
                config={"temperature": self.temperature, "frequency_penalty": self.frequency_penalty}
            )

            # Check if chart configuration was generated
            if hasattr(chart_result, 'chart_config') and chart_result.chart_config:
                # Store chart configuration in signature outputs
                self.signature_outputs['ChartGenerator'] = {'chart_config': chart_result.chart_config}

                # Yield chart with standardized format
                yield self._create_message("highchart_config", chart_result.chart_config, "chart")
            else:
                logger.warning("Chart generator did not return a chart configuration")

        except Exception as chart_error:
            logger.error(f"Chart generation failed: {chart_error}")
            yield self._create_debug_message("chart_error", {"error": str(chart_error)})

    async def process_query_async(self, request: QueryRequest, session_id=None, message_id=None, test_mode=False):
        """Process query using the redesigned workflow with structured JSON output."""
        try:
            # Set MLflow trace name using session_id and message_id if available
            if session_id and message_id:
                set_mlflow_trace_name(session_id, message_id)

            # Validate required inputs
            if not request.user_query or not request.user_query.strip():
                yield "message", {
                    "type": "debug",
                    "content": {
                        "type": "process_error",
                        "error": "Empty user query provided"
                    },
                    "render_type": "debug",
                    "timestamp": time.time()
                }
                return

            self.temperature = getattr(request, 'temperature', 0.0)
            self.frequency_penalty = getattr(request, 'frequency_penalty', 0.0)
            parsed_history = self._parse_history(request.conversation_history)
            self.signature_outputs = {}  # Reset storage

            # Step 1: ThinkingSignature
            yield "message", {
                "type": "debug",
                "content": {
                    "type": "debug_step",
                    "step": "thinking"
                },
                "render_type": "debug",
                "timestamp": time.time()
            }

            try:
                thinking_result = self.thinking(
                    system_prompt=request.system_prompt,
                    user_query=request.user_query,
                    conversation_history=parsed_history,
                    goal=request.goal,
                    success_criteria=request.success_criteria,
                    config=dict(temperature=self.temperature, frequency_penalty=self.frequency_penalty)
                )

                detailed_query = thinking_result.detailed_user_query
                is_within_context = thinking_result.is_within_context

                self.signature_outputs['ThinkingSignature'] = {
                    'detailed_user_query': detailed_query,
                    'is_within_context': is_within_context
                }

                # Yield detailed_user_query as frontend content
                yield "message", {
                    "type": "detailed_user_query",
                    "content": detailed_query,
                    "render_type": "text",
                    "timestamp": time.time()
                }

                # If query is out of context, yield message and stop processing
                if not is_within_context:
                    yield "message", {
                        "type": "out_of_scope_message",
                        "content": f"I'm sorry, but your query is outside my area of expertise. {detailed_query}",
                        "render_type": "text",
                        "timestamp": time.time()
                    }
                    return

            except Exception as e:
                logger.error(f"ThinkingSignature failed: {e}")

                yield "debug_info", self._convert_to_json_serializable({
                    "type": "process_error",
                    "error": f"Failed to analyze user query: {str(e)}"
                })
                return

            # Step 2: QueryWorkflowPlanner
            yield "message", {
                "type": "debug",
                "content": {
                    "type": "debug_step",
                    "step": "workflow_planning"
                },
                "render_type": "debug",
                "timestamp": time.time()
            }

            try:
                workflow_result = self.workflow_planner(
                    system_prompt=request.system_prompt,
                    detailed_user_query=detailed_query,
                    es_schema_available=request.es_schemas is not None,
                    vector_index_available=request.vector_db_index is not None,
                    es_schema=request.es_schemas,
                    config=dict(temperature=self.temperature, frequency_penalty=self.frequency_penalty)
                )

                workflow_steps = workflow_result.workflow_plan
                is_within_context = workflow_result.is_within_context

                self.signature_outputs['QueryWorkflowPlanner'] = {
                    'workflow_steps': workflow_steps,
                    'is_within_context': is_within_context
                }

                yield "message", {
                    "type": "debug",
                    "content": {
                        "type": "workflow_plan",
                        "workflow_steps": workflow_steps
                    },
                    "render_type": "debug",
                    "timestamp": time.time()
                }

                # If workflow is out of context, yield message and stop processing
                if not is_within_context:
                    yield "message", {
                        "type": "out_of_scope_message",
                        "content": "I'm sorry, but the required workflow for your query is outside my capabilities.",
                        "render_type": "text",
                        "timestamp": time.time()
                    }
                    return

            except Exception as e:
                logger.error(f"QueryWorkflowPlanner failed: {e}")
                # Use default workflow as fallback
                workflow_steps = ["EsQueryProcessor", "SummarySignature"]
                logger.info("Using default workflow as fallback")

            # Override workflow for test mode
            if test_mode:
                if request.es_schemas:
                    workflow_steps = ["EsQueryProcessor"]
                elif request.vector_db_index:
                    workflow_steps = ["VectorQueryProcessor"]
                logger.info(f"Running in test mode: workflow overridden to only use {workflow_steps[0]}")

            # Step 3: Execute workflow steps dynamically
            query_result = None
            has_data = False

            for step in workflow_steps:
                yield "message", {
                    "type": "debug",
                    "content": {
                        "type": "debug_step",
                        "step": f"executing_{step.lower()}"
                    },
                    "render_type": "debug",
                    "timestamp": time.time()
                }

                if step == "EsQueryProcessor":
                    async for result in self._execute_es_query_processor(request, detailed_query):
                        if result[0] == "query_result":
                            query_result = result[1]
                            has_data = query_result is not None and hasattr(query_result, 'result') and len(query_result.result) > 0
                        else:
                            yield result

                elif step == "VectorQueryProcessor":
                    async for result in self._execute_vector_query_processor(request, detailed_query):
                        if result[0] == "query_result":
                            query_result = result[1]
                            has_data = query_result is not None and hasattr(query_result, 'result') and len(query_result.result) > 0
                        else:
                            yield result

                elif step == "SummarySignature":
                    if has_data:
                        async for result in self._execute_summary_signature(request, detailed_query, query_result):
                            yield result
                    else:
                        logger.info("Skipping summary generation because query returned no data")
                        yield "message", {
                            "type": "debug",
                            "content": {
                                "type": "summary_skipped",
                                "reason": "no_data"
                            },
                            "render_type": "debug",
                            "timestamp": time.time()
                        }

                elif step == "ChartGenerator":
                    if has_data:
                        async for result in self._execute_chart_generator(request, detailed_query, query_result):
                            yield result
                    else:
                        logger.info("Skipping chart generation because query returned no data")
                        yield "message", {
                            "type": "debug",
                            "content": {
                                "type": "chart_skipped",
                                "reason": "no_data"
                            },
                            "render_type": "debug",
                            "timestamp": time.time()
                        }

            yield "message", {
                "type": "debug",
                "content": {
                    "type": "process_completed",
                    "reason": "success"
                },
                "render_type": "debug",
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Query processing failed: {e}")

            yield "debug_info", self._convert_to_json_serializable({
                "type": "process_error",
                "error": str(e)
            })
