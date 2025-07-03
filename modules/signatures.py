from typing import List, Dict, Literal

import dspy


class ThinkingSignature(dspy.Signature):
    """
    Analyzes user query in context of conversation history to understand what they're really asking for.
    Uses previous conversation messages to better understand context, references, and follow-up questions.
    """
    user_query: str = dspy.InputField(
        desc="The user's current question or request that needs to be analyzed and understood in context")
    conversation_history: List[Dict] = dspy.InputField(
        desc="Complete list of previous conversation messages with roles and content. REQUIRED for understanding references like 'that data', 'previous chart', follow-up questions, and conversation flow patterns")

    detailed_analysis: str = dspy.OutputField(
        desc="Concise analysis (6-8 lines max) of user intent including: what they're asking for, references to previous data/results, follow-up question indicators, analysis type needed, and key concepts involved")
    intent: str = dspy.OutputField(
        desc="Primary purpose behind the user's query in simple terms (e.g., 'data analysis', 'chart creation', 'follow-up visualization', 'information retrieval', 'comparison analysis')")
    context_summary: str = dspy.OutputField(
        desc="Brief summary (6-8 lines max) of relevant conversation context: previous data sources (ES/Vector), query types executed, data retrieved, visualizations created, and ongoing analytical themes affecting current request")


class QueryWorkflowPlanner(dspy.Signature):
    """
    Decides workflow based on conversation context, query type, and data availability.

    Decision Logic:
    1. Check context_summary for previous ES/Vector queries → maintain consistency
    2. Analyze detailed_analysis for analytics/reports/analysis questions → prefer ES if schema allows
    3. Check for information retrieval requests (legal, procedural, guidelines, how-to) → use Vector search
    4. Check es_schema relevance for new structured data queries → use ES if relevant
    5. Default to Vector search as fallback for information needs
    6. ALWAYS include a data query processor (ES or Vector) when ChartGenerator is needed
    7. ALWAYS include a data query processor for follow-up questions that reference previous data
    8. ALWAYS include a data query processor for information retrieval requests

    Always include SummarySignature. Include ChartGenerator based on user intent.
    """
    user_query: str = dspy.InputField(desc="The original user question that needs workflow planning")
    detailed_analysis: str = dspy.InputField(
        desc="Detailed analysis from ThinkingSignature containing user intent, context understanding, and indicators of analytics/reports questions, information retrieval requests, or references to previous data/charts")
    context_summary: str = dspy.InputField(
        desc="Conversation context including previous query patterns (ES/Vector usage), data sources accessed, results obtained, and ongoing analytical themes influencing data source selection")
    es_schema: str = dspy.InputField(
        desc="Complete Elasticsearch schema definition showing available indices, field mappings, and data types. Analyze to determine if relevant structured data exists for the user's analytical needs")

    workflow_plan: List[str] = dspy.OutputField(
        desc="Ordered execution sequence using: 'EsQueryProcessor' (structured data queries), 'VectorQueryProcessor' (semantic document search for information retrieval), 'SummarySignature' (ALWAYS required for text analysis), 'ChartGenerator' (for visualizations). CRITICAL: Always include data processor when ChartGenerator needed, user references previous data, OR for information retrieval requests (legal, procedural, guidelines, how-to)")
    reasoning: str = dspy.OutputField(
        desc="Concise justification covering: 1) Context analysis 2) Analytics detection 3) Information retrieval detection 4) Data reference handling 5) Schema relevance 6) Data source selection 7) Processor inclusion rationale 8) Summary necessity 9) Chart generation decision")
    primary_data_source: Literal['elasticsearch', 'vector', 'none'] = dspy.OutputField(
        desc="Selected data source: 'elasticsearch' for structured analytics/reports when schema matches or previous ES usage detected, 'vector' for information retrieval (legal, procedural, guidelines, how-to) or as fallback, 'none' ONLY for pure conversational queries not requiring any information retrieval")


class EsQueryProcessor(dspy.Signature):
    """
    Elasticsearch query processor that returns top 25 results with relevant business data fields only.
    Automatically excludes ES metadata fields (_id, _index, _score, _type, etc.) and selects only meaningful business columns and all the user requested columns.
    """
    user_query: str = dspy.InputField(desc="The user's question that will be translated into an Elasticsearch query")
    detailed_analysis: str = dspy.InputField(
        desc="User intent analysis from ThinkingSignature providing context about what data aspects are needed and how the query should be structured")
    context_summary: str = dspy.InputField(
        desc="Conversation context including previous ES queries, data patterns accessed, and analytical themes to maintain consistency in data retrieval approach")
    es_schema: str = dspy.InputField(
        desc="Elasticsearch schema with indices, fields, and data types available for querying. Use to select "
             "appropriate index and optimize field selection, appropriate size limit, and query structure size limit can't be more than 100")
    es_instructions = dspy.InputField(
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
    user_query: str = dspy.InputField(
        desc="The user's question that needs to be transformed into an effective vector search query")
    detailed_analysis: str = dspy.InputField(
        desc="User intent and context analysis from ThinkingSignature to understand what concepts and information patterns to search for in vector space")
    context_summary: str = dspy.InputField(
        desc="Conversation context including previous vector searches, document types accessed, and search patterns to maintain consistency and improve search relevance")

    reasoning: str = dspy.OutputField(
        desc="Explanation of: search strategy chosen, key concepts extracted for vector matching, how context influences search terms, and expected document types or content patterns to find")
    vector_query: str = dspy.OutputField(
        desc="Optimized search string designed for vector embedding conversion. Should capture user intent, key concepts, and context in natural language that will effectively match relevant documents in vector space")
    data_json: str = dspy.OutputField(
        desc="Raw JSON string containing vector search results with document content, metadata, and relevance scores, formatted for downstream summary and analysis processing")


class SummarySignature(dspy.Signature):
    """
    Summarizes results and conversation using data from elastic search or vector search.
    Generates purely text-based summaries without any code, file references, or image descriptions.
    """
    user_query: str = dspy.InputField(
        desc="The original user question that needs to be answered through data analysis and summarization")
    detailed_analysis: str = dspy.InputField(
        desc="User intent and context analysis from ThinkingSignature providing understanding of what insights, patterns, or specific information the user is seeking")
    context_summary: str = dspy.InputField(
        desc="Conversation context including previous queries, data accessed, and analytical themes to ensure summary builds appropriately on prior discussion and maintains consistency")
    json_results: str = dspy.InputField(
        desc="Raw JSON data from Elasticsearch or Vector search containing the actual information to analyze, synthesize, and present. May include structured data, documents, or search results with metadata",
        default="")

    reasoning: str = dspy.OutputField(
        desc="Analysis process explanation covering: data interpretation approach, key insights identified, how results address user query, integration with conversation context, and summary construction logic")
    summary: str = dspy.OutputField(
        desc="Comprehensive, detailed summary that directly answers the user's question using search results. Can be as long as needed to fully address the query. MUST be purely textual with natural language explanations, insights, and findings. NO code snippets, file references, JSON data, technical formatting, or image descriptions. Focus on data insights, trends, patterns, and actionable information in readable prose")


class ChartGenerator(dspy.Signature):
    """
    Generates complete Highcharts configuration from data and user query.
    """
    user_query: str = dspy.InputField(
        desc="The user's question or request that involves data visualization, including any specific chart type preferences or visualization requirements")
    detailed_analysis: str = dspy.InputField(
        desc="User intent analysis from ThinkingSignature indicating visualization needs, chart type preferences, and how the chart should support the analytical goals")
    context_summary: str = dspy.InputField(
        desc="Conversation context including previous visualizations created, chart types used, and ongoing analytical themes to maintain consistency in visualization approach")
    json_results: str = dspy.InputField(
        desc="Raw JSON data from query processors containing the actual dataset to visualize. Should include numerical data, categories, and metadata needed for chart construction")

    needs_chart: bool = dspy.OutputField(
        desc="Determination of whether the user's request actually requires a visual chart based on query intent, data availability, and visualization value for answering their question")
    chart_type: str = dspy.OutputField(
        desc="Optimal chart type selection from available options (line, column, bar, pie, scatter) based on data characteristics, user intent, and analytical purpose")
    x_axis_column: str = dspy.OutputField(
        desc="Field name from the data to use for x-axis values, typically categorical data, time series, or independent variables that provide meaningful grouping")
    y_axis_column: str = dspy.OutputField(
        desc="Field name from the data to use for y-axis values, typically numerical measurements, counts, or dependent variables that show the primary metric of interest")
    chart_title: str = dspy.OutputField(
        desc="Descriptive, user-friendly title for the chart that clearly communicates what the visualization shows and its relevance to the user's question")
    reasoning: str = dspy.OutputField(
        desc="Justification for chart design decisions including: why this chart type is optimal, how axis selections support analysis goals, title choice rationale, and how the visualization addresses user needs")


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
