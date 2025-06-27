"""Integration tests for the complete query agent system."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from core.interfaces import DatabaseType, QueryResult, ProcessedResult
from core.container import DIContainer
from agents.query_agent import QueryAgent


class TestQueryAgentIntegration:
    """Integration tests for the complete query agent system."""

    def setup_method(self):
        """Setup test fixtures."""
        self.container = DIContainer()
        # Clear any cached instances
        self.container.clear_cache()

    def test_full_query_processing_pipeline(self):
        """Test the complete query processing pipeline."""
        # Mock all dependencies
        mock_db_selector = Mock()
        mock_db_selector.select_database.return_value = DatabaseType.VECTOR

        mock_query_executor = Mock()
        mock_query_result = QueryResult(
            database_type=DatabaseType.VECTOR,
            data=[{"id": 1, "name": "test"}],
            raw_result={"hits": {"hits": [{"_source": {"id": 1, "name": "test"}}]}},
            elastic_query=None
        )
        mock_query_executor.execute_query.return_value = mock_query_result

        mock_result_processor = Mock()
        mock_processed_result = ProcessedResult(
            query_result=mock_query_result,
            summary="Test summary",
            chart_config={"type": "column"},
            chart_html="<div>Chart</div>"
        )
        mock_result_processor.process_results.return_value = mock_processed_result

        # Override container instances with mocks
        self.container.override_instance('database_selector', mock_db_selector)
        self.container.override_instance('query_executor', mock_query_executor)
        self.container.override_instance('result_processor', mock_result_processor)

        # Create query agent
        query_agent = QueryAgent(
            database_selector=mock_db_selector,
            query_executor=mock_query_executor,
            result_processor=mock_result_processor
        )

        # Test query processing
        result = query_agent.process_query("test query", "conversation history")

        # Verify results
        assert isinstance(result, ProcessedResult)
        assert result.summary == "Test summary"
        assert result.chart_config == {"type": "column"}
        assert result.chart_html == "<div>Chart</div>"

        # Verify method calls
        mock_db_selector.select_database.assert_called_once()
        mock_query_executor.execute_query.assert_called_once()
        mock_result_processor.process_results.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_query_processing_pipeline(self):
        """Test the async query processing pipeline."""
        # Mock all dependencies
        mock_db_selector = Mock()
        mock_db_selector.select_database.return_value = DatabaseType.ELASTIC

        mock_query_executor = Mock()
        mock_query_result = QueryResult(
            database_type=DatabaseType.ELASTIC,
            data=[{"id": 2, "type": "elastic"}],
            raw_result={"hits": {"hits": [{"_source": {"id": 2, "type": "elastic"}}]}},
            elastic_query={"query": {"match_all": {}}}
        )
        mock_query_executor.execute_query.return_value = mock_query_result

        # Mock async generator for result processor
        async def mock_async_generator():
            yield "database", "Elastic"
            yield "data", [{"id": 2, "type": "elastic"}]
            yield "summary", "Async test summary"
            yield "chart_config", {"type": "bar"}
            yield "chart_html", "<div>Async Chart</div>"

        mock_result_processor = Mock()
        mock_result_processor.process_results_async.return_value = mock_async_generator()

        # Create query agent
        query_agent = QueryAgent(
            database_selector=mock_db_selector,
            query_executor=mock_query_executor,
            result_processor=mock_result_processor
        )

        # Test async query processing
        results = {}
        async for field_name, field_value in query_agent.process_query_async("async test query"):
            results[field_name] = field_value

        # Verify results
        assert results["database"] == "Elastic"
        assert results["data"] == [{"id": 2, "type": "elastic"}]
        assert results["summary"] == "Async test summary"
        assert results["chart_config"] == {"type": "bar"}
        assert results["chart_html"] == "<div>Async Chart</div>"

        # Verify method calls
        mock_db_selector.select_database.assert_called_once()
        mock_query_executor.execute_query.assert_called_once()
        mock_result_processor.process_results_async.assert_called_once()

    def test_error_handling_in_pipeline(self):
        """Test error handling throughout the pipeline."""
        # Mock database selector to raise an exception
        mock_db_selector = Mock()
        mock_db_selector.select_database.side_effect = Exception("Database selection failed")

        mock_query_executor = Mock()
        mock_result_processor = Mock()

        # Create query agent
        query_agent = QueryAgent(
            database_selector=mock_db_selector,
            query_executor=mock_query_executor,
            result_processor=mock_result_processor
        )

        # Test that exception is properly handled and re-raised
        with pytest.raises(Exception) as exc_info:
            query_agent.process_query("test query")

        assert "Query processing failed" in str(exc_info.value)

        # Verify that subsequent components weren't called
        mock_query_executor.execute_query.assert_not_called()
        mock_result_processor.process_results.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_error_handling(self):
        """Test async error handling."""
        # Mock database selector to raise an exception
        mock_db_selector = Mock()
        mock_db_selector.select_database.side_effect = Exception("Async database selection failed")

        mock_query_executor = Mock()
        mock_result_processor = Mock()

        # Create query agent
        query_agent = QueryAgent(
            database_selector=mock_db_selector,
            query_executor=mock_query_executor,
            result_processor=mock_result_processor
        )

        # Test async error handling
        results = []
        async for field_name, field_value in query_agent.process_query_async("test query"):
            results.append((field_name, field_value))

        # Should yield error
        assert len(results) == 1
        assert results[0][0] == "error"
        assert "Async database selection failed" in results[0][1]


class TestDependencyInjectionContainer:
    """Test the dependency injection container."""

    def setup_method(self):
        """Setup test fixtures."""
        self.container = DIContainer()
        self.container.clear_cache()

    def test_singleton_behavior(self):
        """Test that container returns the same instance for multiple calls."""
        # Get instances multiple times
        selector1 = self.container.get_database_selector()
        selector2 = self.container.get_database_selector()

        # Should be the same instance
        assert selector1 is selector2

        # Same for other components
        executor1 = self.container.get_query_executor()
        executor2 = self.container.get_query_executor()
        assert executor1 is executor2

    def test_dependency_injection_wiring(self):
        """Test that dependencies are properly wired."""
        # Get result processor (which depends on summary and chart generators)
        result_processor = self.container.get_result_processor()

        # Verify it has the expected dependencies
        assert hasattr(result_processor, 'summary_generator')
        assert hasattr(result_processor, 'chart_generator')

        # Get query agent (which depends on multiple components)
        query_agent = self.container.get_query_agent()

        # Verify it has the expected dependencies
        assert hasattr(query_agent, 'database_selector')
        assert hasattr(query_agent, 'query_executor')
        assert hasattr(query_agent, 'result_processor')

    def test_cache_clearing(self):
        """Test cache clearing functionality."""
        # Get an instance
        selector1 = self.container.get_database_selector()

        # Clear cache
        self.container.clear_cache()

        # Get instance again
        selector2 = self.container.get_database_selector()

        # Should be different instances
        assert selector1 is not selector2

    def test_instance_override(self):
        """Test instance override functionality."""
        # Create a mock instance
        mock_selector = Mock()

        # Override the instance
        self.container.override_instance('database_selector', mock_selector)

        # Get the instance
        selector = self.container.get_database_selector()

        # Should be the mock instance
        assert selector is mock_selector
