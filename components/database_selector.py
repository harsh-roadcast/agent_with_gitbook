"""Simple database selector - now obsolete with new workflow."""
import logging
from typing import Optional, List, Dict

from core.exceptions import DatabaseSelectionError
from core.interfaces import IDatabaseSelector, DatabaseType
from util.performance import monitor_performance

logger = logging.getLogger(__name__)


class DSPyDatabaseSelector(IDatabaseSelector):
    """Simple database selector - functionality moved to QueryWorkflowPlanner."""

    def __init__(self):
        """Initialize the database selector."""
        pass

    @monitor_performance("database_selection")
    def select_database(self, user_query: str, schema: str, conversation_history: Optional[List[Dict]] = None) -> DatabaseType:
        """
        Simple fallback database selection - defaults to ELASTIC.
        Real logic is now in QueryWorkflowPlanner.
        """
        logger.info("Using fallback database selection - defaulting to ELASTIC")
        return DatabaseType.ELASTIC
