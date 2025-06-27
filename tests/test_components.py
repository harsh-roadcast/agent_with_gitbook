"""Tests for the component implementations."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import json
import asyncio

from core.interfaces import DatabaseType, QueryResult
from core.exceptions import DatabaseSelectionError, QueryExecutionError, SummaryGenerationError, ChartGenerationError
from components.database_selector import DSPyDatabaseSelector
from components.query_executor import DSPyQueryExecutor
from components.summary_generator import DSPySummaryGenerator
from components.chart_generator import DSPyChartGenerator


class TestDSPyDatabaseSelector:
    """Test DSPyDatabaseSelector implementation."""

    @patch('components.database_selector.dspy.Predict')
    def test_select_database_vector(self, mock_predict):
        """Test database selection returns Vector."""
        # Setup mock
        mock_result = Mock()
        mock_result.database = "Vector"
        mock_predict_instance = Mock()
        mock_predict_instance.return_value = mock_result
        mock_predict.return_value = mock_predict_instance

        selector = DSPyDatabaseSelector()
        result = selector.select_database("test query", "schema")

        assert result == DatabaseType.VECTOR
        mock_predict_instance.assert_called_once()

    @patch('components.database_selector.dspy.Predict')
    def test_select_database_elastic(self, mock_predict):
        """Test database selection returns Elastic."""
        # Setup mock
        mock_result = Mock()
        mock_result.database = "Elastic"
        mock_predict_instance = Mock()
        mock_predict_instance.return_value = mock_result
        mock_predict.return_value = mock_predict_instance

        selector = DSPyDatabaseSelector()
        result = selector.select_database("test query", "schema")

        assert result == DatabaseType.ELASTIC

    @patch('components.database_selector.dspy.Predict')
    def test_select_database_unknown_defaults_to_vector(self, mock_predict):
        """Test unknown database type defaults to Vector."""
        # Setup mock
        mock_result = Mock()
        mock_result.database = "Unknown"
        mock_predict_instance = Mock()
        mock_predict_instance.return_value = mock_result
        mock_predict.return_value = mock_predict_instance

        selector = DSPyDatabaseSelector()
        result = selector.select_database("test query", "schema")

        assert result == DatabaseType.VECTOR

    @patch('components.database_selector.dspy.Predict')
    def test_select_database_exception_handling(self, mock_predict):
        """Test exception handling in database selection."""
        # Setup mock to raise exception
        mock_predict_instance = Mock()
        mock_predict_instance.side_effect = Exception("DSPy error")
        mock_predict.return_value = mock_predict_instance

        selector = DSPyDatabaseSelector()

        with pytest.raises(DatabaseSelectionError):
            selector.select_database("test query", "schema")


class TestDSPyQueryExecutor:
    """Test DSPyQueryExecutor implementation."""

    @patch('components.query_executor.dspy.ReAct')
    def test_execute_vector_query(self, mock_react):
        """Test vector query execution."""
        # Setup mock
        mock_result = Mock()
        mock_result.data_json = '{"hits": {"hits": [{"_source": {"id": 1}}]}}'
        mock_result.elastic_query = None

        mock_agent = Mock()
        mock_agent.return_value = mock_result
        mock_react.return_value = mock_agent

        executor = DSPyQueryExecutor()
        result = executor.execute_query(
            DatabaseType.VECTOR, "test query", "schema", "instructions"
        )

        assert isinstance(result, QueryResult)
        assert result.database_type == DatabaseType.VECTOR
        assert result.data == [{"id": 1}]

    @patch('components.query_executor.dspy.ReAct')
    def test_execute_elastic_query(self, mock_react):
        """Test Elasticsearch query execution."""
        # Setup mock
        mock_result = Mock()
        mock_result.data_json = {"hits": {"hits": [{"_source": {"id": 2}}]}}
        mock_result.elastic_query = {"query": {"match_all": {}}}

        mock_agent = Mock()
        mock_agent.return_value = mock_result
        mock_react.return_value = mock_agent

        executor = DSPyQueryExecutor()
        result = executor.execute_query(
            DatabaseType.ELASTIC, "test query", "schema", "instructions"
        )

        assert isinstance(result, QueryResult)
        assert result.database_type == DatabaseType.ELASTIC
        assert result.data == [{"id": 2}]
        assert result.elastic_query == {"query": {"match_all": {}}}

    def test_unsupported_database_type(self):
        """Test handling of unsupported database type."""
        executor = DSPyQueryExecutor()

        # Create a mock enum value that doesn't exist
        with pytest.raises(QueryExecutionError):
            executor.execute_query(
                "UNSUPPORTED", "test query", "schema", "instructions"
            )


class TestDSPySummaryGenerator:
    """Test DSPySummaryGenerator implementation."""

    @patch('components.summary_generator.dspy.ChainOfThought')
    def test_generate_summary(self, mock_cot):
        """Test summary generation."""
        # Setup mock
        mock_result = Mock()
        mock_result.summary = "Test summary"
        mock_summarizer = Mock()
        mock_summarizer.return_value = mock_result
        mock_cot.return_value = mock_summarizer

        generator = DSPySummaryGenerator()
        result = generator.generate_summary("query", {"data": "test"}, "history")

        assert result == "Test summary"
        mock_summarizer.assert_called_once()

    @patch('components.summary_generator.dspy.ChainOfThought')
    def test_generate_summary_no_summary_attribute(self, mock_cot):
        """Test summary generation when result has no summary attribute."""
        # Setup mock
        mock_result = Mock(spec=[])  # No summary attribute
        mock_summarizer = Mock()
        mock_summarizer.return_value = mock_result
        mock_cot.return_value = mock_summarizer

        generator = DSPySummaryGenerator()
        result = generator.generate_summary("query", {"data": "test"})

        assert result is None

    @patch('components.summary_generator.dspy.ChainOfThought')
    def test_generate_summary_exception(self, mock_cot):
        """Test summary generation exception handling."""
        # Setup mock to raise exception
        mock_summarizer = Mock()
        mock_summarizer.side_effect = Exception("DSPy error")
        mock_cot.return_value = mock_summarizer

        generator = DSPySummaryGenerator()

        with pytest.raises(SummaryGenerationError):
            generator.generate_summary("query", {"data": "test"})

    @pytest.mark.asyncio
    @patch('components.summary_generator.asyncio.to_thread')
    async def test_generate_summary_async(self, mock_to_thread):
        """Test async summary generation."""
        mock_to_thread.return_value = "Async summary"

        generator = DSPySummaryGenerator()
        result = await generator.generate_summary_async("query", {"data": "test"})

        assert result == "Async summary"
        mock_to_thread.assert_called_once()


class TestDSPyChartGenerator:
    """Test DSPyChartGenerator implementation."""

    @patch('components.chart_generator.generate_chart_from_config')
    @patch('components.chart_generator.dspy.ChainOfThought')
    def test_generate_chart(self, mock_cot, mock_chart_util):
        """Test chart generation."""
        # Setup mocks
        mock_result = Mock()
        mock_result.highchart_config = {"type": "column", "data": []}
        mock_selector = Mock()
        mock_selector.return_value = mock_result
        mock_cot.return_value = mock_selector

        mock_chart_util.return_value = "<div>Chart HTML</div>"

        generator = DSPyChartGenerator()
        chart_config, chart_html = generator.generate_chart({"data": "test"}, "query")

        assert chart_config == {"type": "column", "data": []}
        assert chart_html == "<div>Chart HTML</div>"
        mock_selector.assert_called_once()
        mock_chart_util.assert_called_once_with({"type": "column", "data": []})

    @patch('components.chart_generator.dspy.ChainOfThought')
    def test_generate_chart_no_config(self, mock_cot):
        """Test chart generation when no config is returned."""
        # Setup mock
        mock_result = Mock(spec=[])  # No highchart_config attribute
        mock_selector = Mock()
        mock_selector.return_value = mock_result
        mock_cot.return_value = mock_selector

        generator = DSPyChartGenerator()
        chart_config, chart_html = generator.generate_chart({"data": "test"}, "query")

        assert chart_config is None
        assert chart_html is None

    @patch('components.chart_generator.dspy.ChainOfThought')
    def test_generate_chart_exception(self, mock_cot):
        """Test chart generation exception handling."""
        # Setup mock to raise exception
        mock_selector = Mock()
        mock_selector.side_effect = Exception("DSPy error")
        mock_cot.return_value = mock_selector

        generator = DSPyChartGenerator()

        with pytest.raises(ChartGenerationError):
            generator.generate_chart({"data": "test"}, "query")

    @pytest.mark.asyncio
    @patch('components.chart_generator.asyncio.to_thread')
    async def test_generate_chart_async(self, mock_to_thread):
        """Test async chart generation."""
        mock_to_thread.return_value = ({"type": "column"}, "<div>Chart</div>")

        generator = DSPyChartGenerator()
        chart_config, chart_html = await generator.generate_chart_async({"data": "test"}, "query")

        assert chart_config == {"type": "column"}
        assert chart_html == "<div>Chart</div>"
        mock_to_thread.assert_called_once()
