from typing import List, Dict, Literal, Any

import dspy


class ThinkingSignature(dspy.Signature):
    """
    Analyzes user query in context of conversation history to understand what they're really asking for.
    Uses previous conversation messages to better understand context, references, and follow-up questions.
    """
    system_prompt: str = dspy.InputField(
        desc="System prompt to guide the analysis of user intent based on their query and conversation context. Should define the role of the analyzer and how to interpret user requests in relation to previous messages")

    user_query: str = dspy.InputField(
        desc="The user's current question or request that needs to be analyzed and understood in context")
    conversation_history: List[Dict] = dspy.InputField(
        desc="Complete list of previous conversation messages with only user messages and timestamps, use it to understand the context, references, and follow-up questions.")
    goal: str = dspy.InputField(
        desc="High-level goal or objective of the user query, derived from the detailed analysis. Should summarize what the user is trying to achieve with their question in 1-2 lines")
    success_criteria: str = dspy.InputField(
        desc="Criteria for determining if the analysis successfully captured user intent and context. Should define what constitutes a successful understanding of the user's query and how it aligns with the system prompt and agent's capabilities")

    detailed_user_query: str = dspy.OutputField(
        desc="In maximum 2 lines Deep understanding of the user's query, including intent, context, and any references to previous messages or data. Should capture the underlying purpose of the question and how it relates to the conversation history.")

    is_within_context: bool = dspy.OutputField(
        desc="Boolean indicating whether the user query is within the scope and context of the system prompt. True if the query relates to the agent's defined responsibilities and capabilities, False if the query is outside the agent's domain or asking for unrelated functionality")


class QueryWorkflowPlanner(dspy.Signature):
    """
    Decides workflow based on conversation context, query type, and data availability
    , whether es_schema and vector_index are available or not needs to be considered.

    Decision Logic:
    1. Check detailed_user_query for previous ES/Vector queries → maintain consistency
    2. Analyze detailed_user_query for analytics/reports/analysis questions → prefer ES if schema allows and es_schema_available
    3. Check for information retrieval requests (legal, procedural, guidelines, how-to) → use Vector search if vector_index_available
    4. Check es_schema relevance for new structured data queries → use ES if relevant
    5. If no relevant data sources available, return is_within_context as False and system will return error
    6. ALWAYS include a data query processor (ES or Vector) when ChartGenerator is needed
    7. ALWAYS include a data query processor for follow-up questions that reference previous data
    8. ALWAYS include a data query processor for information retrieval requests

    Always include SummarySignature. Include ChartGenerator based on user intent.
    """
    system_prompt: str = dspy.InputField(desc="System prompt to guide workflow planning decisions based on user query and context, also defines the responsibilities of the workflow planner")

    detailed_user_query: str = dspy.InputField(
        desc="Detailed analysis from ThinkingSignature containing user intent, context understanding, and indicators of analytics/reports questions, information retrieval requests, or references to previous data/charts")
    es_schema: List[Dict[str, Any]] = dspy.InputField(
        desc="Complete Elasticsearch schema definition showing available indices, field mappings, and data types. Analyze to determine if relevant structured data exists for the user's analytical needs")
    es_schema_available: bool = dspy.InputField(desc="Boolean indicating whether the Elasticsearch schema is available for querying. True if schema exists, False if not")
    vector_index_available: bool = dspy.InputField(desc="Boolean indicating whether the vector index is available for querying")

    workflow_plan: List[str] = dspy.OutputField(
        desc="Ordered execution sequence using: 'EsQueryProcessor' (structured data queries), 'VectorQueryProcessor' (semantic document search for information retrieval), 'SummarySignature' (ALWAYS required for text analysis), 'ChartGenerator' (for visualizations). CRITICAL: Always include data processor when ChartGenerator needed, user references previous data, OR for information retrieval requests (legal, procedural, guidelines, how-to)")
    is_within_context: bool = dspy.OutputField(desc="Boolean indicating whether the user query is within the scope and context of the system prompt. True if the query relates to the agent's defined responsibilities and capabilities, False if the query is outside the agent's domain or asking for unrelated functionality")


class EsQueryProcessor(dspy.Signature):
    """
    Elasticsearch query processor that returns top 25 results with relevant business data fields only.
    Automatically excludes ES metadata fields (_id, _index, _score, _type, etc.) and selects only meaningful business columns and all the user requested columns.
    """

    detailed_user_query: str = dspy.InputField(
        desc="User intent analysis from ThinkingSignature providing context about what data aspects are needed and how the query should be structured")

    es_schema: List[Dict[str, Any]] = dspy.InputField(
        desc="Elasticsearch schema with indices, fields, and data types available for querying. Use to select "
             "appropriate index and optimize field selection, appropriate size limit, and query structure size limit can't be more than 100")
    es_instructions: List[str] = dspy.InputField(
        desc="Elasticsearch-specific query guidelines, best practices, and formatting requirements for generating valid queries")

    elastic_query: dict = dspy.OutputField(
        desc="Complete Elasticsearch query object with proper syntax including: query clauses, filters, field selection via _source, size limit of 25, and any aggregations or sorting needed")
    elastic_index: str = dspy.OutputField(
        desc="Specific Elasticsearch index name to query, selected based on schema analysis and user requirements")


class VectorQueryProcessor(dspy.Signature):
    """
    Simple vector search processor. Return a string which can then be converted to embedding to perform vector search.
    Depends on ThinkingSignature to generate the query string and user query and context.
    """

    detailed_user_query: str = dspy.InputField(
        desc="User intent and context analysis from ThinkingSignature to understand what concepts and information patterns to search for in vector space")

    vector_query: str = dspy.OutputField(
        desc="Optimized search string designed for vector embedding conversion. Should capture user intent, key concepts, and context in natural language that will effectively match relevant documents in vector space")


class SummarySignature(dspy.Signature):
    """
    Summarizes results and conversation using data from elastic search or vector search.
    Generates purely text-based summaries without any code, file references, or image descriptions.
    if json_results is empty, it should return an error message indicating no data available for summarization.
    Do not generate any code snippets, file references, JSON data, technical formatting, or image descriptions.
    Do not generate any summary if json_results is empty or invalid.
    """

    detailed_user_query: str = dspy.InputField(
        desc="User intent and context analysis from ThinkingSignature to understand what concepts and information patterns to search for in vector space")


    json_results: str = dspy.InputField(
        desc="Raw JSON data from Elasticsearch or Vector search containing the actual information to analyze, synthesize, and present. May include structured data, documents, or search results with metadata",
        default="")

    summary: str = dspy.OutputField(
        desc="Comprehensive, detailed summary that directly answers the user's question using"
             " search results from elastic or vector search. Should synthesize key information, insights,"
             " and findings from the provided data to provide a clear and concise response to the user's query."
             " If json_results is empty or invalid, return an error message indicating no data available for"
             " summarization, Always return in markdown format with proper headings and bullet points where applicable.")


class ChartGenerator(dspy.Signature):
    """
    Generates complete Highcharts configuration from data and user query.
    DO not generate any code snippets, file references, or image descriptions.
    Do not use javascript function or methods in the chart configuration.
    Do not generate any dummy data or placeholder values.
    Generates a fully specified Highcharts configuration object that can be directly used in a web application.
    """
    detailed_user_query: str = dspy.InputField(
        desc="User intent and context analysis from ThinkingSignature to understand what concepts and information patterns to search for in vector space")

    json_results: str = dspy.InputField(
        desc="Raw JSON data from Elasticsearch or Vector search containing the actual information to analyze, synthesize, and present. May include structured data, documents, or search results with metadata",
        default="")

    chart_config: Dict[str, Any] = dspy.OutputField(desc="Complete Highcharts configuration object that defines the chart type, data series, axes, labels, tooltips, and any additional features needed to visualize the results effectively. Should be fully specified with all required properties for rendering in a web application")



class DocumentMetadataExtractor(dspy.Signature):
    """
    Extracts structured metadata from document content for indexing and searchability.
    Analyzes document text to identify key information patterns and categorize content.
    """
    document_text: str = dspy.InputField(
        desc="Complete text content of the document to be analyzed for metadata extraction. Should include all textual content from the document including headings, body text, and any structured elements")
    filename: str = dspy.InputField(
        desc="Original filename of the document including extension. Used to infer document type, source patterns, and provide additional context for metadata extraction")

    document_title: str = dspy.OutputField(
        desc="Extracted or inferred primary title of the document. Should be the most descriptive heading or main subject that represents the document's primary focus")
    document_type: str = dspy.OutputField(
        desc="Classification of document type based on content structure and patterns (e.g., 'Legal Code', 'Government Gazette', 'Legislative Act', 'Report', 'Manual', 'Policy Document')")
    main_topics: List[str] = dspy.OutputField(
        desc="List of primary subject areas and themes covered in the document. Should identify 3-7 key topics that represent the main content areas for effective categorization")
    key_entities: List[str] = dspy.OutputField(
        desc="Important named entities mentioned in the document including organizations, laws, acts, places, dates, and specific legal or regulatory references that are central to the content")
    language: str = dspy.OutputField(
        desc="Primary language of the document content detected through text analysis (e.g., 'English', 'Hindi', 'Mixed')")
    summary: str = dspy.OutputField(
        desc="Concise summary of the document's main purpose, scope, and key provisions. Should capture the essential information in 2-3 sentences for quick understanding")
    keywords: List[str] = dspy.OutputField(
        desc="Relevant search terms and phrases that would help users find this document. Include both specific technical terms and general concepts that relate to the document content")
