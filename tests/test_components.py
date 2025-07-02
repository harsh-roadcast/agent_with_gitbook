"""Tests for the remaining component implementations."""
from unittest.mock import patch

import pytest

from components.query_executor import DSPyQueryExecutor
from core.exceptions import QueryExecutionError
from core.interfaces import DatabaseType


class TestDSPyQueryExecutor:
    """Test DSPyQueryExecutor implementation."""

    def test_query_executor_initialization(self):
        """Test query executor can be initialized."""
        executor = DSPyQueryExecutor()
        assert executor is not None

    @patch('components.query_executor.execute_query')
    def test_execute_elastic_query_success(self, mock_execute_query):
        """Test successful Elasticsearch query execution."""
        # Setup mock
        mock_execute_query.return_value = {
            'success': True,
            'result': {'hits': {'hits': [{'_source': {'test': 'data'}}]}}
        }

        executor = DSPyQueryExecutor()
        result = executor.execute_query(
            database_type=DatabaseType.ELASTIC,
            user_query="test query",
            schema="test schema",
            instructions="test instructions"
        )

        assert result.database_type == DatabaseType.ELASTIC
        assert len(result.data) > 0

    def test_execute_query_unsupported_database(self):
        """Test error handling for unsupported database type."""
        executor = DSPyQueryExecutor()

        with pytest.raises(QueryExecutionError):
            executor.execute_query(
                database_type="UNSUPPORTED",
                user_query="test query",
                schema="test schema",
                instructions="test instructions"
            )
