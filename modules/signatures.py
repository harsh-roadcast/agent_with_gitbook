from typing import List, Dict, Optional, Literal

import dspy


class ThinkingSignature(dspy.Signature):
    """
    Analyzes user query to understand what they're really asking for.
    """
    user_query: str = dspy.InputField(desc="User's question or request")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )

    detailed_analysis: str = dspy.OutputField(desc="Detailed analysis of what the user is trying to ask")
    intent: str = dspy.OutputField(desc="Primary intent behind the user's query")
    key_concepts: List[str] = dspy.OutputField(desc="Key concepts and entities the user is asking about")
    search_terms: List[str] = dspy.OutputField(desc="Relevant search terms extracted from the query")


class QueryWorkflowPlanner(dspy.Signature):
    """
    Decides the complete workflow based on metadata search results and ES schema.
    Plans which signatures to call in what sequence.

    Logic:
    - If metadata_found = True: Use VectorQueryProcessor (semantic search on found documents)
    - If metadata_found = False: Check if es_schema contains relevant indices/columns that can fulfill the user query
      - If es_schema has relevant data: Use EsQueryProcessor (regular Elasticsearch search)
      - If es_schema does NOT have relevant data: Skip query processors, go directly to SummarySignature
    - If neither query processor is suitable: Skip both and use only SummarySignature
    - Always consider if ChartGenerator is needed based on user request

    IMPORTANT: Only use EsQueryProcessor if the es_schema actually contains indices and columns that are relevant to the user's query.
    For queries about weather, external APIs, current events, or topics not in the schema, skip query processors entirely.
    """
    user_query: str = dspy.InputField(desc="User's original question")
    detailed_analysis: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature")
    metadata_found: bool = dspy.InputField(desc="Whether vector metadata was found - if True consider VectorQueryProcessor, if False check es_schema relevance")
    metadata_summary: str = dspy.InputField(desc="Summary of metadata search results")
    es_schema: str = dspy.InputField(desc="Available Elasticsearch schema with indices and columns - CAREFULLY CHECK if this schema contains data relevant to the user query")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )

    workflow_plan: List[str] = dspy.OutputField(desc="Ordered list of signatures to execute. Options: 'EsQueryProcessor', 'VectorQueryProcessor', 'SummarySignature', 'ChartGenerator'. ONLY include EsQueryProcessor if es_schema has relevant indices/columns for the query. For queries about weather, external data, or topics not in schema, use only ['SummarySignature'].")
    reasoning: str = dspy.OutputField(desc="Detailed reasoning for the chosen workflow. MUST explain schema relevance check: why EsQueryProcessor was included/excluded based on whether es_schema contains data relevant to the user query. If schema doesn't match query topic, explain why SummarySignature only is appropriate.")
    primary_data_source: Literal['elasticsearch', 'vector', 'hybrid', 'none'] = dspy.OutputField(desc="Primary data source for this query - use 'none' if no data retrieval is needed or schema doesn't match query")


class EsQueryProcessor(dspy.Signature):
    """
    Elasticsearch query processor that returns top 25 results with relevant columns only.
    Should select only the most relevant columns based on the query context plus any user-specified columns.
    """
    user_query: str = dspy.InputField(desc="User's question")
    detailed_analysis: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature")
    es_schema: str = dspy.InputField(desc="Elastic schema showing available fields")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )
    es_instructions = dspy.InputField(desc="Elasticsearch query instructions")

    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning about the query and column selection")
    elastic_query: dict = dspy.OutputField(desc="Generated Elasticsearch query with size=25 and _source field limiting columns to relevant ones only")
    elastic_index: str = dspy.OutputField(desc="Index to search in Elasticsearch")
    selected_columns: List[str] = dspy.OutputField(desc="List of columns selected for the query based on relevance to user query")
    data_json: str = dspy.OutputField(desc="Raw results as JSON")


class VectorSearchDecider(dspy.Signature):
    """
    Analyzes metadata to decide if vector search should be performed.
    """
    user_query: str = dspy.InputField(desc="User's original question")
    detailed_user_query: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature")
    key_concepts: List[str] = dspy.InputField(desc="Key concepts from user query")
    search_terms: List[str] = dspy.InputField(desc="Search terms from user query")

    metadata_query: str = dspy.OutputField(desc="Query to search document metadata")
    should_search_vector: bool = dspy.OutputField(desc="Should we proceed with vector search?")
    reasoning: str = dspy.OutputField(desc="Why vector search is or isn't needed")


class VectorQueryProcessor(dspy.Signature):
    """
    Simple vector search processor.
    """
    user_query: str = dspy.InputField(desc="User's question")
    detailed_user_query: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )

    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning about vector search")
    vector_query: str = dspy.OutputField(desc="Vector search query text")
    data_json: str = dspy.OutputField(desc="Raw results as JSON")


class SummarySignature(dspy.Signature):
    """
    Summarizes results and conversation.
    """
    user_query: str = dspy.InputField(desc="User's question")
    detailed_user_query: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Conversation history as a list of messages",
        default=None
    )
    json_results: str = dspy.InputField(
        desc="JSON results from query processor",
        default=""
    )

    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning about the summary")
    summary: str = dspy.OutputField(desc="Summary of the conversation and results")


class ChartGenerator(dspy.Signature):
    """
    Generates complete Highcharts configuration from data and user query.
    """
    user_query: str = dspy.InputField(desc="User's question")
    detailed_user_query: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature")
    json_results: str = dspy.InputField(desc="JSON data to visualize")

    needs_chart: bool = dspy.OutputField(desc="Does the user want a chart?")
    chart_type: str = dspy.OutputField(desc="Type of chart (line, column, bar, pie)")
    x_axis_column: str = dspy.OutputField(desc="Column name for x-axis")
    y_axis_column: str = dspy.OutputField(desc="Column name for y-axis")
    chart_title: str = dspy.OutputField(desc="Chart title")
    reasoning: str = dspy.OutputField(desc="Why this chart configuration was chosen")


class DocumentMetadataExtractor(dspy.Signature):
    """
    Simple metadata extraction from documents.
    """
    document_text: str = dspy.InputField(desc="Full text content of the document")
    filename: str = dspy.InputField(desc="Original filename of the document")

    document_title: str = dspy.OutputField(desc="Document title")
    document_type: str = dspy.OutputField(desc="Type of document")
    main_topics: List[str] = dspy.OutputField(desc="Main topics covered")
    key_entities: List[str] = dspy.OutputField(desc="Important entities mentioned")
    language: str = dspy.OutputField(desc="Primary language of the document")
    summary: str = dspy.OutputField(desc="Brief summary")
    keywords: List[str] = dspy.OutputField(desc="Key terms")
