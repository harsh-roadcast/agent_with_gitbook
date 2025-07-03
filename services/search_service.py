import logging
import os
import time
from typing import List

from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Global Elasticsearch client
es_client = Elasticsearch(
    [os.getenv('ES_HOST', 'https://62.72.41.235:9200')],
    http_auth=(os.getenv('ES_USERNAME', 'elastic'), os.getenv('ES_PASSWORD', 'GGgCYcnpA_0R_fT5TfFY')),
    verify_certs=os.getenv('ES_VERIFY_CERTS', 'False').lower() == 'true',
    request_timeout=30
)

# Global sentence transformer model
sentence_model = SentenceTransformer('all-MiniLM-L6-v2')

def get_es_client():
    """Returns the global Elasticsearch client instance."""
    return es_client

def get_sentence_transformer_model():
    """Returns the global sentence transformer model instance."""
    return sentence_model

def execute_query(query_body: dict, index: str) -> dict:
    """Execute a standard Elasticsearch query"""
    start_time = time.time()
    logger.info(f"🔍 [TIMING] Starting ES query execution at {start_time}")
    logger.info(f"Executing standard ES query on index '{index}': {query_body}")

    # Remove any size parameters and force to 25

    logger.info(f"Executing query on index: {index} body: {query_body}")

    try:
        query_start = time.time()
        result = es_client.search(index=index, body=query_body, request_timeout=30)
        query_end = time.time()

        total_hits = result.get('hits', {}).get('total', {})
        if isinstance(total_hits, dict):
            total_count = total_hits.get('value', 0)
        else:
            total_count = total_hits

        logger.info(f"⚡ [TIMING] ES query completed in {(query_end - query_start) * 1000:.2f}ms - found {total_count} results on index {index}")

        # Extract only the _source data (actual document data) without ES metadata
        clean_documents = []
        hits = result.get('hits', {}).get('hits', [])

        for hit in hits:
            # Only include the _source data, exclude _id, _index, _score, _type, etc.
            source_data = hit.get('_source', {})
            if source_data:
                clean_documents.append(source_data)

        logger.info(f"📄 Extracted {len(clean_documents)} clean documents without ES metadata")

        end_time = time.time()
        logger.info(f"🏁 [TIMING] Total execute_query function took {(end_time - start_time) * 1000:.2f}ms")

        return {
            "success": True,
            "result": clean_documents,  # Return clean documents instead of full ES response
            "total_count": total_count,
            "query_type": "standard"
        }
    except Exception as e:
        logger.error(f"Error executing query on index {index}: {e}")
        raise

def generate_embedding(text: str) -> List[float]:
    """Generate an embedding vector for the given text."""
    embedding = sentence_model.encode(text).tolist()
    logger.debug(f"Generated embedding of length {len(embedding)} for text: {text[:50]}...")
    return embedding

def execute_vector_query(es_query: dict) -> dict:
    """Execute a simple vector search query."""
    logger.info(f"Executing vector search: {es_query}")

    query_text = es_query.get('query_text', '')
    index = es_query.get('index', 'docling_documents')
    size = max(es_query.get('size', 100), 100)

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

    result = es_client.search(index=index, body=vector_query, request_timeout=30)
    total_hits = result.get('hits', {}).get('total', {}).get('value', 0)
    logger.info(f"Vector search successful - found {total_hits} results")
    return {"success": True, "result": result, "query_type": "vector"}

def convert_json_to_markdown(data, title: str = "Query Results") -> str:
    """Convert JSON query results to markdown formatted table."""
    logger.info("🔄 Starting markdown generation from JSON data")

    if not data:
        return f"# {title}\n\nNo data provided."

    records = []
    total_count = 0

    if isinstance(data, dict) and 'hits' in data:
        hits = data['hits']['hits']
        if not hits:
            return f"# {title}\n\nNo results found."

        for hit in hits:
            source = hit.get('_source', {})
            if source:
                records.append(source)

        total_hits = data['hits']['total']
        if isinstance(total_hits, dict):
            total_count = total_hits.get('value', len(records))
        else:
            total_count = total_hits if total_hits else len(records)
    elif isinstance(data, list):
        records = [record for record in data if isinstance(record, dict)]
        total_count = len(records)
    elif isinstance(data, dict):
        records = [data]
        total_count = 1
    else:
        return f"# {title}\n\nUnsupported data format provided."

    if not records:
        return f"# {title}\n\nNo valid records found."

    all_fields = set()
    for record in records:
        if isinstance(record, dict):
            all_fields.update(record.keys())

    all_fields = sorted(list(all_fields))
    markdown = f"# {title}\n\n"

    if all_fields:
        header = "| " + " | ".join(all_fields) + " |"
        separator = "| " + " | ".join(["---"] * len(all_fields)) + " |"
        markdown += header + "\n" + separator + "\n"

        for record in records:
            row_data = []
            for field in all_fields:
                value = record.get(field, "")
                str_value = str(value).replace("|", "\\|").replace("\n", " ")
                row_data.append(str_value)

            row = "| " + " | ".join(row_data) + " |"
            markdown += row + "\n"

    markdown += f"\n**Total Results**: {total_count} records found\n"
    markdown += f"**Displayed**: {len(records)} records\n"

    logger.info(f"✅ Markdown generation completed: {len(records)} records")
    return markdown
