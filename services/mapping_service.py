"""Service for managing Elasticsearch index mappings in Redis."""
import json
import logging
from typing import Dict, List

from services.search_service import es_client
from util.redis_client import redis_client, store_index_schema, get_index_schema

logger = logging.getLogger(__name__)


def extract_fields_from_mapping(mapping: Dict) -> List[str]:
    """Extract field names from Elasticsearch mapping recursively."""
    fields = []

    def traverse_properties(props: Dict, prefix: str = ""):
        for field_name, field_config in props.items():
            full_field_name = f"{prefix}.{field_name}" if prefix else field_name
            fields.append(full_field_name)

            if isinstance(field_config, dict) and "properties" in field_config:
                traverse_properties(field_config["properties"], full_field_name)

    if "properties" in mapping:
        traverse_properties(mapping["properties"])
    elif "mappings" in mapping and "properties" in mapping["mappings"]:
        traverse_properties(mapping["mappings"]["properties"])
    else:
        for key, value in mapping.items():
            if isinstance(value, dict) and "properties" in value:
                traverse_properties(value["properties"])
                break

    return sorted(list(set(fields)))


def fetch_all_index_mappings() -> Dict[str, List[str]]:
    """Fetch all index mappings from Elasticsearch and extract field names."""
    logger.info("Fetching all Elasticsearch index mappings")

    indices_response = es_client.cat.indices(format="json", h="index")
    index_schema = {}

    for index_info in indices_response:
        index_name = index_info["index"]

        if index_name.startswith(('.', '_')):
            continue

        logger.debug(f"Fetching mapping for index: {index_name}")
        mapping_response = es_client.indices.get_mapping(index=index_name)

        if index_name in mapping_response:
            mapping = mapping_response[index_name]
            fields = extract_fields_from_mapping(mapping)

            if fields:
                index_schema[index_name] = fields
                logger.info(f"Extracted {len(fields)} fields from index '{index_name}'")

    logger.info(f"Successfully fetched mappings for {len(index_schema)} indices")
    return index_schema


def initialize_index_schema() -> bool:
    """Initialize index schema on application startup."""
    logger.info("Initializing index schema on startup")

    existing_schema = get_index_schema()
    if existing_schema:
        logger.info(f"Found existing index schema in Redis with {len(existing_schema)} indices")
        return True

    index_schema = fetch_all_index_mappings()
    if index_schema:
        store_index_schema(index_schema)
        logger.info(f"Successfully initialized index schema with {len(index_schema)} indices")
        return True

    logger.error("Failed to initialize index schema")
    return False


def refresh_index_schema() -> Dict:
    """Refresh index schema by fetching from Elasticsearch and storing in Redis."""
    logger.info("Refreshing index schema")

    index_schema = fetch_all_index_mappings()
    if index_schema:
        store_index_schema(index_schema)
        return {
            "success": True,
            "message": "Index schema refreshed successfully",
            "indices_count": len(index_schema),
            "indices": list(index_schema.keys())
        }

    return {
        "success": False,
        "error": "No index mappings found",
        "indices_count": 0
    }


def get_index_fields(index_name: str) -> List[str]:
    """Get field names for a specific index from Redis cache."""
    schema = get_index_schema()
    return schema.get(index_name, [])


def get_all_indices() -> List[str]:
    """Get list of all available index names from Redis cache."""
    schema = get_index_schema()
    return list(schema.keys())
