from typing import List, Dict, Optional, Literal

import dspy


class DatabaseSelectionSignature(dspy.Signature):
    """
    Signature for selecting the appropriate query based on user query, schemas, and conversation context.
    Considers previous queries and results to make better database selection decisions.

    """
    user_query: str = dspy.InputField(desc="User's question")
    es_schema: str = dspy.InputField(desc="Elastic schema")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )
    database: Literal['Vector', 'Elastic'] = dspy.OutputField(desc="Selected database for query execution (Vector or Elastic)")

class EsQueryProcessor(dspy.Signature):
    """
    Signature for processing Elasticsearch queries based on user input, schema, and conversation history.
    Uses previous context to provide more relevant queries and handle follow-up questions.
    """
    user_query: str = dspy.InputField(desc="User's question")
    es_schema: str = dspy.InputField(desc="Elastic schema")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )
    es_instructions = dspy.InputField(desc="Elasticsearch query instructions")
    elastic_query: dict = dspy.OutputField(desc="Generated Elastic query with only top 25 rows and relevant fields")
    data_json: str = dspy.OutputField(desc="Raw results as JSON")


class VectorQueryProcessor(dspy.Signature):
    """"
    Signature for processing vector search queries based on user input, schema, and conversation history.
    Uses previous context to provide more relevant searches and handle follow-up questions.
    """

    user_query: str = dspy.InputField(desc="User's question")
    es_schema: str = dspy.InputField(desc="Elastic schema")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )
    es_instructions = dspy.InputField(desc="Elasticsearch query instructions")
    elastic_query: dict = dspy.OutputField(desc="Generated vector search query with only top 25 rows and relevant fields")
    data_json: str = dspy.OutputField(desc="Raw results as JSON")

class SummarySignature(dspy.Signature):
    """
    Signature for summarizing conversation history and results.
    """
    user_query: str = dspy.InputField(desc="User's question")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Conversation history as a list of messages",
        default=None
    )
    json_results: str = dspy.InputField(
        desc="JSON results from the query processor",
        default=""
    )
    summary: str = dspy.OutputField(desc="Summary of the conversation")

class ChartAxisSelector(dspy.Signature):
    """
    Signature for processing JSON data and selecting appropriate columns for visualization axes.
    Determines which data columns should be used for x, y, z axes and their labels for Highcharts visualization.
    """
    json_data: str = dspy.InputField(desc="Raw JSON data to be visualized")
    user_query: str = dspy.InputField(desc="User's visualization request", default="")

    x_axis_column: str = dspy.OutputField(desc="Column to use for x-axis")
    y_axis_column: str = dspy.OutputField(desc="Column to use for y-axis")
    z_axis_column: Optional[str] = dspy.OutputField(desc="Column to use for z-axis (if applicable)", default=None)

    x_axis_label: str = dspy.OutputField(desc="Label for x-axis")
    y_axis_label: str = dspy.OutputField(desc="Label for y-axis")
    z_axis_label: Optional[str] = dspy.OutputField(desc="Label for z-axis (if applicable)", default=None)

    chart_title: str = dspy.OutputField(desc="Title for the chart")
    highchart_config: dict = dspy.OutputField(desc="Configuration object for Highcharts")
