"""Configuration management with validation and environment support."""
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ElasticsearchConfig:
    """Elasticsearch configuration."""
    host: str
    username: str
    password: str
    verify_certs: bool = False
    request_timeout: int = 30


@dataclass
class ModelConfig:
    """Model configuration for embeddings and LLM."""
    embedding_model: str = 'all-MiniLM-L6-v2'
    openai_api_key: str = ""
    default_chart_type: str = "column"
    default_query_size: int = 10


@dataclass
class AuthConfig:
    """Authentication configuration."""
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    token_expire_minutes: int = 30


@dataclass
class AppConfig:
    """Main application configuration."""
    elasticsearch: ElasticsearchConfig
    models: ModelConfig
    auth: AuthConfig
    es_schema: str
    es_instructions: str
    log_level: str = "INFO"


class ConfigManager:
    """Centralized configuration management."""

    def __init__(self):
        self._config: Optional[AppConfig] = None
        self._llm_initialized = False

    @property
    def config(self) -> AppConfig:
        """Get configuration, loading it if not already loaded."""
        if self._config is None:
            self._config = self._load_config()
            # Initialize LM when config is first accessed
            self._ensure_llm_initialized()
        return self._config

    def _ensure_llm_initialized(self):
        """Ensure DSPy LM is initialized."""
        if not self._llm_initialized:
            from services.llm_service import init_llm
            init_llm("gpt-4o-mini")
            self._llm_initialized = True
            logger.info("DSPy LM initialized successfully")

    def _load_config(self) -> AppConfig:
        """Load configuration from environment variables."""
        elasticsearch_config = ElasticsearchConfig(
            host=os.getenv('ES_HOST', 'https://62.72.41.235:9200'),
            username=os.getenv('ES_USERNAME', 'elastic'),
            password=os.getenv('ES_PASSWORD', 'GGgCYcnpA_0R_fT5TfFY'),
            verify_certs=os.getenv('ES_VERIFY_CERTS', 'False').lower() == 'true',
            request_timeout=int(os.getenv('ES_REQUEST_TIMEOUT', '30'))
        )

        model_config = ModelConfig(
            embedding_model=os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'),
            openai_api_key=os.getenv('OPENAI_API_KEY', ''),
            default_chart_type=os.getenv('DEFAULT_CHART_TYPE', 'column'),
            default_query_size=int(os.getenv('DEFAULT_QUERY_SIZE', '10'))
        )

        auth_config = AuthConfig(
            jwt_secret_key=os.getenv('JWT_SECRET_KEY', ''),
            jwt_algorithm=os.getenv('JWT_ALGORITHM', 'HS256'),
            token_expire_minutes=int(os.getenv('TOKEN_EXPIRE_MINUTES', '30'))
        )

        return AppConfig(
            elasticsearch=elasticsearch_config,
            models=model_config,
            auth=auth_config,
            es_schema=self._get_es_schema(),
            es_instructions=os.getenv('ES_INSTRUCTIONS', ''),
            log_level=os.getenv('LOG_LEVEL', 'INFO')
        )

    def _get_es_schema(self) -> str:
        """Get Elasticsearch schema definition from Redis cache."""
        from util.redis_client import get_index_schema

        schema_dict = get_index_schema()
        if schema_dict:
            formatted_schema = f"INDEX_SCHEMA = {json.dumps(schema_dict, indent=4)}"
            logger.info("Elasticsearch schema loaded from Redis cache")
            return formatted_schema

        logger.warning("No schema data found in Redis cache")
        return "INDEX_SCHEMA = {}"

    def update_config(self, **kwargs) -> None:
        """Update configuration values for testing."""
        if self._config is None:
            self._config = self._load_config()

        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)


# Global configuration manager instance
config_manager = ConfigManager()
