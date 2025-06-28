import logging
import logging
import os
from typing import List

from elasticsearch import Elasticsearch

try:
    from sentence_transformers import SentenceTransformer
    _has_sentence_transformers = True
except ImportError:
    _has_sentence_transformers = False
    logging.warning("sentence_transformers not installed. Vector search will not be available.")

# Configure logging
logger = logging.getLogger(__name__)


# Elasticsearch Configuration
ES_HOST = os.getenv('ES_HOST', 'https://62.72.41.235:9200')
ES_USERNAME = os.getenv('ES_USERNAME', 'elastic')
ES_PASSWORD = os.getenv('ES_PASSWORD', 'GGgCYcnpA_0R_fT5TfFY')
ES_VERIFY_CERTS = os.getenv('ES_VERIFY_CERTS', 'False').lower() == 'true'

# Initialize the sentence transformer model (loaded once)
_model = None

def get_sentence_transformer_model():
    """
    Returns a sentence transformer model for generating embeddings.
    Loads the model once and reuses it.
    """
    global _model
    if not _has_sentence_transformers:
        raise ImportError("sentence_transformers not installed. Please install it first.")

    if _model is None:
        logger.info("Loading sentence transformer model")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Sentence transformer model loaded")
    return _model


def get_es_client():
    """
    Returns an Elasticsearch client instance using environment variables or defaults.
    """
    return Elasticsearch(
        [ES_HOST],
        http_auth=(ES_USERNAME, ES_PASSWORD),
        verify_certs=ES_VERIFY_CERTS
    )


def execute_query(es_query: dict) -> dict:
    """
    Execute a standard Elasticsearch query

    Args:
        es_query: A dict with 'index', 'body', and optional 'size' keys

    Returns:
        Dictionary with the query results
    """
    logger.info(f"Executing standard ES query: {es_query}")

    # Validate that we have a proper ES query
    if not es_query or not isinstance(es_query, dict):
        error_msg = "Invalid or missing Elasticsearch query - cannot proceed"
        logger.error(error_msg)
        return {"error": error_msg, "query_type": "standard", "stop_processing": True}

    # Validate that query body is properly structured
    if 'body' not in es_query or not es_query.get('body'):
        error_msg = "Elasticsearch query body not generated or is empty - cannot proceed"
        logger.error(error_msg)
        return {"error": error_msg, "query_type": "standard", "stop_processing": True}

    es = get_es_client()
    try:
        index = es_query.get('index')
        body = es_query.get('body', {})

        if not index:
            error_msg = "Missing 'index' in Elasticsearch query - cannot proceed"
            logger.error(error_msg)
            return {"error": error_msg, "query_type": "standard", "stop_processing": True}

        # ENFORCE MAXIMUM 25 RESULTS - Remove any size parameters and force to 25
        if 'size' in body:
            body.pop('size')  # Remove size from body

        # Force maximum size to 25, no matter what was requested
        max_size = 25
        logger.info(f"Enforcing maximum result limit of {max_size} records")

        # Execute with enforced size limit and timeout
        result = es.search(index=index, body=body, size=max_size, request_timeout=30)

        # Check if the result actually contains data
        total_hits = result.get('hits', {}).get('total', {}).get('value', 0)
        has_aggregations = 'aggregations' in result

        if total_hits == 0 and not has_aggregations:
            error_msg = f"Elasticsearch query returned 0 results for index {index} - cannot proceed"
            logger.error(error_msg)
            return {"error": error_msg, "query_type": "standard", "stop_processing": True}

        logger.info(f"ES query successful - found {total_hits} results")
        return {"success": True, "result": result, "query_type": "standard"}

    except Exception as e:
        error_msg = f"Elasticsearch query execution failed: {str(e)} - cannot proceed"
        logger.error(error_msg)
        return {"error": error_msg, "query_type": "standard", "stop_processing": True}


def generate_embedding(text: str) -> List[float]:
    """
    Generate an embedding vector for the given text using sentence transformers.

    Args:
        text: The query text to embed

    Returns:
        A list of floating point values representing the text embedding
    """
    try:
        model = get_sentence_transformer_model()
        embedding = model.encode(text).tolist()  # Convert to list of floats
        logger.debug(f"Generated embedding of length {len(embedding)} for text: {text[:50]}...")
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise


def execute_vector_query(es_query: dict) -> dict:
    """
    Execute a vector search query using Elasticsearch's cosine similarity.

    Args:
        es_query: A dict with 'index', 'query_text', and optional 'size' keys

    Returns:
        Dictionary with the query results
    """
    logger.info(f"Executing vector search ES query: {es_query}")

    # Validate that we have a proper vector query
    if not es_query or not isinstance(es_query, dict):
        error_msg = "Invalid or missing vector search query - cannot proceed"
        logger.error(error_msg)
        return {"error": error_msg, "query_type": "vector", "stop_processing": True}

    es = get_es_client()
    try:
        index = es_query.get('index')
        query_text = es_query.get('query_text', '')
        field_name = es_query.get('embedding_field', 'embedding')

        if not index:
            error_msg = "Missing 'index' in vector search query - cannot proceed"
            logger.error(error_msg)
            return {"error": error_msg, "query_type": "vector", "stop_processing": True}

        if not query_text:
            error_msg = "Missing 'query_text' for vector search - cannot proceed"
            logger.error(error_msg)
            return {"error": error_msg, "query_type": "vector", "stop_processing": True}

        # Generate embedding from the query text
        try:
            embedding = generate_embedding(query_text)
        except Exception as e:
            error_msg = f"Failed to generate embedding for vector search: {str(e)} - cannot proceed"
            logger.error(error_msg)
            return {"error": error_msg, "query_type": "vector", "stop_processing": True}

        # ENFORCE MAXIMUM 25 RESULTS - Force maximum size to 25, no matter what was requested
        max_size = 25
        logger.info(f"Enforcing maximum result limit of {max_size} records for vector search")

        # Build cosine similarity query with enforced size limit
        vector_query = {
            "size": max_size,
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": f"cosineSimilarity(params.query_vector, '{field_name}') + 1.0",
                        "params": {"query_vector": embedding}
                    }
                }
            }
        }

        # Add any filters from the original query if they exist
        if 'body' in es_query and 'query' in es_query['body']:
            if 'bool' in es_query['body']['query'] and 'filter' in es_query['body']['query']['bool']:
                vector_query['query']['script_score']['query'] = {
                    "bool": {
                        "filter": es_query['body']['query']['bool']['filter']
                    }
                }

        logger.debug(f"Vector query: {vector_query}")

        # Execute with a timeout to prevent hanging
        result = es.search(index=index, body=vector_query, request_timeout=30)

        # Check if the result actually contains data
        total_hits = result.get('hits', {}).get('total', {}).get('value', 0)
        if total_hits == 0:
            error_msg = f"Vector search returned 0 results for index {index} - cannot proceed"
            logger.error(error_msg)
            return {"error": error_msg, "query_type": "vector", "stop_processing": True}

        logger.info(f"Vector search successful - found {total_hits} results")
        return {"success": True, "result": result, "query_type": "vector"}

    except Exception as e:
        error_msg = f"Vector search execution failed: {str(e)} - cannot proceed"
        logger.error(error_msg)
        return {"error": error_msg, "query_type": "vector", "stop_processing": True}


def convert_json_to_markdown(data: dict, title: str = "Query Results") -> str:
    """
    Convert Elasticsearch JSON query results to markdown formatted table.

    This function is designed to be called by LLM agents to format raw Elasticsearch
    query results into human-readable markdown tables with proper formatting.

    Args:
        data (dict): Elasticsearch query result dictionary containing 'hits' structure
        title (str, optional): Title for the markdown output. Defaults to "Query Results"

    Returns:
        str: Formatted markdown string with table headers, data rows, and summary statistics

    Example:
        >>> es_result = {"hits": {"hits": [{"_source": {"name": "John", "age": 30}}], "total": {"value": 1}}}
        >>> markdown = convert_json_to_markdown(es_result, "User Data")
        >>> print(markdown)
        # User Data

        | age | name |
        | --- | --- |
        | 30 | John |

        **Total Results**: 1 records found
        **Displayed**: 1 records

    Note:
        - Automatically extracts all unique fields from document sources
        - Escapes markdown special characters in data values
        - Provides summary statistics including total and displayed record counts
        - Returns "No results found" message for empty datasets
    """
    if not data or not isinstance(data, dict):
        return f"# {title}\n\nInvalid data format provided."

    if 'hits' not in data:
        return f"# {title}\n\nNo results found - missing 'hits' structure."

    hits = data['hits']['hits']
    if not hits:
        return f"# {title}\n\nNo results found."

    # Extract all unique fields from all documents
    all_fields = set()
    for hit in hits:
        source = hit.get('_source', {})
        all_fields.update(source.keys())

    all_fields = sorted(list(all_fields))

    # Create markdown table
    markdown = f"# {title}\n\n"

    if all_fields:
        # Create table header
        header = "| " + " | ".join(all_fields) + " |"
        separator = "| " + " | ".join(["---"] * len(all_fields)) + " |"

        markdown += header + "\n" + separator + "\n"

        # Add data rows
        for hit in hits:
            source = hit.get('_source', {})
            row_data = []
            for field in all_fields:
                value = source.get(field, "")
                # Convert to string and escape markdown special characters
                str_value = str(value).replace("|", "\\|").replace("\n", " ")
                row_data.append(str_value)

            row = "| " + " | ".join(row_data) + " |"
            markdown += row + "\n"

    # Add summary
    total_hits = data['hits']['total']
    if isinstance(total_hits, dict):
        total_count = total_hits.get('value', 0)
    else:
        total_count = total_hits

    markdown += f"\n**Total Results**: {total_count} records found\n"
    markdown += f"**Displayed**: {len(hits)} records\n"

    return markdown
