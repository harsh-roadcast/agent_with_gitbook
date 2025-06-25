import json
import logging

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

# Create custom DSPy modules using MCP
class ActionDecider(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(DatabaseSelectionSignature)
        self.vector_agent = dspy.ReAct(VectorQueryProcessor, tools=[execute_vector_query])
        self.es_agent = dspy.ReAct(EsQueryProcessor, tools=[execute_query])
        self.summarizer = dspy.ChainOfThought(SummarySignature)
        self.chart_selector = dspy.ChainOfThought(ChartAxisSelector)

    def forward(self, user_query, conversation_history=None):
        try:
            database = self.predictor(
                user_query=user_query,
                database_schema=settings.DATABASE_SCHEMA,
                es_schema=settings.ES_SCHEMA
            ).database
            logger.info(f"Selected database: {database}")
            if database == "Vector":
                # Process Vector query
                logger.info(f"Processing Vector query for: {user_query}")
                result = self.vector_agent(
                    user_query=user_query,
                    es_schema=settings.ES_SCHEMA,
                    es_instructions=settings.ES_INSTRUCTIONS
                )
                logger.debug(f"Vector result: {result}")
            elif database == "Elastic":
                logger.info(f"Processing Elasticsearch query for: {user_query}")
                # Process Elasticsearch query
                result = self.es_agent(
                    user_query=user_query,
                    es_schema=settings.ES_SCHEMA,
                    es_instructions=settings.ES_INSTRUCTIONS
                )
                logger.debug(f"Elasticsearch result: {result}")
            else:
                logger.warning("Unknown database type, defaulting to Vector")
                raise ValueError(f"Unknown database type: {database}")
            # Generate summary of the results
            logger.info(f"Generating summary for: {user_query}")
            logger.debug(f"Result: {result}")
            if not result:
                logger.warning("No results returned from query processor, returning default action")
                return {"database": database, "action": "default"}

            # Parse the JSON data from the result
            data_json = json.loads(result.data_json) if isinstance(result.data_json, str) else result.data_json
            logger.debug(f"Data JSON: {data_json} type {type(data_json)} type {type(result.data_json)}")
            summary = self.summarizer(
                user_query=user_query,
                conversation_history=conversation_history,
                json_results=json.dumps(data_json)
            )

            logger.debug(f"Summary result: {summary}")
            # Generate chart configuration
            chart_selector = self.chart_selector(
                json_data=json.dumps(data_json),
                chart_type="column",  # Default chart type
                user_query=user_query
            )

            logger.debug(f"Chart selector: {chart_selector}")

            # Extract the chart configuration
            chart_config = chart_selector.highchart_config

            # Generate HTML for OpenWebUI to render using the chart config template
            chart_html = generate_chart_from_config(chart_config)

            logger.info("Chart HTML generated successfully")

            return {
                "database": database,
                "data": [i['_source'] for i in data_json['hits']['hits']],
                "summary": summary.summary,
                "chart_config": chart_selector.highchart_config,
                "chart_html": chart_html,  # Include the HTML for OpenWebUI to render
            }
        except Exception as e:
            logger.error(f"Error in ActionDecider: {e}")
            # Return a default action if prediction fails
            return {"database": "Vector", "action": "default"}
