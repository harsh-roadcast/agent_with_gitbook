"""Custom exceptions for the DSPy agent system."""


class DSPyAgentException(Exception):
    """Base exception for DSPy agent system."""
    pass


class DatabaseSelectionError(DSPyAgentException):
    """Raised when database selection fails."""
    pass


class QueryExecutionError(DSPyAgentException):
    """Raised when query execution fails."""
    pass


class DataParsingError(DSPyAgentException):
    """Raised when data parsing fails."""
    pass


class SummaryGenerationError(DSPyAgentException):
    """Raised when summary generation fails."""
    pass


class ChartGenerationError(DSPyAgentException):
    """Raised when chart generation fails."""
    pass


class ConfigurationError(DSPyAgentException):
    """Raised when configuration is invalid."""
    pass


class ElasticsearchConnectionError(DSPyAgentException):
    """Raised when Elasticsearch connection fails."""
    pass
