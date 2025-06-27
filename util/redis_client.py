"""Redis client utility with environment variable configuration."""
import logging
import os
from typing import Optional, Any, Dict, List
import json

try:
    import redis
    from redis import Redis, ConnectionPool
    _has_redis = True
except ImportError:
    _has_redis = False
    logging.warning("redis package not installed. Redis functionality will not be available.")

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper with connection management and error handling."""

    def __init__(self):
        """Initialize Redis client with environment variables."""
        if not _has_redis:
            raise ImportError("redis package not installed. Please install it with: pip install redis")

        # Redis configuration from environment variables
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', '6379'))
        self.db = int(os.getenv('REDIS_DB', '0'))
        self.password = os.getenv('REDIS_PASSWORD', None)
        self.username = os.getenv('REDIS_USERNAME', None)
        self.ssl = os.getenv('REDIS_SSL', 'False').lower() == 'true'
        self.ssl_cert_reqs = os.getenv('REDIS_SSL_CERT_REQS', 'required')
        self.socket_timeout = int(os.getenv('REDIS_SOCKET_TIMEOUT', '5'))
        self.socket_connect_timeout = int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', '5'))
        self.max_connections = int(os.getenv('REDIS_MAX_CONNECTIONS', '50'))

        # Connection pool for better performance
        self.pool = ConnectionPool(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            username=self.username,
            ssl=self.ssl,
            ssl_cert_reqs=self.ssl_cert_reqs,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
            max_connections=self.max_connections,
            decode_responses=True  # Automatically decode responses to strings
        )

        self._client: Optional[Redis] = None

    @property
    def client(self) -> Redis:
        """Get Redis client instance (lazy initialization)."""
        if self._client is None:
            self._client = Redis(connection_pool=self.pool)
            logger.info(f"Connected to Redis at {self.host}:{self.port} (DB: {self.db})")
        return self._client

    def is_connected(self) -> bool:
        """Check if Redis connection is active."""
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis connection check failed: {e}")
            return False

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set a key-value pair with optional expiration."""
        try:
            # Serialize non-string values to JSON
            if not isinstance(value, str):
                value = json.dumps(value)

            result = self.client.set(key, value, ex=ex)
            logger.debug(f"Set key '{key}' with expiration {ex}s")
            return result
        except Exception as e:
            logger.error(f"Error setting key '{key}': {e}")
            return False

    def get(self, key: str, deserialize_json: bool = True) -> Optional[Any]:
        """Get value by key with optional JSON deserialization."""
        try:
            value = self.client.get(key)
            if value is None:
                return None

            # Try to deserialize JSON if requested
            if deserialize_json:
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # Return as string if not valid JSON
                    return value

            return value
        except Exception as e:
            logger.error(f"Error getting key '{key}': {e}")
            return None

    def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        try:
            count = self.client.delete(*keys)
            logger.debug(f"Deleted {count} keys: {keys}")
            return count
        except Exception as e:
            logger.error(f"Error deleting keys {keys}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Error checking existence of key '{key}': {e}")
            return False

    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key."""
        try:
            result = self.client.expire(key, seconds)
            logger.debug(f"Set expiration for key '{key}' to {seconds}s")
            return result
        except Exception as e:
            logger.error(f"Error setting expiration for key '{key}': {e}")
            return False

    def ttl(self, key: str) -> int:
        """Get time to live for a key."""
        try:
            return self.client.ttl(key)
        except Exception as e:
            logger.error(f"Error getting TTL for key '{key}': {e}")
            return -1

    def hset(self, name: str, mapping: Dict[str, Any]) -> int:
        """Set multiple hash fields."""
        try:
            # Serialize non-string values in the mapping
            serialized_mapping = {}
            for k, v in mapping.items():
                if not isinstance(v, str):
                    serialized_mapping[k] = json.dumps(v)
                else:
                    serialized_mapping[k] = v

            count = self.client.hset(name, mapping=serialized_mapping)
            logger.debug(f"Set {count} hash fields in '{name}'")
            return count
        except Exception as e:
            logger.error(f"Error setting hash fields in '{name}': {e}")
            return 0

    def hget(self, name: str, key: str, deserialize_json: bool = True) -> Optional[Any]:
        """Get hash field value."""
        try:
            value = self.client.hget(name, key)
            if value is None:
                return None

            # Try to deserialize JSON if requested
            if deserialize_json:
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value

            return value
        except Exception as e:
            logger.error(f"Error getting hash field '{key}' from '{name}': {e}")
            return None

    def hgetall(self, name: str, deserialize_json: bool = True) -> Dict[str, Any]:
        """Get all hash fields."""
        try:
            data = self.client.hgetall(name)
            if not data:
                return {}

            # Try to deserialize JSON values if requested
            if deserialize_json:
                result = {}
                for k, v in data.items():
                    try:
                        result[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        result[k] = v
                return result

            return data
        except Exception as e:
            logger.error(f"Error getting all hash fields from '{name}': {e}")
            return {}

    def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields."""
        try:
            count = self.client.hdel(name, *keys)
            logger.debug(f"Deleted {count} hash fields from '{name}': {keys}")
            return count
        except Exception as e:
            logger.error(f"Error deleting hash fields from '{name}': {e}")
            return 0

    def lpush(self, name: str, *values: Any) -> int:
        """Push values to the left of a list."""
        try:
            # Serialize non-string values
            serialized_values = []
            for value in values:
                if not isinstance(value, str):
                    serialized_values.append(json.dumps(value))
                else:
                    serialized_values.append(value)

            count = self.client.lpush(name, *serialized_values)
            logger.debug(f"Pushed {len(values)} values to list '{name}'")
            return count
        except Exception as e:
            logger.error(f"Error pushing to list '{name}': {e}")
            return 0

    def lrange(self, name: str, start: int = 0, end: int = -1, deserialize_json: bool = True) -> List[Any]:
        """Get list range."""
        try:
            values = self.client.lrange(name, start, end)
            if not values:
                return []

            # Try to deserialize JSON values if requested
            if deserialize_json:
                result = []
                for value in values:
                    try:
                        result.append(json.loads(value))
                    except (json.JSONDecodeError, TypeError):
                        result.append(value)
                return result

            return values
        except Exception as e:
            logger.error(f"Error getting list range from '{name}': {e}")
            return []

    def ltrim(self, name: str, start: int, end: int) -> bool:
        """Trim list to specified range."""
        try:
            result = self.client.ltrim(name, start, end)
            logger.debug(f"Trimmed list '{name}' to range {start}:{end}")
            return result
        except Exception as e:
            logger.error(f"Error trimming list '{name}': {e}")
            return False

    def flushdb(self) -> bool:
        """Clear current database."""
        try:
            result = self.client.flushdb()
            logger.warning(f"Flushed Redis database {self.db}")
            return result
        except Exception as e:
            logger.error(f"Error flushing database: {e}")
            return False

    def close(self) -> None:
        """Close Redis connection."""
        try:
            if self._client:
                self._client.close()
                logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> Optional[RedisClient]:
    """Get global Redis client instance."""
    global _redis_client

    if not _has_redis:
        logger.warning("Redis not available - redis package not installed")
        return None

    if _redis_client is None:
        try:
            _redis_client = RedisClient()
            # Test connection
            if not _redis_client.is_connected():
                logger.error("Failed to connect to Redis")
                return None
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            return None

    return _redis_client


def is_redis_available() -> bool:
    """Check if Redis is available and connected."""
    client = get_redis_client()
    return client is not None and client.is_connected()
