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
    es = get_es_client()
    try:
        index = es_query.get('index')
        body = es_query.get('body', {})

        if not index:
            return {"error": "Missing 'index' in query.", "vehicles": []}

        # Extract size from body if it exists to avoid parameter conflict
        size = None
        if 'size' in body:
            size = body.pop('size')  # Remove size from body
        elif 'size' in es_query:
            size = es_query.get('size', 10)

        # Execute with a timeout to prevent hanging
        # Pass size as named parameter only if it's not None and not in body
        if size is not None:
            result = es.search(index=index, body=body, size=size, request_timeout=30)
        else:
            result = es.search(index=index, body=body, request_timeout=30)

        # Check if the result actually contains data
        if result.get('hits', {}).get('total', {}).get('value', 0) == 0 and 'aggregations' not in result:
            logger.warning(f"ES query returned no results for index {index}")
            # Return empty results in expected format to prevent retries
            return {"success": True, "result": result, "query_type": "standard", "vehicles": []}

        return {"success": True, "result": result, "query_type": "standard"}
    except Exception as e:
        logger.error(f"ES query execution failed: {e}")
        return {"error": str(e), "query_type": "standard", "vehicles": []}


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
    es = get_es_client()
    try:
        index = es_query.get('index')
        query_text = es_query.get('query_text', '')
        size = es_query.get('size', 10)
        field_name = es_query.get('embedding_field', 'embedding')

        if not index:
            return {"error": "Missing 'index' in query.", "vehicles": []}

        if not query_text:
            return {"error": "Missing 'query_text' for vector search.", "vehicles": []}

        # Generate embedding from the query text
        embedding = generate_embedding(query_text)

        # Build cosine similarity query
        vector_query = {
            "size": size,
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
        if result.get('hits', {}).get('total', {}).get('value', 0) == 0:
            logger.warning(f"Vector search ES query returned no results for index {index}")
            # Return empty results in expected format to prevent retries
            return {"success": True, "result": result, "query_type": "vector", "vehicles": []}

        return {"success": True, "result": result, "query_type": "vector"}
    except Exception as e:
        logger.error(f"Vector search ES query execution failed: {e}")
        return {"error": str(e), "query_type": "vector", "vehicles": []}