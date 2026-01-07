"""Redis client utility for caching and session management."""
import json
import logging
import os
import time
from typing import Any, Dict

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


def _create_redis_client() -> redis.Redis | None:
    """Create a Redis client from environment variables, return None if unavailable."""
    host = os.getenv("REDIS_HOST")
    if not host:
        logger.warning("REDIS_HOST not configured; Redis-dependent features disabled")
        return None

    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    password = os.getenv("REDIS_PASSWORD") or None
    use_ssl = os.getenv("REDIS_SSL", "false").lower() == "true"

    try:
        client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            ssl=use_ssl,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        client.ping()
        logger.info(f"Connected to Redis at {host}:{port} db={db} ssl={use_ssl}")
        return client
    except RedisError as exc:
        logger.error(f"Failed to connect to Redis at {host}:{port}: {exc}")
        return None


# Global Redis client instance (may be None if not configured)
redis_client = _create_redis_client()


def _is_redis_available() -> bool:
    if redis_client is None:
        logger.debug("Redis unavailable; skipping cache operation")
        return False
    return True


def store_message_query(session_id: str, message_id: str, es_query: Dict[str, Any], index_name: str, ttl: int = 7200) -> bool:
    """Store Elasticsearch query and index name for a specific message."""
    if not _is_redis_available():
        return False
    key = f"session_id:{session_id}:message_id:{message_id}"

    # Store both query and index in a single object
    query_data = {
        "es_query": es_query,
        "index_name": index_name,
        "timestamp": time.time()
    }

    query_json = json.dumps(query_data)
    try:
        redis_client.setex(key, ttl, query_json)
        logger.info(f"Stored ES query and index '{index_name}' for session {session_id}, message {message_id}")
        return True
    except RedisError as exc:
        logger.warning(f"Failed to store Redis key {key}: {exc}")
        return False


def get_message_query(session_id: str, message_id: str) -> Dict[str, Any]:
    """Retrieve Elasticsearch query and index name for a specific message."""
    if not _is_redis_available():
        return {}
    key = f"session_id:{session_id}:message_id:{message_id}"
    try:
        query_json = redis_client.get(key)
    except RedisError as exc:
        logger.warning(f"Failed to fetch Redis key {key}: {exc}")
        return {}

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
    if not _is_redis_available():
        return {}
    pattern = f"session_id:{session_id}:message_id:*"
    try:
        keys = redis_client.keys(pattern)
    except RedisError as exc:
        logger.warning(f"Failed to scan Redis keys with pattern {pattern}: {exc}")
        return {}

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
    if not _is_redis_available():
        return
    formatted_schema = {"INDEX_SCHEMA": schema_dict}
    schema_json = json.dumps(formatted_schema, indent=2)
    try:
        redis_client.setex("elasticsearch:index_schema", ttl, schema_json)
        logger.info(f"Stored index schema for {len(schema_dict)} indices")
    except RedisError as exc:
        logger.warning(f"Failed to cache index schema: {exc}")


def get_index_schema() -> Dict[str, Any]:
    """Get index schema from Redis."""
    if not _is_redis_available():
        return {}
    try:
        schema_json = redis_client.get("elasticsearch:index_schema")
    except RedisError as exc:
        logger.warning(f"Failed to read cached index schema: {exc}")
        return {}
    if schema_json:
        schema_data = json.loads(schema_json)
        return schema_data.get("INDEX_SCHEMA", {})
    return {}


def delete_index_schema() -> None:
    """Delete index schema from Redis."""
    if not _is_redis_available():
        return
    try:
        redis_client.delete("elasticsearch:index_schema")
        logger.info("Deleted index schema from Redis cache")
    except RedisError as exc:
        logger.warning(f"Failed to delete cached index schema: {exc}")
