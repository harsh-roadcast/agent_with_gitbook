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
ES_HOST = os.getenv('ES_HOST', None)
ES_USERNAME = os.getenv('ES_USERNAME', None)
ES_PASSWORD = os.getenv('ES_PASSWORD', None)
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
    Execute a simple vector search query using Elasticsearch's cosine similarity.

    Args:
        es_query: A dict with 'query_text' and optional 'index', 'size' keys

    Returns:
        Dictionary with the query results
    """
    logger.info(f"Executing vector search: {es_query}")

    # Basic validation
    if not es_query or not isinstance(es_query, dict):
        return {"error": "Invalid vector search query", "query_type": "vector"}

    # Extract parameters
    query_text = es_query.get('query_text', '')
    index = es_query.get('index', 'docling_documents')
    size = min(es_query.get('size', 10), 25)  # Max 25 results

    if not query_text:
        return {"error": "Missing query_text", "query_type": "vector"}

    es = get_es_client()

    try:
        # Check if index exists
        if not es.indices.exists(index=index):
            return {"error": f"Index '{index}' does not exist", "query_type": "vector"}

        # Generate embedding
        embedding = generate_embedding(query_text)
        logger.info(f"Generated embedding for: '{query_text[:50]}...'")

        # Simple vector search query
        vector_query = {
            "size": size,
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                        "params": {"query_vector": embedding}
                    }
                }
            },
            "_source": ["filename", "text", "chunk_id"]
        }

        # Execute search
        result = es.search(index=index, body=vector_query, request_timeout=30)

        # Check for results
        total_hits = result.get('hits', {}).get('total', {}).get('value', 0)
        if total_hits == 0:
            return {"error": "No results found", "query_type": "vector"}

        logger.info(f"Vector search successful - found {total_hits} results")
        return {"success": True, "result": result, "query_type": "vector"}

    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return {"error": str(e), "query_type": "vector"}


def convert_json_to_markdown(data, title: str = "Query Results") -> str:
    """
    Convert JSON query results to markdown formatted table.

    Handles both Elasticsearch format and processed data formats.

    Args:
        data: Query result data - can be dict with 'hits' structure, list of dicts, or single dict
        title (str, optional): Title for the markdown output. Defaults to "Query Results"

    Returns:
        str: Formatted markdown string with table headers, data rows, and summary statistics
    """
    logger.info("🔄 Starting markdown generation from JSON data")

    if not data:
        logger.warning("⚠️ Markdown generation: No data provided")
        return f"# {title}\n\nNo data provided."

    # Handle different data formats
    records = []
    total_count = 0

    # Check if it's Elasticsearch format with 'hits' structure
    if isinstance(data, dict) and 'hits' in data:
        hits = data['hits']['hits']
        if not hits:
            logger.info("⚠️ Markdown generation completed: No results found")
            return f"# {title}\n\nNo results found."

        # Extract records from Elasticsearch format
        for hit in hits:
            source = hit.get('_source', {})
            if source:
                records.append(source)

        # Get total count
        total_hits = data['hits']['total']
        if isinstance(total_hits, dict):
            total_count = total_hits.get('value', len(records))
        else:
            total_count = total_hits if total_hits else len(records)

    # Handle list of dictionaries (processed data)
    elif isinstance(data, list):
        records = [record for record in data if isinstance(record, dict)]
        total_count = len(records)

    # Handle single dictionary
    elif isinstance(data, dict):
        records = [data]
        total_count = 1

    else:
        logger.warning("❌ Markdown generation failed: Unsupported data format")
        return f"# {title}\n\nUnsupported data format provided."

    if not records:
        logger.info("⚠️ Markdown generation completed: No valid records found")
        return f"# {title}\n\nNo valid records found."

    # Extract all unique fields from all records
    all_fields = set()
    for record in records:
        if isinstance(record, dict):
            all_fields.update(record.keys())

    all_fields = sorted(list(all_fields))

    # Create markdown table
    markdown = f"# {title}\n\n"

    if all_fields:
        # Create table header
        header = "| " + " | ".join(all_fields) + " |"
        separator = "| " + " | ".join(["---"] * len(all_fields)) + " |"

        markdown += header + "\n" + separator + "\n"

        # Add data rows
        for record in records:
            row_data = []
            for field in all_fields:
                value = record.get(field, "")
                # Convert to string and escape markdown special characters
                str_value = str(value).replace("|", "\\|").replace("\n", " ")
                row_data.append(str_value)

            row = "| " + " | ".join(row_data) + " |"
            markdown += row + "\n"

    # Add summary
    markdown += f"\n**Total Results**: {total_count} records found\n"
    markdown += f"**Displayed**: {len(records)} records\n"

    logger.info(f"✅ Markdown generation completed successfully: {len(records)} records displayed from {total_count} total records")

    return markdown
