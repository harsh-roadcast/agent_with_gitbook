"""Dependency injection container for the DSPy agent system."""
import logging

from agents.query_agent import QueryAgent
from components.chart_generator import DSPyChartGenerator
from components.database_selector import DSPyDatabaseSelector
from components.query_executor import DSPyQueryExecutor
from components.result_processor import ResultProcessor
from components.summary_generator import DSPySummaryGenerator
from core.config import config_manager
from core.interfaces import (
    IQueryAgent, IDatabaseSelector, IQueryExecutor, IResultProcessor,
    ISummaryGenerator, IChartGenerator
)

logger = logging.getLogger(__name__)


class DIContainer:
    """Dependency injection container for managing component instances."""

    def __init__(self):
        self._instances = {}
        self._config = config_manager.config

    def get_database_selector(self) -> IDatabaseSelector:
        """Get database selector instance."""
        if 'database_selector' not in self._instances:
            self._instances['database_selector'] = DSPyDatabaseSelector()
        return self._instances['database_selector']

    def get_query_executor(self) -> IQueryExecutor:
        """Get query executor instance."""
        if 'query_executor' not in self._instances:
            self._instances['query_executor'] = DSPyQueryExecutor()
        return self._instances['query_executor']

    def get_summary_generator(self) -> ISummaryGenerator:
        """Get summary generator instance."""
        if 'summary_generator' not in self._instances:
            self._instances['summary_generator'] = DSPySummaryGenerator()
        return self._instances['summary_generator']

    def get_chart_generator(self) -> IChartGenerator:
        """Get chart generator instance."""
        if 'chart_generator' not in self._instances:
            self._instances['chart_generator'] = DSPyChartGenerator(
                default_chart_type=self._config.models.default_chart_type
            )
        return self._instances['chart_generator']

    def get_result_processor(self) -> IResultProcessor:
        """Get result processor instance."""
        if 'result_processor' not in self._instances:
            self._instances['result_processor'] = ResultProcessor(
                summary_generator=self.get_summary_generator(),
                chart_generator=self.get_chart_generator()
            )
        return self._instances['result_processor']

    def get_query_agent(self) -> IQueryAgent:
        """Get main query agent instance."""
        if 'query_agent' not in self._instances:
            self._instances['query_agent'] = QueryAgent(
                database_selector=self.get_database_selector(),
                query_executor=self.get_query_executor(),
                result_processor=self.get_result_processor()
            )
        return self._instances['query_agent']

    def clear_cache(self):
        """Clear all cached instances (useful for testing)."""
        self._instances.clear()

    def override_instance(self, key: str, instance: any):
        """Override an instance (useful for testing with mocks)."""
        self._instances[key] = instance


# Global container instance
container = DIContainer()


def get_query_agent() -> IQueryAgent:
    """Factory function to get the main query agent."""
    return container.get_query_agent()
