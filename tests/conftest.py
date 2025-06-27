"""Test configuration and fixtures for pytest."""
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from core.config import AppConfig, ElasticsearchConfig, ModelConfig
from core.container import DIContainer


@pytest.fixture
def mock_config():
    """Provide a mock configuration for testing."""
    elasticsearch_config = ElasticsearchConfig(
        host="http://localhost:9200",
        username="test_user",
        password="test_pass",
        verify_certs=False,
        request_timeout=10
    )

    model_config = ModelConfig(
        embedding_model="test-model",
        openai_api_key="test-key",
        default_chart_type="test-chart",
        default_query_size=5
    )

    return AppConfig(
        elasticsearch=elasticsearch_config,
        models=model_config,
        es_schema="test_schema",
        es_instructions="test_instructions",
        log_level="DEBUG"
    )


@pytest.fixture
def test_container():
    """Provide a clean container for testing."""
    container = DIContainer()
    container.clear_cache()
    yield container
    container.clear_cache()


@pytest.fixture
def sample_query_result():
    """Provide sample query result data for testing."""
    from core.interfaces import QueryResult, DatabaseType

    return QueryResult(
        database_type=DatabaseType.VECTOR,
        data=[
            {"id": 1, "name": "Test Item 1", "value": 100},
            {"id": 2, "name": "Test Item 2", "value": 200}
        ],
        raw_result={
            "hits": {
                "hits": [
                    {"_source": {"id": 1, "name": "Test Item 1", "value": 100}},
                    {"_source": {"id": 2, "name": "Test Item 2", "value": 200}}
                ],
                "total": {"value": 2}
            }
        },
        elastic_query={"query": {"match_all": {}}}
    )


@pytest.fixture
def sample_elasticsearch_response():
    """Provide sample Elasticsearch response for testing."""
    return {
        "took": 5,
        "timed_out": False,
        "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
        "hits": {
            "total": {"value": 2, "relation": "eq"},
            "max_score": 1.0,
            "hits": [
                {
                    "_index": "test_index",
                    "_type": "_doc",
                    "_id": "1",
                    "_score": 1.0,
                    "_source": {"id": 1, "name": "Test Item 1", "value": 100}
                },
                {
                    "_index": "test_index",
                    "_type": "_doc",
                    "_id": "2",
                    "_score": 1.0,
                    "_source": {"id": 2, "name": "Test Item 2", "value": 200}
                }
            ]
        }
    }


@pytest.fixture
def temp_env_file():
    """Create a temporary .env file for testing."""
    env_content = """
OPENAI_API_KEY=test_openai_key
ES_HOST=http://test-es:9200
ES_USERNAME=test_elastic_user
ES_PASSWORD=test_elastic_pass
ES_VERIFY_CERTS=true
ES_REQUEST_TIMEOUT=15
EMBEDDING_MODEL=test-embedding-model
DEFAULT_CHART_TYPE=bar
DEFAULT_QUERY_SIZE=20
LOG_LEVEL=WARNING
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write(env_content.strip())
        f.flush()

        # Store original env vars
        original_env = {}
        for line in env_content.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                original_env[key] = os.environ.get(key)
                os.environ[key] = value

        yield f.name

        # Restore original env vars
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        # Clean up temp file
        os.unlink(f.name)


# Configure pytest to handle async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Mock DSPy components to avoid actual model calls during testing
@pytest.fixture(autouse=True)
def mock_dspy_components():
    """Automatically mock DSPy components for all tests."""
    with patch('dspy.Predict') as mock_predict, \
         patch('dspy.ReAct') as mock_react, \
         patch('dspy.ChainOfThought') as mock_cot:

        # Configure default behaviors
        mock_predict.return_value = Mock()
        mock_react.return_value = Mock()
        mock_cot.return_value = Mock()

        yield {
            'predict': mock_predict,
            'react': mock_react,
            'cot': mock_cot
        }
