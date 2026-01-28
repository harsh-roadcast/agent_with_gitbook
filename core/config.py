"""Configuration management with validation and environment support."""
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional, Tuple

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
class GitBookCrawlerConfig:
    base_url: str = "https://roadcast.gitbook.io/roadcast-docs"
    allowed_path_prefixes: Tuple[str, ...] = tuple(
        prefix.strip() for prefix in os.getenv("GITBOOK_ALLOWED_PREFIXES", "/documentation").split(",") if prefix.strip()
    )
    max_pages: int = 200
    request_timeout: int = 15
    auth_token: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.base_url:
            self.base_url = "https://roadcast.gitbook.io/roadcast-docs"
        self.base_url = self.base_url.rstrip("/")
        if not self.allowed_path_prefixes:
            self.allowed_path_prefixes = ("/",)
        else:
            self.allowed_path_prefixes = tuple(prefix if prefix.startswith("/") else f"/{prefix}" for prefix in self.allowed_path_prefixes)


@dataclass
class GitBookProcessorConfig:
    index_name: str = os.getenv("GITBOOK_INDEX_NAME", "gitbook_docs")
    max_pages: int = int(os.getenv("GITBOOK_MAX_PAGES", "150"))
    chunk_size: int = int(os.getenv("GITBOOK_CHUNK_SIZE", "1000"))


@dataclass
class AppConfig:
    """Main application configuration."""
    elasticsearch: ElasticsearchConfig
    models: ModelConfig
    auth: AuthConfig
    gitbook: GitBookCrawlerConfig
    gitbook_processor: GitBookProcessorConfig
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
            init_llm()
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

        gitbook_crawler_config = GitBookCrawlerConfig(
            base_url=os.getenv("GITBOOK_SPACE_URL", "https://roadcast.gitbook.io/roadcast-docs"),
            auth_token=os.getenv("GITBOOK_AUTH_TOKEN"),
            max_pages=int(os.getenv("GITBOOK_CRAWLER_MAX_PAGES", "200"))
        )

        gitbook_processor_config = GitBookProcessorConfig(
            index_name=os.getenv("GITBOOK_INDEX_NAME", "gitbook_docs"),
            max_pages=int(os.getenv("GITBOOK_MAX_PAGES", "150")),
            chunk_size=int(os.getenv("GITBOOK_CHUNK_SIZE", "1000"))
        )

        return AppConfig(
            elasticsearch=elasticsearch_config,
            models=model_config,
            auth=auth_config,
            gitbook=gitbook_crawler_config,
            gitbook_processor=gitbook_processor_config,
            log_level=os.getenv('LOG_LEVEL', 'INFO')
        )


    def update_config(self, **kwargs) -> None:
        """Update configuration values for testing."""
        if self._config is None:
            self._config = self._load_config()

        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)


# Global configuration manager instance
config_manager = ConfigManager()
