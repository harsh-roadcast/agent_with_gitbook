from typing import List, Dict, Optional, Literal

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
    key_concepts: List[str] = dspy.OutputField(desc="Key concepts and entities the user is asking about, including any referenced from conversation history")
    search_terms: List[str] = dspy.OutputField(desc="Relevant search terms extracted from both the current query and conversation context")
    context_summary: str = dspy.OutputField(desc="Summary of relevant context from conversation history that affects understanding of current query")


class QueryWorkflowPlanner(dspy.Signature):
    """
    Decides the complete workflow based on metadata search results, ES schema, and conversation history.
    Plans which signatures to call in what sequence, considering previous conversation context and data availability.

    Logic:
    - PRIORITY: For follow-up questions, ALWAYS regenerate data queries to ensure fresh and complete results
    - FIRST: Analyze conversation_history to check if this is a follow-up question or new request
    - For follow-up questions (visualizations, different analysis, refined queries): ALWAYS include query processors to regenerate data
    - If NO relevant data exists in conversation context OR data is insufficient/outdated, ALWAYS regenerate searches
    - If conversation_history indicates need for fresh data or different search approach, prioritize new query execution
    - If metadata_found = True: Use VectorQueryProcessor (semantic search on found documents)
    - If metadata_found = False: Check if es_schema contains relevant indices/columns that can fulfill the user query
      - If es_schema has relevant data: Use EsQueryProcessor (regular Elasticsearch search)
      - If es_schema does NOT have relevant data: Skip query processors, proceed to SummarySignature
    - Consider conversation flow: ALWAYS RERUN searches when:
      * Follow-up questions about existing data (even for visualization changes)
      * No elastic data exists in conversation context
      * Previous query results are insufficient for current question
      * User asks follow-up questions that reference previous data
      * Vector or JSON data is missing from context but needed for the query
      * User requests different chart types or visualization changes
    - ALWAYS include SummarySignature in the workflow plan (required for all queries)
    - Consider if ChartGenerator is needed based on user request and conversation context (optional)

    IMPORTANT:
    - PRIORITY: Follow-up questions should ALWAYS regenerate data, even if previous data exists in conversation
    - Check conversation_history for existing elastic data/query results - if this is a follow-up, regenerate anyway
    - Analyze conversation_history to determine if current query needs fresh data retrieval or can build on previous results
    - Only use EsQueryProcessor if the es_schema actually contains indices and columns that are relevant to the user's query
    - For ALL follow-up questions that reference previous data or request changes, rerun appropriate search processors
    - If vector or normal JSON data doesn't exist in context but is needed, always include the appropriate processor
    - For queries about weather, external APIs, current events, or topics not in the schema, skip query processors but still include SummarySignature
    """
    user_query: str = dspy.InputField(desc="User's original question")
    detailed_analysis: str = dspy.InputField(desc="Detailed analysis from ThinkingSignature including conversation context and whether this is a follow-up question")
    metadata_found: bool = dspy.InputField(desc="Whether vector metadata was found - if True consider VectorQueryProcessor, if False check es_schema relevance")
    metadata_summary: str = dspy.InputField(desc="Summary of metadata search results")
    es_schema: str = dspy.InputField(desc="Available Elasticsearch schema with indices and columns - CAREFULLY CHECK if this schema contains data relevant to the user query")
    conversation_history: List[Dict] = dspy.InputField(desc="Previous conversation messages for context - REQUIRED. Analyze this to identify follow-up questions, check if elastic data/query results exist, determine if current query needs fresh data retrieval, references previous results, or requires different search approach based on conversation flow")

    workflow_plan: List[str] = dspy.OutputField(desc="Ordered list of signatures to execute. Options: 'EsQueryProcessor', 'VectorQueryProcessor', 'SummarySignature', 'ChartGenerator'. MUST ALWAYS include 'SummarySignature'. CRITICAL: For follow-up questions (even visualization changes), ALWAYS include appropriate query processors to regenerate data. PRIORITY: If this is a follow-up question or elastic data/query results don't exist in conversation_history or are insufficient, include appropriate query processors to regenerate data. Consider conversation_history: if user asks follow-up questions needing fresh data, different time periods, visualization changes, or missing vector/JSON data, include appropriate query processors even if similar searches were done before. For queries about external topics not in schema, use ['SummarySignature'] or ['SummarySignature', 'ChartGenerator'] if chart needed.")
    reasoning: str = dspy.OutputField(desc="Detailed reasoning for the chosen workflow. MUST explain: 1) Whether this is a follow-up question based on conversation_history analysis 2) Analysis of existing data in conversation_history (elastic data, query results, vector/JSON data) 3) How conversation_history influenced the decision 4) Whether fresh data retrieval is needed based on follow-up nature, missing context or conversation needs 5) Schema relevance check for EsQueryProcessor 6) Why SummarySignature is included (required). For follow-up questions, ALWAYS explain why data regeneration is needed even if previous data exists. If regenerating searches due to follow-up nature, missing data or conversation context, explain specifically what triggers regeneration.")
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
