from typing import List, Dict, Optional, Literal

import dspy


class DatabaseSelectionSignature(dspy.Signature):
    """
    Signature for selecting the appropriate query based on user query, schemas, and conversation context.
    Considers previous queries and results to make better database selection decisions.
    Detects follow-up queries that reference previous conversation context.

    """
    user_query: str = dspy.InputField(desc="User's question")
    es_schema: str = dspy.InputField(desc="Elastic schema")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )
    database: Literal['Vector', 'Elastic'] = dspy.OutputField(desc="Selected database for query execution (Vector or Elastic)")
    is_followup_query: bool = dspy.OutputField(desc="Whether this query references previous conversation context and should be handled as a follow-up")
    followup_action: Optional[Literal['visualization', 'reuse_data', 'modify_query']] = dspy.OutputField(desc="Type of follow-up action if this is a follow-up query", default=None)

class EsQueryProcessor(dspy.Signature):
    """
    Signature for processing Elasticsearch queries based on user input, schema, and conversation history.
    Uses previous context to provide more relevant queries and handle follow-up questions.
    If user is asking something about previous query results, reuses the previous elastic query.
    """
    user_query: str = dspy.InputField(desc="User's question")
    es_schema: str = dspy.InputField(desc="Elastic schema")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )
    es_instructions = dspy.InputField(desc="Elasticsearch query instructions")

    is_reusing_previous_query: bool = dspy.OutputField(desc="Whether this request should reuse a previous query instead of generating a new one")
    elastic_query: dict = dspy.OutputField(desc="Generated Elastic query with only top 25 rows and relevant fields, or reused previous query if is_reusing_previous_query is True")
    data_json: str = dspy.OutputField(desc="Raw results as JSON")
    reuse_reason: Optional[str] = dspy.OutputField(desc="Explanation of why previous query is being reused", default=None)


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
    Uses conversation history to understand follow-up visualization requests.
    """
    json_data: str = dspy.InputField(desc="Raw JSON data to be visualized")
    user_query: str = dspy.InputField(desc="User's visualization request")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )

    chart_type: str = dspy.OutputField(desc="Type of chart to generate (line, column, bar, pie, scatter, etc.)")
    x_axis_column: str = dspy.OutputField(desc="Column to use for x-axis")
    y_axis_column: str = dspy.OutputField(desc="Column to use for y-axis")
    z_axis_column: Optional[str] = dspy.OutputField(desc="Column to use for z-axis (if applicable)", default=None)

    x_axis_label: str = dspy.OutputField(desc="Label for x-axis")
    y_axis_label: str = dspy.OutputField(desc="Label for y-axis")
    z_axis_label: Optional[str] = dspy.OutputField(desc="Label for z-axis (if applicable)", default=None)

    chart_title: str = dspy.OutputField(desc="Title for the chart")
    highchart_config: dict = dspy.OutputField(desc="Configuration object for Highcharts")


class FollowUpQueryProcessor(dspy.Signature):
    """
    Signature for processing follow-up queries that reference previous conversation context.
    Determines if current query is a follow-up that needs previous data and what type of action is requested.
    """
    user_query: str = dspy.InputField(desc="Current user's question")
    conversation_history: List[Dict] = dspy.InputField(desc="Previous conversation messages for context")

    is_followup: bool = dspy.OutputField(desc="Whether this query is a follow-up to previous queries")
    action_type: Literal['visualization', 'data_query', 'modification'] = dspy.OutputField(desc="Type of action requested")
    previous_query_to_reuse: Optional[str] = dspy.OutputField(desc="Previous query to re-execute if needed", default=None)
    visualization_type: Optional[str] = dspy.OutputField(desc="Type of visualization requested (line, bar, pie, etc.)", default=None)
