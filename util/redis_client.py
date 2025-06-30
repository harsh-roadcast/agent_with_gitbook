"""Redis client utility for caching and session management."""
import json
import logging
import time
from typing import Any, Dict
import redis

logger = logging.getLogger(__name__)

# Global Redis client instance
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5
)


def store_message_query(session_id: str, message_id: str, es_query: Dict[str, Any], index_name: str, ttl: int = 7200) -> bool:
    """Store Elasticsearch query and index name for a specific message."""
    key = f"session_id:{session_id}:message_id:{message_id}"

    # Store both query and index in a single object
    query_data = {
        "es_query": es_query,
        "index_name": index_name,
        "timestamp": time.time()
    }

    query_json = json.dumps(query_data)
    redis_client.setex(key, ttl, query_json)
    logger.info(f"Stored ES query and index '{index_name}' for session {session_id}, message {message_id}")
    return True


def get_message_query(session_id: str, message_id: str) -> Dict[str, Any]:
    """Retrieve Elasticsearch query and index name for a specific message."""
    key = f"session_id:{session_id}:message_id:{message_id}"
    query_json = redis_client.get(key)

    if query_json:
        query_data = json.loads(query_json)

        # Handle legacy format (just the query) and new format (query + index)
        if "es_query" in query_data and "index_name" in query_data:
            return query_data
        else:
            # Legacy format - return in old structure for backward compatibility
            return {"es_query": query_data, "index_name": None}

    return {}


def get_session_message_queries(session_id: str) -> Dict[str, Dict[str, Any]]:
    """Get all message queries for a session."""
    pattern = f"session_id:{session_id}:message_id:*"
    keys = redis_client.keys(pattern)

    queries = {}
    for key in keys:
        parts = key.split(':')
        if len(parts) >= 4:
            message_id = parts[3]
            query_json = redis_client.get(key)
            if query_json:
                queries[message_id] = json.loads(query_json)

    return queries


def store_index_schema(schema_dict: Dict[str, Any], ttl: int = 86400) -> None:
    """Store index schema in Redis."""
    formatted_schema = {"INDEX_SCHEMA": schema_dict}
    schema_json = json.dumps(formatted_schema, indent=2)
    redis_client.setex("elasticsearch:index_schema", ttl, schema_json)
    logger.info(f"Stored index schema for {len(schema_dict)} indices")


def get_index_schema() -> Dict[str, Any]:
    """Get index schema from Redis."""
    schema_json = redis_client.get("elasticsearch:index_schema")
    if schema_json:
        schema_data = json.loads(schema_json)
        return schema_data.get("INDEX_SCHEMA", {})
    return {}


def delete_index_schema() -> None:
    """Delete index schema from Redis."""
    redis_client.delete("elasticsearch:index_schema")
    logger.info("Deleted index schema from Redis cache")
