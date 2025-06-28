from typing import List, Dict, Optional, Literal

import dspy


class QueryWorkflowPlanner(dspy.Signature):
    """
    Signature for planning the workflow of signatures to execute based on user query.
    Determines the sequence of steps needed to fulfill the user's request, including:
    - Data retrieval from databases
    - Summary generation (ALWAYS included for all queries)
    - Chart/visualization creation (ONLY if explicitly requested by user)
    - Query modifications
    - Follow-up visualization requests (reuse previous data)

    IMPORTANT: SummarySignature is ALWAYS included in the workflow for every query.
    IMPORTANT: Only include ChartAxisSelector if user explicitly asks for chart, graph, visualization, or plot.
    IMPORTANT: For follow-up visualization requests (e.g., "show in bar graph" after a data query),
               only use ChartAxisSelector and SummarySignature - do NOT re-execute data queries.
    Default behavior should be to return data with summary, unless user specifically requests charts.

    AVAILABLE SIGNATURE NAMES (use exactly these names):
    - DatabaseSelectionSignature: Select database type (Vector or Elastic)
    - EsQueryProcessor: Execute Elasticsearch queries
    - VectorQueryProcessor: Execute vector search queries
    - SummarySignature: Generate summaries (ALWAYS included)
    - ChartAxisSelector: Create charts/visualizations (only if explicitly requested)

    This signature acts as the orchestrator that guides the query agent on which
    signatures to call and in what order.
    """
    user_query: str = dspy.InputField(desc="User's question or request")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )

    # Output fields defining the workflow
    workflow_steps: List[str] = dspy.OutputField(
        desc="Ordered list of EXACT signature names to execute. MUST use these exact names: 'DatabaseSelectionSignature', 'EsQueryProcessor', 'VectorQueryProcessor', 'SummarySignature', 'ChartAxisSelector'. SummarySignature MUST ALWAYS be included for every query. For follow-up visualization requests that reference previous data (e.g., 'show in bar graph' after data query), use ONLY: ['ChartAxisSelector', 'SummarySignature']. For new data queries use: ['DatabaseSelectionSignature', 'EsQueryProcessor', 'SummarySignature'] or ['DatabaseSelectionSignature', 'VectorQueryProcessor', 'SummarySignature']."
    )
    requires_data_retrieval: bool = dspy.OutputField(desc="Whether the query requires fetching NEW data from a database (False for follow-up visualization requests)")
    requires_summary: bool = dspy.OutputField(desc="Always True - summary is always generated for every query")
    requires_visualization: bool = dspy.OutputField(desc="Whether the user explicitly asked for a chart, graph, visualization, or plot in their query")
    is_modification_request: bool = dspy.OutputField(desc="Whether this is a request to modify a previous query")
    is_followup_visualization: bool = dspy.OutputField(desc="Whether this is a follow-up request to visualize previously retrieved data (e.g., 'show in bar graph' after data query)")
    modification_type: Optional[Literal['query_change', 'new_chart', 'chart_modification', 'followup_visualization']] = dspy.OutputField(
        desc="Type of modification if this is a modification request. Use 'followup_visualization' for requests to visualize previous data", default=None
    )
    expected_final_output: Literal['data_and_summary', 'summary_and_chart', 'modified_query', 'chart_from_previous_data'] = dspy.OutputField(
        desc="The type of final output the user expects - always includes summary, optionally includes chart. Use 'chart_from_previous_data' for follow-up visualization requests"
    )
    explanation: str = dspy.OutputField(desc="Brief explanation of the planned workflow and reasoning, noting whether this reuses previous data for visualization or fetches new data")


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


class EsQueryProcessor(dspy.Signature):
    """
    Signature for processing Elasticsearch queries based on user input, schema, and conversation history.
    Uses previous context to provide more relevant queries and handle follow-up questions.
    If user is asking something about previous query results, reuses the previous elastic query. Max size of results is 25 rows.

    IMPORTANT: Only select fields that are relevant to the user's query. Analyze the user's question to determine
    which specific fields they need and include only those in the _source field of the Elasticsearch query.
    This makes queries more efficient and responses more focused.

    This signature uses ReAct pattern to enable function calling for data retrieval.
    Results are formatted in markdown for better readability.
    """
    user_query: str = dspy.InputField(desc="User's question")
    es_schema: str = dspy.InputField(desc="Elastic schema")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )
    es_instructions = dspy.InputField(desc="Elasticsearch query instructions")

    # ReAct outputs for reasoning and action
    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning about what query to construct and execute, including which specific fields are needed for this query")
    selected_fields: List[str] = dspy.OutputField(desc="List of specific field names that are relevant to the user's query and should be included in the _source parameter. Only include fields the user explicitly asked for or are needed to answer their question.")
    elastic_query: dict = dspy.OutputField(desc="Generated Elastic query with only top 25 rows and ONLY the relevant fields specified in selected_fields in the _source parameter")
    data_json: str = dspy.OutputField(desc="Raw results as JSON retrieved from function call")
    data_markdown: str = dspy.OutputField(desc="Results formatted in markdown format with proper tables, headers, and structure for better readability")


class VectorQueryProcessor(dspy.Signature):
    """
    Signature for processing vector search queries based on user input, schema, and conversation history.
    Uses previous context to provide more relevant searches and handle follow-up questions.

    This signature uses ReAct pattern to enable function calling for data retrieval.
    """

    user_query: str = dspy.InputField(desc="User's question")
    es_schema: str = dspy.InputField(desc="Elastic schema")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )
    es_instructions = dspy.InputField(desc="Elasticsearch query instructions")

    # ReAct outputs for reasoning and action
    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning about what vector search query to construct and execute")
    elastic_query: dict = dspy.OutputField(desc="Generated vector search query with only top 25 rows and relevant fields")
    data_json: str = dspy.OutputField(desc="Raw results as JSON retrieved from function call")


class SummarySignature(dspy.Signature):
    """
    Signature for summarizing conversation history and results.
    Uses Chain of Thought reasoning to provide better summaries.
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

    # Chain of Thought outputs
    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning about how to summarize the data and conversation context")
    summary: str = dspy.OutputField(desc="Summary of the conversation and results")


class ChartAxisSelector(dspy.Signature):
    """
    Determines which data columns should be used for x, y, z axes and their labels for Highcharts visualization.
    Uses conversation history to understand follow-up visualization requests.
    Only outputs basic chart parameters - the actual chart config is generated by a separate function.
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
