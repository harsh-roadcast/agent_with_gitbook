import json
import logging
import os
import time
from typing import List, Dict, Any

from dotenv import load_dotenv
from elasticsearch import Elasticsearch

from langchain_openai import OpenAIEmbeddings
from core.config import config_manager

# Import the Pydantic models
from services.models import QueryResult, VectorQueryResult, QueryError, QueryErrorException
from util.context import get_authorization_header

load_dotenv()

logger = logging.getLogger(__name__)

es_config = config_manager.config.elasticsearch

es_client = Elasticsearch(
    [es_config.host] if isinstance(es_config.host, str) else es_config.host,
    http_auth=(es_config.username, es_config.password) if es_config.username and es_config.password else None,
    verify_certs=es_config.verify_certs,
    request_timeout=es_config.request_timeout
)

# Global OpenAI embeddings model
sentence_model = OpenAIEmbeddings(
    model=config_manager.config.models.embedding_model,
    api_key=config_manager.config.models.openai_api_key
)

def get_es_client():
    """Returns the global Elasticsearch client instance."""
    return es_client

def get_sentence_transformer_model():
    """Returns the global sentence transformer model instance."""
    return sentence_model

def execute_query(query_body: dict, index: str) -> QueryResult:
    """Execute a standard Elasticsearch query"""
    start_time = time.time()
    auth_header = get_authorization_header()

    # Log context information
    logger.info(f"🔍 [TIMING] Starting ES query execution at {start_time}")
    logger.info(f"🔑 Auth header present: {auth_header is not None}")
    logger.info(f"Executing standard ES query on index '{index}'")

    try:
        result = _perform_es_search(query_body, index, auth_header)
        clean_documents, total_count = _extract_documents_from_result(result, index)
        markdown_content = convert_json_to_markdown(clean_documents, f"Results from {index}")
        
        _log_query_completion(start_time)

        return QueryResult(
            success=True,
            result=clean_documents,
            total_count=total_count,
            query_type="standard",
            markdown_content=markdown_content
        )
    except Exception as e:
        logger.error(f"Error executing query on index {index}: {e}")
        raise e


def _log_query_start(start_time: float, auth_header: str, index: str) -> None:
    """Log query initialization details."""
    logger.info(f"🔍 [TIMING] Starting ES query execution at {start_time}")
    logger.info(f"🔑 Auth header present: {auth_header is not None}")
    logger.info(f"Executing standard ES query on index '{index}'")


def _log_query_completion(start_time: float) -> None:
    """Log query completion timing."""
    end_time = time.time()
    logger.info(f"🏁 [TIMING] Total execute_query function took {(end_time - start_time) * 1000:.2f}ms")


def _perform_es_search(query_body: dict, index: str, auth_header: str) -> dict:
    """Execute Elasticsearch search and return result."""
    query_start = time.time()
    result = es_client.search(
        index=index, 
        body=query_body, 
        request_timeout=30, 
        headers={'authorization': auth_header} if auth_header else {}
    )
    query_end = time.time()
    
    logger.info(
        f"⚡ [TIMING] ES query completed in {(query_end - query_start) * 1000:.2f}ms"
    )
    
    return result


def _extract_documents_from_result(result: dict, index: str) -> tuple:
    """Extract clean documents and count from ES result."""
    if 'aggregations' in result:
        return _extract_aggregation_results(result, index)
    else:
        return _extract_standard_results(result, index)


def _extract_aggregation_results(result: dict, index: str) -> tuple:
    """Extract results from aggregation response."""
    clean_documents = _process_aggregations(result['aggregations'])
    total_count = len(clean_documents)
    logger.info(
        f"⚡ [TIMING] Found {total_count} aggregation results on index {index}"
    )
    return clean_documents, total_count


def _extract_standard_results(result: dict, index: str) -> tuple:
    """Extract results from standard query response."""
    total_count = _get_total_hits_count(result)
    logger.info(f"Found {total_count} results on index {index}")
    
    clean_documents = _extract_source_documents(result.get('hits', {}).get('hits', []))
    logger.info(f"📄 Extracted {len(clean_documents)} clean documents without ES metadata")
    
    return clean_documents, total_count


def _get_total_hits_count(result: dict) -> int:
    """Get total hits count from ES result."""
    total_hits = result.get('hits', {}).get('total', {})
    if isinstance(total_hits, dict):
        return total_hits.get('value', 0)
    return total_hits if total_hits else 0


def _extract_source_documents(hits: List[dict]) -> List[dict]:
    """Extract _source data from ES hits."""
    clean_documents = []
    for hit in hits:
        source_data = hit.get('_source', {})
        if source_data:
            clean_documents.append(source_data)
    return clean_documents

def _process_aggregations(aggregations: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Process Elasticsearch aggregation results and convert them to a flat structure.
    Handles nested buckets and various aggregation types to create a tabular representation.

    Args:
        aggregations: The aggregations part of an Elasticsearch response

    Returns:
        List of dictionaries representing the aggregation data in a flat, consumable format
    """
    processed_data = []
    logger.debug(f"Processing aggregations: {json.dumps(aggregations)}")

    # Helper function to process any bucket type recursively
    def process_bucket(bucket, parent_key, parent_metadata=None, depth=0):
        indent = "  " * depth
        logger.info(f"{indent}[DEBUG] Processing bucket for key: '{parent_key}' at depth {depth}")

        if parent_metadata is None:
            parent_metadata = {}
            logger.debug(f"{indent}No parent metadata provided, initializing empty dict")
        else:
            logger.debug(f"{indent}Parent metadata: {json.dumps(parent_metadata)}")

        record = parent_metadata.copy()

        # Always prefer key_as_string (for dates and formatted values) over raw key
        if 'key_as_string' in bucket:
            record[f"{parent_key}"] = bucket['key_as_string']
            logger.debug(f"{indent}Using key_as_string: '{bucket['key_as_string']}' for field '{parent_key}'")
        elif 'key' in bucket:
            record[f"{parent_key}"] = bucket['key']
            logger.debug(f"{indent}Using key: '{bucket['key']}' for field '{parent_key}'")

        # Add doc_count if present
        if 'doc_count' in bucket:
            record[f"{parent_key}_count"] = bucket['doc_count']
            logger.debug(f"{indent}Added doc_count: {bucket['doc_count']} as '{parent_key}_count'")

        # Process metrics and nested buckets
        for field, value in bucket.items():
            if field not in ('key', 'key_as_string', 'doc_count'):
                logger.debug(f"{indent}Processing field: '{field}' of type: {type(value).__name__}")

                # Handle metric aggregations (avg, sum, etc.)
                if isinstance(value, dict) and 'value' in value:
                    record[field] = value['value']
                    logger.debug(f"{indent}Added metric value: {value['value']} for field '{field}'")

                # Handle special max_bucket type aggs
                elif isinstance(value, dict) and 'keys' in value and 'value' in value:
                    record[f"{field}_value"] = value['value']
                    keys_str = ", ".join(value['keys']) if isinstance(value['keys'], list) else value['keys']
                    record[f"{field}_key"] = keys_str
                    logger.debug(f"{indent}Added max_bucket: value={value['value']}, keys={keys_str} for field '{field}'")

                # Handle nested buckets
                elif isinstance(value, dict) and 'buckets' in value:
                    logger.debug(f"{indent}Found nested buckets in field '{field}' with {len(value['buckets'])} buckets")

                    # If it's a multi-bucket nested aggregation
                    if len(value['buckets']) > 1:
                        logger.debug(f"{indent}Processing multi-bucket nested aggregation for field '{field}'")
                        nested_records = []
                        for i, nested_bucket in enumerate(value['buckets']):
                            logger.debug(f"{indent}Processing nested bucket {i+1}/{len(value['buckets'])} for field '{field}'")
                            # Create a new record for each nested bucket
                            nested_record = process_bucket(nested_bucket, field, record.copy(), depth+1)
                            if nested_record:
                                nested_records.append(nested_record)

                        logger.debug(f"{indent}Processed {len(nested_records)} nested records for field '{field}'")
                        if nested_records:
                            return nested_records

                    # If it's a single-bucket nested aggregation (like a filter)
                    elif len(value['buckets']) == 1:
                        logger.debug(f"{indent}Processing single-bucket nested aggregation for field '{field}'")
                        nested_bucket = value['buckets'][0]
                        # Process any fields from the nested bucket
                        for nested_field, nested_value in nested_bucket.items():
                            if nested_field not in ('key', 'key_as_string', 'doc_count'):
                                if isinstance(nested_value, dict) and 'value' in nested_value:
                                    record[f"{field}_{nested_field}"] = nested_value['value']
                                    logger.debug(f"{indent}Added nested metric: {nested_value['value']} for field '{field}_{nested_field}'")
                                elif nested_field == 'key' and 'key_as_string' not in nested_bucket:
                                    record[field] = nested_value
                                    logger.debug(f"{indent}Added nested key: {nested_value} for field '{field}'")

                    # Empty buckets
                    else:
                        logger.debug(f"{indent}Empty buckets for field '{field}', setting to None")
                        record[field] = None

        logger.debug(f"{indent}Completed processing bucket for key '{parent_key}', record: {json.dumps(record)}")
        return record

    # Process top-level aggregations
    for agg_name, agg_data in aggregations.items():
        logger.info(f"Processing top-level aggregation: '{agg_name}'")

        # Handle bucket aggregations
        if 'buckets' in agg_data:
            logger.debug(f"Found {len(agg_data['buckets'])} buckets in '{agg_name}'")

            for i, bucket in enumerate(agg_data['buckets']):
                logger.debug(f"Processing bucket {i+1}/{len(agg_data['buckets'])} for '{agg_name}'")
                result = process_bucket(bucket, agg_name)

                # Handle the case where we get a list of records back (nested buckets)
                if isinstance(result, list):
                    logger.debug(f"Adding {len(result)} nested records from '{agg_name}' to processed data")
                    processed_data.extend(result)
                else:
                    logger.debug(f"Adding single record from '{agg_name}' to processed data")
                    processed_data.append(result)

        # Handle simple metric aggregations at top level
        elif 'value' in agg_data:
            logger.debug(f"Found simple metric aggregation '{agg_name}' with value {agg_data['value']}")
            processed_data.append({agg_name: agg_data['value']})

    logger.info(f"Processed {len(processed_data)} total records from aggregation results")
    return processed_data

def generate_embedding(text: str) -> List[float]:
    """Generate an embedding vector for the given text."""
    embedding = sentence_model.embed_query(text).tolist()
    logger.debug(f"Generated embedding of length {len(embedding)} for text: {text[:50]}...")
    return embedding



def execute_vector_query(es_query: dict) -> VectorQueryResult:
    """Execute a vector similarity search query with optional keyword enhancement."""
    start_time = time.time()
    query_params = _extract_query_params(es_query)
    
    _log_query_start(start_time, query_params['auth_header'], query_params['index'])
    
    embedding = generate_embedding(query_params['query_text'])
    logger.info(f"Generated embedding for: '{query_params['query_text'][:50]}...'")
    
    try:
        vector_query = _build_vector_query(
            embedding, 
            query_params['keywords'], 
            query_params['source_fields'], 
            query_params['size']
        )
        
        result = _execute_vector_search(
            vector_query, 
            query_params['index'], 
            query_params['auth_header']
        )
        
        clean_documents = _extract_vector_results(result)
        
        _log_query_completion(start_time)
        
        return VectorQueryResult(
            success=True,
            result=clean_documents,
            query_type="vector",
        )
    except Exception as e:
        logger.error(f"Error executing vector query: {e}")
        error = QueryError(success=False, error=str(e), error_type="vector_query")
        raise QueryErrorException(error) from e


def _generate_base_query(keywords: List[str]) -> dict:
    """
    Generate base query with keyword enhancement, fuzzy matching, and typo tolerance.
    
    Supports:
    - Fuzzy matching for typos (up to 2 character edits)
    - Phrase matching for exact terms
    - Multi-field searching
    """
    if keywords and isinstance(keywords, list) and len(keywords) > 0:
        logger.info(f"Applying keyword filter with {len(keywords)} keywords: {keywords}")
        
        keyword_query = " ".join(keywords)
        
        return {
            "bool": {
                "should": [
                    # Exact phrase matching (highest priority)
                    {
                        "multi_match": {
                            "query": keyword_query,
                            "fields": ["text^2.0", "filename^1.5", "title^2.5"],
                            "type": "phrase",
                            "boost": 0.5
                        }
                    },
                    # Fuzzy matching for typo tolerance
                    {
                        "multi_match": {
                            "query": keyword_query,
                            "fields": ["text^1.5", "filename^1.2", "title^2.0"],
                            "fuzziness": "AUTO",  # AUTO: 1 edit for 3-5 chars, 2 edits for >5 chars
                            "prefix_length": 2,   # First 2 chars must match exactly
                            "max_expansions": 50, # Limit fuzzy term expansions
                            "boost": 0.3
                        }
                    },
                    # Standard matching (fallback)
                    {
                        "multi_match": {
                            "query": keyword_query,
                            "fields": ["text", "filename", "title^1.5"],
                            "type": "best_fields",
                            "operator": "or",
                            "boost": 0.2
                        }
                    }
                ],
                "minimum_should_match": 0
            }
        }
    else:
        return {"match_all": {}}


def _extract_query_params(es_query: dict) -> dict:
    """Extract and validate query parameters."""
    return {
        'auth_header': get_authorization_header(),
        'query_text': es_query.get('query_text', ''),
        'index': es_query.get('index', 'docling_documents'),
        'size': min(es_query.get('size', 10), 10),
        'keywords': es_query.get('keywords', []),
        'source_fields': es_query.get('_source', ["filename", "text", "chunk_id"])
    }


def _build_vector_query(
    embedding: List[float], 
    keywords: List[str], 
    source_fields: List[str], 
    size: int
) -> dict:
    """Build Elasticsearch vector query with optional keyword enhancement."""
    base_query = _generate_base_query(keywords)
    
    return {
        "size": size,
        "query": {
            "script_score": {
                "query": base_query,
                "script": {
                    "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                    "params": {"query_vector": embedding}
                }
            }
        },
        "_source": source_fields
    }


def _execute_vector_search(vector_query: dict, index: str, auth_header: str) -> dict:
    """Execute vector search against Elasticsearch."""
    result = es_client.search(
        index=index, 
        body=vector_query, 
        request_timeout=30, 
        headers={'authorization': auth_header} if auth_header else {}
    )
    return _to_dict(result)


def _extract_vector_results(result_dict: dict) -> List[dict]:
    """Extract clean documents from vector search results."""
    total_hits = result_dict.get('hits', {}).get('total', {}).get('value', 0)
    logger.info(f"Vector search successful - found {total_hits} results")
    
    return _extract_source_documents(result_dict.get('hits', {}).get('hits', []))


def _to_dict(es_result) -> dict:
    """Convert Elasticsearch result object to dictionary."""
    if hasattr(es_result, 'body'):
        return es_result.body
    elif isinstance(es_result, dict):
        return es_result
    else:
        return dict(es_result)


def convert_json_to_markdown(data, title="Query Results") -> str:
    """Convert JSON query results to formatted markdown."""
    records, total_count = _parse_data_records(data)
    
    if not records:
        logger.warning("No valid records found after processing")
        return f"# {title}\n\nNo valid records found."

    # Check for complex nested structures in aggregations
    if _has_complex_nested_structure(records):
        logger.info("Detected complex nested structure, using special formatter")
        return _format_complex_aggregations(records, title)

    return _format_standard_table(records, total_count, title)


def _parse_data_records(data) -> tuple:
    """Parse data into records and total count."""
    if isinstance(data, dict) and 'hits' in data:
        return _parse_es_hits(data)
    elif isinstance(data, list):
        return _parse_list_data(data)
    elif isinstance(data, dict):
        return [data], 1
    else:
        logger.warning(f"Unsupported data format: {type(data).__name__}")
        return [], 0


def _parse_es_hits(data: dict) -> tuple:
    """Parse Elasticsearch hits response."""
    logger.info("Processing standard Elasticsearch response with hits")
    hits = data['hits']['hits']
    
    if not hits:
        logger.warning("No hits found in Elasticsearch response")
        return [], 0

    records = [hit.get('_source', {}) for hit in hits if hit.get('_source')]
    total_count = _get_total_hits_count(data)
    
    logger.info(f"Processed {len(records)} hits from {total_count} total hits")
    return records, total_count


def _parse_list_data(data: list) -> tuple:
    """Parse list data into records."""
    logger.info(f"Processing list data with {len(data)} items")
    records = [record for record in data if isinstance(record, dict)]
    logger.info(f"Filtered to {len(records)} dictionary records")
    return records, len(records)


def _has_complex_nested_structure(records: List[dict]) -> bool:
    """Check if records have complex nested dictionary structures."""
    if not records:
        return False
    
    return any(
        isinstance(v, dict) 
        for record in records 
        for v in record.values()
    )


def _format_standard_table(records: List[dict], total_count: int, title: str) -> str:
    """Format records as a standard markdown table."""
    all_fields = _extract_all_fields(records)
    logger.info(f"Extracted {len(all_fields)} unique fields from records")
    
    markdown = f"# {title}\n\n"
    
    if all_fields:
        markdown += _create_table_header(all_fields)
        markdown += _create_table_rows(records, all_fields)
    
    markdown += _create_summary_section(total_count, len(records))
    
    logger.info(f"✅ Markdown generation completed: {len(records)} records")
    return markdown


def _extract_all_fields(records: List[dict]) -> List[str]:
    """Extract and sort all unique fields from records."""
    all_fields = set()
    for record in records:
        if isinstance(record, dict):
            all_fields.update(record.keys())
    return sorted(list(all_fields))


def _create_table_header(fields: List[str]) -> str:
    """Create markdown table header and separator."""
    header = "| " + " | ".join(fields) + " |"
    separator = "| " + " | ".join(["---"] * len(fields)) + " |"
    return header + "\n" + separator + "\n"


def _create_table_rows(records: List[dict], fields: List[str]) -> str:
    """Create markdown table rows from records."""
    rows = []
    for record in records:
        row_data = [_format_field_value(record.get(field, "")) for field in fields]
        rows.append("| " + " | ".join(row_data) + " |")
    return "\n".join(rows) + "\n"


def _format_field_value(value: Any) -> str:
    """Format a field value for markdown table."""
    # Format numbers for better readability
    if isinstance(value, float):
        str_value = f"{value:,.2f}"
    elif isinstance(value, int):
        str_value = f"{value:,}"
    else:
        str_value = str(value)
    
    # Escape markdown special characters
    return str_value.replace("|", "\\|").replace("\n", " ")


def _create_summary_section(total_count: int, displayed_count: int) -> str:
    """Create summary section for markdown output."""
    return (
        f"\n**Total Results**: {total_count:,} records found\n"
        f"**Displayed**: {displayed_count:,} records\n"
    )


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
    logger.info(f"Formatting complex aggregations with {len(data)} records and title '{title}'")

    # Start with title
    markdown = f"# {title}\n\n"

    # Group data by first-level aggregation key if possible
    first_level_keys = set()
    for item in data:
        for key in item.keys():
            if key not in ('doc_count', 'key'):
                first_level_keys.add(key)
                break

    logger.debug(f"Identified potential grouping keys: {first_level_keys}")

    # If we have clear grouping fields
    if first_level_keys and len(first_level_keys) == 1:
        group_key = list(first_level_keys)[0]
        logger.info(f"Using '{group_key}' as the grouping field")

        groups = {}

        # Group by the first level key
        for item in data:
            group_value = item.get(group_key)
            if group_value is not None:
                if group_value not in groups:
                    groups[group_value] = []
                groups[group_value].append(item)

        logger.info(f"Created {len(groups)} distinct groups based on '{group_key}'")

        # Create section for each group
        for group_idx, (group_value, group_data) in enumerate(groups.items()):
            logger.debug(f"Processing group {group_idx+1}/{len(groups)}: {group_key}={group_value} with {len(group_data)} records")

            markdown += f"## {group_key}: {group_value}\n\n"

            # Get fields for this group
            all_fields = set()
            for record in group_data:
                all_fields.update(record.keys())

            # Remove the group key since it's redundant in the table
            if group_key in all_fields:
                all_fields.remove(group_key)
                logger.debug(f"Removed grouping key '{group_key}' from fields")

            # Sort remaining fields for consistent display
            all_fields = sorted(list(all_fields))
            logger.debug(f"Group table will have {len(all_fields)} columns: {all_fields}")

            # Create table header and separator
            header = "| " + " | ".join(all_fields) + " |"
            separator = "| " + " | ".join(["---"] * len(all_fields)) + " |"
            markdown += header + "\n" + separator + "\n"

            # Add rows
            for i, record in enumerate(group_data):
                logger.debug(f"Processing record {i+1}/{len(group_data)} in group {group_value}")

                row_data = []
                for field in all_fields:
                    value = record.get(field, "")

                    # Log any potential problematic values
                    if isinstance(value, (list, dict)):
                        logger.warning(f"Complex value type {type(value).__name__} for field '{field}' in record {i+1} of group {group_value}")

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
        logger.info(f"No clear grouping field found, using flat table format with {len(data)} records")

        # Fall back to standard table for all records
        all_fields = set()
        for record in data:
            all_fields.update(record.keys())

        all_fields = sorted(list(all_fields))
        logger.debug(f"Flat table will have {len(all_fields)} columns")

        # Create table header and separator
        header = "| " + " | ".join(all_fields) + " |"
        separator = "| " + " | ".join(["---"] * len(all_fields)) + " |"
        markdown += header + "\n" + separator + "\n"

        # Add rows
        for i, record in enumerate(data):
            logger.debug(f"Processing record {i+1}/{len(data)}")

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

                # Check for potentially problematic markdown characters
                if '|' in str_value or '\n' in str_value:
                    logger.debug(f"Field '{field}' contains special characters that need escaping")

                # Escape pipes and newlines for markdown
                str_value = str_value.replace("|", "\\|").replace("\n", " ")
                row_data.append(str_value)

            row = "| " + " | ".join(row_data) + " |"
            markdown += row + "\n"

    # Add summary information
    markdown += f"\n**Total Aggregation Groups**: {len(data):,}\n"

    logger.info(f"Complex aggregation formatting completed with {len(markdown)} characters")
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
