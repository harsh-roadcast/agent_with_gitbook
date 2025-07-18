import logging
import os
import time
from typing import List, Dict, Any

from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

# Import the Pydantic models
from services.models import QueryResult, VectorQueryResult, QueryError
from util.context import get_authorization_header

logger = logging.getLogger(__name__)

# Global Elasticsearch client
es_client = Elasticsearch(
    [os.getenv('ES_HOST')],
    http_auth=(os.getenv('ES_USERNAME'), os.getenv('ES_PASSWORD')),
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

def execute_query(query_body: dict, index: str) -> QueryResult:
    """Execute a standard Elasticsearch query"""
    start_time = time.time()

    # Access context data
    auth_header = get_authorization_header()

    # Log context information
    logger.info(f"🔍 [TIMING] Starting ES query execution at {start_time}")
    logger.info(f"🔑 Auth header present: {auth_header is not None}")
    logger.info(f"Executing standard ES query on index '{index}'")

    try:
        query_start = time.time()
        result = es_client.search(index=index, body=query_body, request_timeout=30, headers={'authorization': auth_header} if auth_header else {})
        query_end = time.time()
        # Check if response contains aggregations
        if 'aggregations' in result:
            # Process aggregation results
            clean_documents = _process_aggregations(result['aggregations'])
            total_count = len(clean_documents)
            logger.info(f"⚡ [TIMING] ES aggregation query completed in {(query_end - query_start) * 1000:.2f}ms - found {total_count} aggregation results on index {index}")
        else:
            # Handle standard query results
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

        # Generate markdown content
        markdown_content = convert_json_to_markdown(clean_documents, f"Results from {index}")

        end_time = time.time()
        logger.info(f"🏁 [TIMING] Total execute_query function took {(end_time - start_time) * 1000:.2f}ms")

        return QueryResult(
            success=True,
            result=clean_documents,
            total_count=total_count,
            query_type="standard",
            markdown_content=markdown_content
        )
    except Exception as e:
        logger.error(f"Error executing query on index {index}: {e}")
        raise QueryError(success=False, error=str(e), error_type="elasticsearch_query")

def _process_aggregations(aggregations: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Process Elasticsearch aggregation results and convert them to a flat structure.

    Args:
        aggregations: The aggregations part of an Elasticsearch response

    Returns:
        List of dictionaries representing the aggregation data in a flat, consumable format
    """
    processed_data = []

    # Recursively process aggregation buckets
    def process_bucket(bucket, parent_key=None, parent_data=None):
        if parent_data is None:
            parent_data = {}

        data = parent_data.copy()

        # Add bucket key/value
        if parent_key and 'key' in bucket:
            if isinstance(bucket['key'], (str, int, float)):
                data[parent_key] = bucket['key']
            elif 'key_as_string' in bucket:
                data[parent_key] = bucket['key_as_string']

        # Add doc_count if present
        if 'doc_count' in bucket:
            data['doc_count'] = bucket['doc_count']

        # Process metric aggregations (sum, avg, etc.)
        for key, value in bucket.items():
            if key not in ('key', 'key_as_string', 'doc_count', 'buckets') and isinstance(value, dict) and 'value' in value:
                data[key] = value['value']

        # Handle top_hits aggregation
        if 'top_hit' in bucket or any(k.startswith('top_hit') for k in bucket.keys()):
            for top_hit_key, top_hit_value in bucket.items():
                if top_hit_key == 'top_hit' or top_hit_key.startswith('top_hit'):
                    hits = top_hit_value.get('hits', {}).get('hits', [])
                    if hits:
                        source = hits[0].get('_source', {})
                        if source:
                            # Use original source fields directly
                            for src_key, src_value in source.items():
                                # Avoid overwriting existing keys
                                if src_key not in data:
                                    data[src_key] = src_value

        # Process nested buckets
        has_nested_buckets = False
        for key, value in bucket.items():
            if isinstance(value, dict) and 'buckets' in value:
                has_nested_buckets = True
                for nested_bucket in value['buckets']:
                    process_bucket(nested_bucket, key, data)

        # If this is a terminal bucket (no nested buckets), add data to result
        if not has_nested_buckets and data:
            # Make sure we don't duplicate entries
            if data not in processed_data:
                processed_data.append(data)

        # Handle edge case: if we have useful data but also nested buckets,
        # we might want to include this level as well
        elif has_nested_buckets and len(data) > 2 and any(k not in ['doc_count', parent_key] for k in data.keys()):
            if data not in processed_data:
                processed_data.append(data)

    # Process each top-level aggregation
    for agg_name, agg_value in aggregations.items():
        if 'buckets' in agg_value:
            for bucket in agg_value['buckets']:
                process_bucket(bucket, agg_name)
        elif 'value' in agg_value:
            # Simple metric aggregation
            processed_data.append({agg_name: agg_value['value']})

    logger.info(f"Processed {len(processed_data)} records from aggregation results")
    return processed_data

def generate_embedding(text: str) -> List[float]:
    """Generate an embedding vector for the given text."""
    embedding = sentence_model.encode(text).tolist()
    logger.debug(f"Generated embedding of length {len(embedding)} for text: {text[:50]}...")
    return embedding

def execute_vector_query(es_query: dict) -> VectorQueryResult:
    """Execute a simple vector search query."""
    logger.info(f"Executing vector search: {es_query}")
    auth_header = get_authorization_header()
    query_text = es_query.get('query_text', '')
    index = es_query.get('index', 'docling_documents')
    size = max(es_query.get('size', 100), 100)

    try:
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

        result = es_client.search(index=index, body=vector_query, request_timeout=30, headers={'authorization': auth_header} if auth_header else {})

        # Convert Elasticsearch response to a dictionary if it's not already one
        if hasattr(result, 'body') and callable(getattr(result, 'body', None)):
            # For Elasticsearch client versions that return a Response object
            result_dict = result.body
        elif hasattr(result, 'to_dict') and callable(getattr(result, 'to_dict', None)):
            # For Elasticsearch client versions that have to_dict method
            result_dict = result.to_dict()
        else:
            # Try to convert to dict directly or as fallback use the raw response
            try:
                result_dict = dict(result)
            except (TypeError, ValueError):
                # If all conversions fail, use the object as is and let the model handle it
                result_dict = {"raw_response": str(result)}

        total_hits = result_dict.get('hits', {}).get('total', {}).get('value', 0)
        logger.info(f"Vector search successful - found {total_hits} results")

        # Extract clean documents for markdown generation
        clean_documents = []
        hits = result_dict.get('hits', {}).get('hits', [])
        for hit in hits:
            source_data = hit.get('_source', {})
            if source_data:
                clean_documents.append(source_data)

        # Generate markdown content
        markdown_content = convert_json_to_markdown(clean_documents, f"Vector Search Results for '{query_text[:30]}...'")

        return VectorQueryResult(
            success=True,
            result=result_dict,  # Now passing a dictionary instead of the response object
            query_type="vector",
            markdown_content=markdown_content
        )
    except Exception as e:
        logger.error(f"Error executing vector query: {e}")
        # Create and raise a proper QueryError
        error = QueryError(success=False, error=str(e), error_type="vector_query")
        raise error from e  # Properly chain the exception

def convert_json_to_markdown(data, title: str = "Query Results") -> str:
    """Convert JSON query results to markdown formatted table."""
    logger.info("🔄 Starting markdown generation from JSON data")

    if not data:
        return f"# {title}\n\nNo data provided."

    records = []
    total_count = 0

    # Handle standard ES response with hits
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

    # Handle aggregation results (already processed into list of dictionaries)
    elif isinstance(data, list):
        records = [record for record in data if isinstance(record, dict)]
        total_count = len(records)

        # Special handling for aggregation results with nested structure
        if records and any(isinstance(v, dict) for record in records for v in record.values()):
            return _format_complex_aggregations(records, title)

    # Handle single dictionary result
    elif isinstance(data, dict):
        records = [data]
        total_count = 1
    else:
        return f"# {title}\n\nUnsupported data format provided."

    if not records:
        return f"# {title}\n\nNo valid records found."

    # Extract all fields from records
    all_fields = set()
    for record in records:
        if isinstance(record, dict):
            all_fields.update(record.keys())

    # Sort fields alphabetically for consistent display
    all_fields = sorted(list(all_fields))

    # Start building markdown table
    markdown = f"# {title}\n\n"

    if all_fields:
        # Create table header and separator
        header = "| " + " | ".join(all_fields) + " |"
        separator = "| " + " | ".join(["---"] * len(all_fields)) + " |"
        markdown += header + "\n" + separator + "\n"

        # Add rows
        for record in records:
            row_data = []
            for field in all_fields:
                value = record.get(field, "")
                # Format numbers for better readability
                if isinstance(value, (int, float)):
                    if isinstance(value, float):
                        str_value = f"{value:,.2f}"
                    else:
                        str_value = f"{value:,}"
                else:
                    str_value = str(value)
                # Escape pipes and newlines for markdown
                str_value = str_value.replace("|", "\\|").replace("\n", " ")
                row_data.append(str_value)

            row = "| " + " | ".join(row_data) + " |"
            markdown += row + "\n"

    # Add summary information
    markdown += f"\n**Total Results**: {total_count:,} records found\n"
    markdown += f"**Displayed**: {len(records):,} records\n"

    logger.info(f"✅ Markdown generation completed: {len(records)} records")
    return markdown

def _format_complex_aggregations(data: List[Dict[str, Any]], title: str) -> str:
    """
    Format complex aggregation results that may have nested structures.
    Creates a more organized markdown output with sections for different aggregation levels.

    Args:
        data: List of dictionaries containing aggregation results
        title: Title for the markdown output

    Returns:
        Formatted markdown string
    """
    # Start with title
    markdown = f"# {title}\n\n"

    # Group data by first-level aggregation key if possible
    first_level_keys = set()
    for item in data:
        for key in item.keys():
            if key not in ('doc_count', 'key'):
                first_level_keys.add(key)
                break

    # If we have clear grouping fields
    if first_level_keys and len(first_level_keys) == 1:
        group_key = list(first_level_keys)[0]
        groups = {}

        # Group by the first level key
        for item in data:
            group_value = item.get(group_key)
            if group_value is not None:
                if group_value not in groups:
                    groups[group_value] = []
                groups[group_value].append(item)

        # Create section for each group
        for group_value, group_data in groups.items():
            markdown += f"## {group_key}: {group_value}\n\n"

            # Get fields for this group
            all_fields = set()
            for record in group_data:
                all_fields.update(record.keys())

            # Remove the group key since it's redundant in the table
            if group_key in all_fields:
                all_fields.remove(group_key)

            # Sort remaining fields for consistent display
            all_fields = sorted(list(all_fields))

            # Create table header and separator
            header = "| " + " | ".join(all_fields) + " |"
            separator = "| " + " | ".join(["---"] * len(all_fields)) + " |"
            markdown += header + "\n" + separator + "\n"

            # Add rows
            for record in group_data:
                row_data = []
                for field in all_fields:
                    value = record.get(field, "")
                    # Format numbers for better readability
                    if isinstance(value, (int, float)):
                        if isinstance(value, float):
                            str_value = f"{value:,.2f}"
                        else:
                            str_value = f"{value:,}"
                    else:
                        str_value = str(value)
                    # Escape pipes and newlines for markdown
                    str_value = str_value.replace("|", "\\|").replace("\n", " ")
                    row_data.append(str_value)

                row = "| " + " | ".join(row_data) + " |"
                markdown += row + "\n"

            markdown += "\n"
    else:
        # Fall back to standard table for all records
        all_fields = set()
        for record in data:
            all_fields.update(record.keys())

        all_fields = sorted(list(all_fields))

        # Create table header and separator
        header = "| " + " | ".join(all_fields) + " |"
        separator = "| " + " | ".join(["---"] * len(all_fields)) + " |"
        markdown += header + "\n" + separator + "\n"

        # Add rows
        for record in data:
            row_data = []
            for field in all_fields:
                value = record.get(field, "")
                # Format numbers for better readability
                if isinstance(value, (int, float)):
                    if isinstance(value, float):
                        str_value = f"{value:,.2f}"
                    else:
                        str_value = f"{value:,}"
                else:
                    str_value = str(value)
                # Escape pipes and newlines for markdown
                str_value = str_value.replace("|", "\\|").replace("\n", " ")
                row_data.append(str_value)

            row = "| " + " | ".join(row_data) + " |"
            markdown += row + "\n"

    # Add summary information
    markdown += f"\n**Total Aggregation Groups**: {len(data):,}\n"

    return markdown

def convert_vector_results_to_markdown(results: List[Dict[str, Any]], title: str = "Vector Search Results") -> str:
    """
    Convert vector search results to a markdown representation.

    Args:
        results: List of dictionaries containing the search results
        title: Title for the markdown output

    Returns:
        Formatted markdown string representation of the results
    """
    if not results:
        return "No vector search results found."

    markdown_content = f"### {title}\n\n"
    for i, item in enumerate(results):
        markdown_content += f"**Result {i+1}**\n"
        for key, value in item.items():
            markdown_content += f"- **{key}**: {value}\n"
        markdown_content += "\n"

    return markdown_content

