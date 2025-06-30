"""Redis client utility for caching and session management."""
import json
import logging
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


def store_message_query(session_id: str, message_id: str, es_query: Dict[str, Any], ttl: int = 7200) -> bool:
    """Store Elasticsearch query for a specific message."""
    key = f"session_id:{session_id}:message_id:{message_id}"
    query_json = json.dumps(es_query)
    redis_client.setex(key, ttl, query_json)
    logger.info(f"Stored ES query for session {session_id}, message {message_id}")
    return True


def get_message_query(session_id: str, message_id: str) -> Dict[str, Any]:
    """Retrieve Elasticsearch query for a specific message."""
    key = f"session_id:{session_id}:message_id:{message_id}"
    query_json = redis_client.get(key)

    if query_json:
        return json.loads(query_json)
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

