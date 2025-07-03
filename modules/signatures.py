from typing import List, Dict, Literal

import dspy


class ThinkingSignature(dspy.Signature):
    """
    Analyzes user query in context of conversation history to understand what they're really asking for.
    Uses previous conversation messages to better understand context, references, and follow-up questions.
    """
    user_query: str = dspy.InputField(desc="User's current question or request")
    conversation_history: List[Dict] = dspy.InputField(desc="Previous conversation messages for context - REQUIRED. Analyze this to understand references, follow-ups, and conversation flow")

    detailed_analysis: str = dspy.OutputField(desc="Detailed analysis of what the user is trying to ask, incorporating context from conversation history")
    intent: str = dspy.OutputField(desc="Primary intent behind the user's query, considering conversation context and any references to previous messages")
    context_summary: str = dspy.OutputField(desc="Summary of relevant context from conversation history that affects understanding of current query")


class QueryWorkflowPlanner(dspy.Signature):
    """
    Decides workflow based on conversation context, query type, and data availability.

    Decision Logic:
    1. Check context_summary for previous ES/Vector queries → maintain consistency
    2. Analyze detailed_analysis for analytics/reports/analysis questions → prefer ES if schema allows
    3. Check es_schema relevance for new queries → use ES if relevant
    4. Default to Vector search as fallback
    5. ALWAYS include a data query processor (ES or Vector) when ChartGenerator is needed
    6. ALWAYS include a data query processor for follow-up questions that reference previous data

    Always include SummarySignature. Include ChartGenerator based on user intent.
    """
    user_query: str = dspy.InputField(desc="User's original question")
    detailed_analysis: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature - check if this indicates analytics/reports/analysis type questions that would benefit from ES structured data, or if user references previous data/charts")
    context_summary: str = dspy.InputField(desc="Summary of relevant context from conversation history, including any previous queries, data sources used, and results")
    es_schema: str = dspy.InputField(desc="Available Elasticsearch schema with indices and columns - check if this schema contains data relevant to the user query")

    workflow_plan: List[str] = dspy.OutputField(desc="Ordered list of signatures to execute. Options: 'EsQueryProcessor', 'VectorQueryProcessor', 'SummarySignature', 'ChartGenerator'. MUST ALWAYS include 'SummarySignature'. CRITICAL: ALWAYS include a data query processor (ES or Vector) when ChartGenerator is needed or when user references previous data. Prefer ES for analytics/reports/analysis questions when schema allows. Include ChartGenerator based on user intent.")
    reasoning: str = dspy.OutputField(desc="Reasoning for workflow choice: 1) Previous query context analysis 2) Analytics/reports question analysis from detailed_analysis 3) Whether user references previous data requiring fresh retrieval 4) ES schema relevance 5) Data source decision 6) Why data query processor is included 7) Why SummarySignature included 8) Chart consideration")
    primary_data_source: Literal['elasticsearch', 'vector', 'none'] = dspy.OutputField(desc="Primary data source - prefer 'elasticsearch' for analytics/reports questions when schema allows, maintain consistency with previous queries, or use 'vector' as fallback. Use 'none' only if no data retrieval is needed (rare cases)")


class EsQueryProcessor(dspy.Signature):
    """
    Elasticsearch query processor that returns top 25 results with relevant columns only.
    Should select only the most relevant columns based on the query context plus any user-specified columns.
    """
    user_query: str = dspy.InputField(desc="User's question")
    detailed_analysis: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature")
    context_summary: str = dspy.InputField(desc="Summary of relevant context from conversation history")
    es_schema: str = dspy.InputField(desc="Elastic schema showing available fields")
    es_instructions = dspy.InputField(desc="Elasticsearch query instructions")

    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning about the query and column selection")
    elastic_query: dict = dspy.OutputField(desc="Generated Elasticsearch query with size=25 and _source field limiting columns to relevant ones only")
    elastic_index: str = dspy.OutputField(desc="Index to search in Elasticsearch")
    selected_columns: List[str] = dspy.OutputField(desc="List of columns selected for the query based on relevance to user query")
    data_json: str = dspy.OutputField(desc="Raw results as JSON")


class VectorQueryProcessor(dspy.Signature):
    """
    Simple vector search processor. Return a string which can then be converted to embedding to perform vector search.
    Depends on ThinkingSignature to generate the query string and user query and context.
    """
    user_query: str = dspy.InputField(desc="User's question")
    detailed_analysis: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature")
    context_summary: str = dspy.InputField(desc="Summary of relevant context from conversation history")

    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning about vector search")
    vector_query: str = dspy.OutputField(desc="Generated vector search query string to be converted to embedding to perform vector search")
    data_json: str = dspy.OutputField(desc="Raw results as JSON")


class SummarySignature(dspy.Signature):
    """
    Summarizes results and conversation using data from elastic search or vector search.
    Generates purely text-based summaries without any code, file references, or image descriptions.
    """
    user_query: str = dspy.InputField(desc="User's question")
    detailed_analysis: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature including conversation context")
    context_summary: str = dspy.InputField(desc="Summary of relevant context from conversation history")
    json_results: str = dspy.InputField(
        desc="JSON results from ElasticSearch or Vector query processor - contains the actual data to analyze and summarize",
        default=""
    )

    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning about the summary based on the query results and conversation context")
    summary: str = dspy.OutputField(desc="Comprehensive text-based summary that directly answers the user query using the provided search results. MUST be purely textual - no code snippets, file references, image descriptions, or technical formatting. Focus on insights, findings, and explanations in natural language.")


class ChartGenerator(dspy.Signature):
    """
    Generates complete Highcharts configuration from data and user query.
    """
    user_query: str = dspy.InputField(desc="User's question")
    detailed_analysis: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature")
    context_summary: str = dspy.InputField(desc="Summary of relevant context from conversation history")
    json_results: str = dspy.InputField(desc="JSON data to visualize")

    needs_chart: bool = dspy.OutputField(desc="Does the user want a chart?")
    chart_type: str = dspy.OutputField(desc="Type of chart (line, column, bar, pie)")
    x_axis_column: str = dspy.OutputField(desc="Column name for x-axis")
    y_axis_column: str = dspy.OutputField(desc="Column name for y-axis")
    chart_title: str = dspy.OutputField(desc="Chart title")
    reasoning: str = dspy.OutputField(desc="Why this chart configuration was chosen")
