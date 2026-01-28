import json
import logging
import os
import time
from typing import List, Dict, Any

from dotenv import load_dotenv

from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

# Import the Pydantic models
from services.models import QueryResult, VectorQueryResult, QueryError, QueryErrorException
from util.context import get_authorization_header

load_dotenv()

logger = logging.getLogger(__name__)

ES_HOST = os.getenv('ES_HOST') or 'http://127.0.0.1:9200'
ES_USERNAME = os.getenv('ES_USERNAME')
ES_PASSWORD = os.getenv('ES_PASSWORD')
ES_VERIFY_CERTS = os.getenv('ES_VERIFY_CERTS', 'False').lower() == 'true'

es_client = Elasticsearch(
    [ES_HOST] if isinstance(ES_HOST, str) else ES_HOST,
    http_auth=(ES_USERNAME, ES_PASSWORD) if ES_USERNAME and ES_PASSWORD else None,
    verify_certs=ES_VERIFY_CERTS,
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
        raise e

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
    embedding = sentence_model.encode(text).tolist()
    logger.debug(f"Generated embedding of length {len(embedding)} for text: {text[:50]}...")
    return embedding

def execute_vector_query(es_query: dict) -> VectorQueryResult:
    """Execute a simple vector search query."""
    logger.info(f"Executing vector search: {es_query}")
    auth_header = get_authorization_header()
    query_text = es_query.get('query_text', '')
    index = es_query.get('index', 'docling_documents')
    size = min(es_query.get('size', 10), 10)

    try:
        # Generate embedding
        embedding = generate_embedding(query_text)
        logger.info(f"Generated embedding for: '{query_text[:50]}...'")

        source_fields = es_query.get('_source', ["filename", "text", "chunk_id"])

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
            "_source": source_fields
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
        return VectorQueryResult(
            success=True,
            result=clean_documents,  # Pass clean documents instead of the full result dict
            query_type="vector",
        )
    except Exception as e:
        logger.error(f"Error executing vector query: {e}")
        error = QueryError(success=False, error=str(e), error_type="vector_query")
        raise QueryErrorException(error) from e

def convert_json_to_markdown(data, title: str = "Query Results") -> str:
    """Convert JSON query results to markdown formatted table."""
    logger.info("🔄 Starting markdown generation from JSON data")
    logger.info(f"Data type: {type(data).__name__}, Title: '{title}'")

    if not data:
        logger.warning("No data provided for markdown conversion")
        return f"# {title}\n\nNo data provided."

    records = []
    total_count = 0

    # Handle standard ES response with hits
    if isinstance(data, dict) and 'hits' in data:
        logger.info("Processing standard Elasticsearch response with hits")
        hits = data['hits']['hits']
        if not hits:
            logger.warning("No hits found in Elasticsearch response")
            return f"# {title}\n\nNo results found."

        for hit in hits:
            source = hit.get('_source', {})
            if source:
                records.append(source)
                logger.debug(f"Added hit source: {json.dumps(source)[:100]}...")

        total_hits = data['hits']['total']
        if isinstance(total_hits, dict):
            total_count = total_hits.get('value', len(records))
        else:
            total_count = total_hits if total_hits else len(records)

        logger.info(f"Processed {len(records)} hits from {total_count} total hits")

    # Handle aggregation results (already processed into list of dictionaries)
    elif isinstance(data, list):
        logger.info(f"Processing list data with {len(data)} items")
        records = [record for record in data if isinstance(record, dict)]
        total_count = len(records)
        logger.info(f"Filtered to {len(records)} dictionary records")

        # Special handling for aggregation results with nested structure
        if records and any(isinstance(v, dict) for record in records for v in record.values()):
            logger.info("Detected complex nested structure in aggregation results, using special formatter")

            # Log a sample of the data structure
            if records:
                sample = records[0]
                logger.debug(f"Sample record structure: {json.dumps(sample)}")

                # Find and log any nested dictionary values
                for key, value in sample.items():
                    if isinstance(value, dict):
                        logger.debug(f"Nested dictionary found at key '{key}': {json.dumps(value)}")

            return _format_complex_aggregations(records, title)

    # Handle single dictionary result
    elif isinstance(data, dict):
        logger.info("Processing single dictionary result")
        records = [data]
        total_count = 1
        logger.debug(f"Dictionary data: {json.dumps(data)[:100]}...")
    else:
        logger.warning(f"Unsupported data format: {type(data).__name__}")
        return f"# {title}\n\nUnsupported data format provided."

    if not records:
        logger.warning("No valid records found after processing")
        return f"# {title}\n\nNo valid records found."

    # Extract all fields from records
    all_fields = set()
    for record in records:
        if isinstance(record, dict):
            all_fields.update(record.keys())

    logger.info(f"Extracted {len(all_fields)} unique fields from records")
    logger.debug(f"Fields: {sorted(list(all_fields))}")

    # Sort fields alphabetically for consistent display
    all_fields = sorted(list(all_fields))

    # Start building markdown table
    logger.info("Building markdown table")
    markdown = f"# {title}\n\n"

    if all_fields:
        # Create table header and separator
        header = "| " + " | ".join(all_fields) + " |"
        separator = "| " + " | ".join(["---"] * len(all_fields)) + " |"
        markdown += header + "\n" + separator + "\n"
        logger.debug(f"Created header with {len(all_fields)} columns")

        # Add rows
        for i, record in enumerate(records):
            row_data = []
            logger.debug(f"Processing record {i+1}/{len(records)}")

            for field in all_fields:
                value = record.get(field, "")

                # Log any potential problematic values
                if isinstance(value, (list, dict)):
                    logger.warning(f"Complex value type {type(value).__name__} for field '{field}' in record {i+1}")

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
