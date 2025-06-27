"""Core interfaces for the DSPy agent system."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, AsyncGenerator, Tuple


class DatabaseType(Enum):
    """Enumeration for database types."""
    VECTOR = "Vector"
    ELASTIC = "Elastic"


@dataclass
class QueryResult:
    """Standardized query result structure."""
    database_type: DatabaseType
    data: List[Dict[str, Any]]
    raw_result: Any
    elastic_query: Optional[Dict] = None
    error: Optional[str] = None


@dataclass
class ProcessedResult:
    """Complete processed result with all components."""
    query_result: QueryResult
    summary: Optional[str] = None
    chart_config: Optional[Dict] = None
    chart_html: Optional[str] = None


class IDatabaseSelector(ABC):
    """Interface for database selection logic."""

    @abstractmethod
    def select_database(self, user_query: str, schema: str, conversation_history: Optional[List[Dict]] = None) -> DatabaseType:
        """Select appropriate database based on query and schema."""
        pass


class IQueryExecutor(ABC):
    """Interface for query execution."""

    @abstractmethod
    def execute_query(self, database_type: DatabaseType, user_query: str, schema: str, instructions: str, conversation_history: Optional[List[Dict]] = None) -> QueryResult:
        """Execute query on specified database."""
        pass


class ISummaryGenerator(ABC):
    """Interface for summary generation."""

    @abstractmethod
    def generate_summary(self, user_query: str, data: Dict, conversation_history: Optional[str] = None) -> Optional[str]:
        """Generate summary from query results."""
        pass

    @abstractmethod
    async def generate_summary_async(self, user_query: str, data: Dict, conversation_history: Optional[str] = None) -> Optional[str]:
        """Generate summary asynchronously."""
        pass


class IChartGenerator(ABC):
    """Interface for chart generation."""

    @abstractmethod
    def generate_chart(self, data: Dict, user_query: str, conversation_history: Optional[List[Dict]] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """Generate chart configuration and HTML."""
        pass

    @abstractmethod
    async def generate_chart_async(self, data: Dict, user_query: str, conversation_history: Optional[List[Dict]] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """Generate chart asynchronously."""
        pass


class IResultProcessor(ABC):
    """Interface for result processing."""

    @abstractmethod
    def process_results(self, query_result: QueryResult, user_query: str, conversation_history: Optional[str] = None) -> ProcessedResult:
        """Process query results into final format."""
        pass

    @abstractmethod
    def process_results_async(self, query_result: QueryResult, user_query: str, conversation_history: Optional[str] = None) -> AsyncGenerator[Tuple[str, Any], None]:
        """Process results asynchronously, yielding intermediate results."""
        pass


class IQueryAgent(ABC):
    """Main interface for the query agent."""

    @abstractmethod
    def process_query(self, user_query: str, conversation_history: Optional[str] = None) -> ProcessedResult:
        """Process a user query and return complete results."""
        pass

    @abstractmethod
    async def process_query_async(self, user_query: str, conversation_history: Optional[str] = None) -> AsyncGenerator[Tuple[str, Any], None]:
        """Process query asynchronously, yielding results as they become available."""
        pass
