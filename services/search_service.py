import logging
import os
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

def execute_query(es_query: dict) -> dict:
    """Execute a standard Elasticsearch query"""
    logger.info(f"Executing standard ES query: {es_query}")

    index = es_query.get('index')
    body = es_query.get('body', {})

    # Remove any size parameters and force to 25
    if 'size' in body:
        body.pop('size')

    max_size = 25
    logger.info(f"Enforcing maximum result limit of {max_size} records")

    result = es_client.search(index=index, body=body, size=max_size, request_timeout=30)
    logger.info(f"ES query successful - found {result.get('hits', {}).get('total', {}).get('value', 0)} results")
    return {"success": True, "result": result, "query_type": "standard"}

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
    size = min(es_query.get('size', 10), 25)

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
