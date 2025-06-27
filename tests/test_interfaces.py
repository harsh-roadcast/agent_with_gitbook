"""Tests for the core interfaces and data structures."""
from unittest.mock import Mock, AsyncMock

from core.interfaces import (
    DatabaseType, QueryResult, ProcessedResult,
    IDatabaseSelector, IQueryExecutor, ISummaryGenerator,
    IChartGenerator
)


class TestDatabaseType:
    """Test DatabaseType enum."""

    def test_database_type_values(self):
        """Test that DatabaseType has correct values."""
        assert DatabaseType.VECTOR.value == "Vector"
        assert DatabaseType.ELASTIC.value == "Elastic"


class TestQueryResult:
    """Test QueryResult dataclass."""

    def test_query_result_creation(self):
        """Test QueryResult creation with basic data."""
        data = [{"id": 1, "name": "test"}]
        raw_result = {"hits": {"hits": [{"_source": {"id": 1, "name": "test"}}]}}

        result = QueryResult(
            database_type=DatabaseType.VECTOR,
            data=data,
            raw_result=raw_result
        )

        assert result.database_type == DatabaseType.VECTOR
        assert result.data == data
        assert result.raw_result == raw_result
        assert result.elastic_query is None
        assert result.error is None

    def test_query_result_with_error(self):
        """Test QueryResult with error."""
        result = QueryResult(
            database_type=DatabaseType.ELASTIC,
            data=[],
            raw_result=None,
            error="Connection failed"
        )

        assert result.error == "Connection failed"
        assert result.data == []


class TestProcessedResult:
    """Test ProcessedResult dataclass."""

    def test_processed_result_creation(self):
        """Test ProcessedResult creation."""
        query_result = QueryResult(
            database_type=DatabaseType.VECTOR,
            data=[{"id": 1}],
            raw_result={}
        )

        processed = ProcessedResult(
            query_result=query_result,
            summary="Test summary",
            chart_config={"type": "column"},
            chart_html="<div>Chart</div>"
        )

        assert processed.query_result == query_result
        assert processed.summary == "Test summary"
        assert processed.chart_config == {"type": "column"}
        assert processed.chart_html == "<div>Chart</div>"


class TestInterfaceContracts:
    """Test that interfaces define the expected contracts."""

    def test_database_selector_interface(self):
        """Test IDatabaseSelector interface."""
        selector = Mock(spec=IDatabaseSelector)
        selector.select_database.return_value = DatabaseType.VECTOR

        result = selector.select_database("test query", "schema")
        assert result == DatabaseType.VECTOR
        selector.select_database.assert_called_once_with("test query", "schema", None)

    def test_query_executor_interface(self):
        """Test IQueryExecutor interface."""
        executor = Mock(spec=IQueryExecutor)
        expected_result = QueryResult(
            database_type=DatabaseType.VECTOR,
            data=[],
            raw_result={}
        )
        executor.execute_query.return_value = expected_result

        result = executor.execute_query(
            DatabaseType.VECTOR, "test query", "schema", "instructions"
        )

        assert result == expected_result
        executor.execute_query.assert_called_once_with(
            DatabaseType.VECTOR, "test query", "schema", "instructions"
        )

    def test_summary_generator_interface(self):
        """Test ISummaryGenerator interface."""
        generator = Mock(spec=ISummaryGenerator)
        generator.generate_summary.return_value = "Test summary"
        generator.generate_summary_async = AsyncMock(return_value="Test summary")

        # Test sync method
        result = generator.generate_summary("query", {}, "history")
        assert result == "Test summary"

        # Test async method would need to be run in an event loop
        generator.generate_summary_async.assert_not_called()

    def test_chart_generator_interface(self):
        """Test IChartGenerator interface."""
        generator = Mock(spec=IChartGenerator)
        expected_chart = ({"type": "column"}, "<div>Chart</div>")
        generator.generate_chart.return_value = expected_chart

        result = generator.generate_chart({}, "query")
        assert result == expected_chart
        generator.generate_chart.assert_called_once_with({}, "query")
