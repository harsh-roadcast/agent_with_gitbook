"""Redis client utility for caching and session management."""
import json
import logging
from typing import Optional, Any, Dict
import redis
from datetime import timedelta

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None
_redis_available = False


def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client instance."""
    global _redis_client, _redis_available

    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            _redis_client.ping()
            _redis_available = True
            logger.info("Redis client connected successfully")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            _redis_client = None
            _redis_available = False

    return _redis_client


def is_redis_available() -> bool:
    """Check if Redis is available."""
    global _redis_available
    if _redis_client is None:
        get_redis_client()
    return _redis_available


def store_message_query(session_id: str, message_id: str, es_query: Dict[str, Any], ttl: int = 7200) -> bool:
    """
    Store Elasticsearch query for a specific message.

    Args:
        session_id: Chat session identifier
        message_id: Individual message identifier
        es_query: Elasticsearch query dictionary
        ttl: Time to live in seconds (default: 2 hours)

    Returns:
        True if stored successfully, False otherwise
    """
    client = get_redis_client()
    if not client:
        logger.warning("Redis not available, cannot store message query")
        return False

    try:
        # Use the requested key format: session_id:<>:message_id:<>
        key = f"session_id:{session_id}:message_id:{message_id}"
        query_json = json.dumps(es_query)

        # Store the query with TTL
        client.setex(key, ttl, query_json)
        logger.info(f"Stored ES query for session {session_id}, message {message_id} with key: {key}")
        return True

    except Exception as e:
        logger.error(f"Error storing message query: {e}")
        return False


def get_message_query(session_id: str, message_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve Elasticsearch query for a specific message.

    Args:
        session_id: Chat session identifier
        message_id: Individual message identifier

    Returns:
        Elasticsearch query dictionary or None if not found
    """
    client = get_redis_client()
    if not client:
        logger.warning("Redis not available, cannot retrieve message query")
        return None

    try:
        # Use the requested key format: session_id:<>:message_id:<>
        key = f"session_id:{session_id}:message_id:{message_id}"
        query_json = client.get(key)

        if query_json:
            query = json.loads(query_json)
            logger.debug(f"Retrieved ES query for session {session_id}, message {message_id}")
            return query
        else:
            logger.debug(f"No ES query found for session {session_id}, message {message_id}")
            return None

    except Exception as e:
        logger.error(f"Error retrieving message query: {e}")
        return None


def get_session_message_queries(session_id: str) -> Dict[str, Dict[str, Any]]:
    """
    Get all message queries for a session.

    Args:
        session_id: Chat session identifier

    Returns:
        Dictionary mapping message_id to es_query
    """
    client = get_redis_client()
    if not client:
        logger.warning("Redis not available, cannot retrieve session queries")
        return {}

    try:
        pattern = f"session_id:{session_id}:message_id:*"
        keys = client.keys(pattern)

        queries = {}
        for key in keys:
            # Extract message_id from key
            # Key format: session_id:<>:message_id:<>
            parts = key.split(':')
            if len(parts) >= 4:
                message_id = parts[3]
                query_json = client.get(key)
                if query_json:
                    queries[message_id] = json.loads(query_json)

        logger.debug(f"Retrieved {len(queries)} queries for session {session_id}")
        return queries

    except Exception as e:
        logger.error(f"Error retrieving session queries: {e}")
        return {}


def delete_message_query(session_id: str, message_id: str) -> bool:
    """
    Delete Elasticsearch query for a specific message.

    Args:
        session_id: Chat session identifier
        message_id: Individual message identifier

    Returns:
        True if deleted successfully, False otherwise
    """
    client = get_redis_client()
    if not client:
        logger.warning("Redis not available, cannot delete message query")
        return False

    try:
        # Use the requested key format: session_id:<>:message_id:<>
        key = f"session_id:{session_id}:message_id:{message_id}"
        deleted = client.delete(key)

        if deleted:
            logger.info(f"Deleted ES query for session {session_id}, message {message_id}")
            return True
        else:
            logger.debug(f"No ES query to delete for session {session_id}, message {message_id}")
            return False

    except Exception as e:
        logger.error(f"Error deleting message query: {e}")
        return False


def delete_session_queries(session_id: str) -> int:
    """
    Delete all message queries for a session.

    Args:
        session_id: Chat session identifier

    Returns:
        Number of queries deleted
    """
    client = get_redis_client()
    if not client:
        logger.warning("Redis not available, cannot delete session queries")
        return 0

    try:
        pattern = f"session_id:{session_id}:message_id:*"
        keys = client.keys(pattern)

        if keys:
            deleted = client.delete(*keys)
            logger.info(f"Deleted {deleted} queries for session {session_id}")
            return deleted
        else:
            logger.debug(f"No queries to delete for session {session_id}")
            return 0

    except Exception as e:
        logger.error(f"Error deleting session queries: {e}")
        return 0
