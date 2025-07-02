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
    - If metadata_found = False: Use EsQueryProcessor (regular Elasticsearch search)
    Both vector and regular data are in the same Elasticsearch index.
    """
    user_query: str = dspy.InputField(desc="User's original question")
    detailed_analysis: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature")
    metadata_found: bool = dspy.InputField(desc="Whether vector metadata was found - if True use VectorQueryProcessor, if False use EsQueryProcessor")
    metadata_summary: str = dspy.InputField(desc="Summary of metadata search results")
    es_schema: str = dspy.InputField(desc="Available Elasticsearch schema")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )

    workflow_plan: List[str] = dspy.OutputField(desc="Ordered list of signatures to execute: If metadata_found=True use ['VectorQueryProcessor', 'SummarySignature'], if metadata_found=False use ['EsQueryProcessor', 'SummarySignature']")
    reasoning: str = dspy.OutputField(desc="Detailed reasoning for the chosen workflow - explain why vector search is used when metadata found vs regular ES when not found")
    primary_data_source: Literal['elasticsearch', 'vector', 'hybrid'] = dspy.OutputField(desc="Primary data source for this query")


class EsQueryProcessor(dspy.Signature):
    """
    Simple Elasticsearch query processor.
    """
    user_query: str = dspy.InputField(desc="User's question")
    es_schema: str = dspy.InputField(desc="Elastic schema")
    conversation_history: Optional[List[Dict]] = dspy.InputField(
        desc="Previous conversation messages for context",
        default=None
    )
    es_instructions = dspy.InputField(desc="Elasticsearch query instructions")

    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning about the query")
    elastic_query: dict = dspy.OutputField(desc="Generated Elasticsearch query")
    elastic_index: str = dspy.OutputField(desc="Index to search in Elasticsearch")
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
