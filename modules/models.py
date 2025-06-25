import json
import logging
from typing import Dict, Any, Optional, Tuple

import dspy

from config import settings
# Import our signatures
from modules.signatures import (
    DatabaseSelectionSignature,
    EsQueryProcessor,
    SummarySignature,
    ChartAxisSelector, VectorQueryProcessor
)
from services.search_service import execute_query, execute_vector_query
from util.chart_utils import generate_chart_from_config

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseType:
    """Constants for database types to avoid string comparisons"""
    VECTOR = "Vector"
    ELASTIC = "Elastic"


# Create custom DSPy modules using MCP
class ActionDecider(dspy.Module):
    """
    DSPy module that decides which database to query based on the user query,
    processes the query, and returns relevant data including summaries and visualizations.
    """

    def __init__(self):
        """Initialize the ActionDecider with necessary DSPy components"""
        super().__init__()
        self.predictor = dspy.Predict(DatabaseSelectionSignature)
        self.vector_agent = dspy.ReAct(VectorQueryProcessor, tools=[execute_vector_query])
        self.es_agent = dspy.ReAct(EsQueryProcessor, tools=[execute_query])
        self.summarizer = dspy.ChainOfThought(SummarySignature)
        self.chart_selector = dspy.ChainOfThought(ChartAxisSelector)

    def forward(self, user_query: str, conversation_history: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a user query and return relevant data including summaries and visualizations.

        Args:
            user_query: The user's query string
            conversation_history: Optional conversation history for context

        Returns:
            Dictionary with database, data, summary, and visualization information
        """
        try:
            # Step 1: Select the appropriate database
            database = self._select_database(user_query)

            # Step 2: Execute the query on selected database
            result = self._execute_query(database, user_query)
            if not result:
                logger.warning("No results returned from query processor")
                return {"database": database, "action": "default"}

            # Step 3: Parse results and generate insights
            return self._process_results(database, user_query, result, conversation_history)

        except Exception as e:
            logger.error(f"Error in ActionDecider: {e}", exc_info=True)
            # Return a default action if processing fails
            return {"database": DatabaseType.VECTOR, "action": "default", "error": str(e)}

    def _select_database(self, user_query: str) -> str:
        """
        Select the appropriate database based on the user query.

        Args:
            user_query: The user's query string

        Returns:
            String indicating the selected database type

        Raises:
            ValueError: If the database type is unknown
        """
        try:
            database = self.predictor(
                user_query=user_query,
                database_schema=settings.DATABASE_SCHEMA,
                es_schema=settings.ES_SCHEMA
            ).database
            logger.info(f"Selected database: {database}")
            return database
        except Exception as e:
            logger.error(f"Error selecting database: {e}", exc_info=True)
            # Default to Vector search if database selection fails
            return DatabaseType.VECTOR

    def _execute_query(self, database: str, user_query: str) -> Any:
        """
        Execute the query on the selected database.

        Args:
            database: The selected database type
            user_query: The user's query string

        Returns:
            Query results or None if execution fails

        Raises:
            ValueError: If the database type is unknown
        """
        try:
            if database == DatabaseType.VECTOR:
                logger.info(f"Processing Vector query for: {user_query}")
                result = self.vector_agent(
                    user_query=user_query,
                    es_schema=settings.ES_SCHEMA,
                    es_instructions=settings.ES_INSTRUCTIONS
                )
                logger.debug(f"Vector result received")
                return result

            elif database == DatabaseType.ELASTIC:
                logger.info(f"Processing Elasticsearch query for: {user_query}")
                result = self.es_agent(
                    user_query=user_query,
                    es_schema=settings.ES_SCHEMA,
                    es_instructions=settings.ES_INSTRUCTIONS
                )
                logger.debug(f"Elasticsearch result received")
                return result

            else:
                logger.warning(f"Unknown database type: {database}")
                raise ValueError(f"Unknown database type: {database}")

        except Exception as e:
            logger.error(f"Error executing query on {database}: {e}", exc_info=True)
            return None

    def _parse_json_data(self, result: Any) -> tuple[None, str] | tuple[Any, None]:
        """
        Parse JSON data from query results.

        Args:
            result: Query result object

        Returns:
            Tuple of (parsed_json_data, error_message)
        """
        try:
            if not hasattr(result, 'data_json'):
                return None, "Result missing data_json attribute"

            # Parse the JSON data from the result
            if isinstance(result.data_json, str):
                data_json = json.loads(result.data_json)
            else:
                data_json = result.data_json

            logger.debug(f"JSON data parsed successfully")
            return data_json, None

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}", exc_info=True)
            return None, f"Could not parse result data: {e}"

        except Exception as e:
            logger.error(f"Error parsing JSON data: {e}", exc_info=True)
            return None, f"Error processing result data: {e}"

    def _generate_summary(self, user_query: str, data_json: Dict, conversation_history: Optional[str] = None) -> Any:
        """
        Generate a summary of the results.

        Args:
            user_query: The user's query string
            data_json: Parsed JSON data
            conversation_history: Optional conversation history for context

        Returns:
            Summary object or None if generation fails
        """
        try:
            logger.info(f"Generating summary for: {user_query}")
            return self.summarizer(
                user_query=user_query,
                conversation_history=conversation_history,
                json_results=json.dumps(data_json)
            )
        except Exception as e:
            logger.error(f"Error generating summary: {e}", exc_info=True)
            return None

    def _generate_chart(self, data_json: Dict, user_query: str) -> Tuple[Dict, Optional[str]]:
        """
        Generate chart configuration and HTML.

        Args:
            data_json: Parsed JSON data
            user_query: The user's query string

        Returns:
            Tuple of (chart_data, chart_html) or None if generation fails
        """
        try:
            # Generate chart configuration
            chart_selector = self.chart_selector(
                json_data=json.dumps(data_json),
                chart_type="column",  # Default chart type
                user_query=user_query
            )

            # Extract the chart configuration
            chart_config = chart_selector.highchart_config

            # Generate HTML for OpenWebUI to render
            chart_html = generate_chart_from_config(chart_config)
            logger.info("Chart generated successfully")

            return chart_config, chart_html

        except Exception as e:
            logger.error(f"Error generating chart: {e}", exc_info=True)
            return None, None

    def _process_results(self, database: str, user_query: str, result: Any,
                         conversation_history: Optional[str] = None) -> Dict[str, Any]:
        """
        Process query results to generate summary and visualizations.

        Args:
            database: The selected database type
            user_query: The user's query string
            result: Query results
            conversation_history: Optional conversation history for context

        Returns:
            Dictionary with processed results
        """
        response = {"database": database}

        # Parse JSON data
        data_json, error = self._parse_json_data(result)
        if error:
            response["error"] = error
            return response

        # Extract source data
        try:
            response["data"] = [i['_source'] for i in data_json['hits']['hits']]
        except (KeyError, TypeError) as e:
            logger.warning(f"Could not extract source data: {e}")
            response["data"] = []

        # Generate summary
        summary = self._generate_summary(user_query, data_json, conversation_history)
        if summary:
            response["summary"] = summary.summary

        # Generate chart
        chart_config, chart_html = self._generate_chart(data_json, user_query)
        if chart_config:
            response["chart_config"] = chart_config
            response["chart_html"] = chart_html

        return response
