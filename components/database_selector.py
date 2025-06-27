"""Database selection implementation using DSPy."""
import logging
from typing import Optional, List, Dict

import dspy

from core.exceptions import DatabaseSelectionError
from core.interfaces import IDatabaseSelector, DatabaseType
from modules.signatures import DatabaseSelectionSignature
from util.performance import monitor_performance

logger = logging.getLogger(__name__)


class DSPyDatabaseSelector(IDatabaseSelector):
    """DSPy-based database selector implementation."""

    def __init__(self):
        """Initialize the database selector with DSPy predictor."""
        self.predictor = dspy.Predict(DatabaseSelectionSignature)

    @monitor_performance("database_selection")
    def select_database(self, user_query: str, schema: str, conversation_history: Optional[List[Dict]] = None) -> DatabaseType:
        """
        Select the appropriate database based on the user query and schema.

        Args:
            user_query: The user's query string
            schema: The database schema information
            conversation_history: Optional conversation history for context

        Returns:
            DatabaseType enum value

        Raises:
            DatabaseSelectionError: If selection fails
        """
        try:
            result = self.predictor(
                user_query=user_query,
                es_schema=schema,
                conversation_history=conversation_history
            )

            database_str = result.database
            logger.info(f"Selected database: {database_str}")

            # Convert string to enum
            try:
                return DatabaseType(database_str)
            except ValueError:
                logger.warning(f"Unknown database type: {database_str}, defaulting to VECTOR")
                return DatabaseType.VECTOR

        except Exception as e:
            logger.error(f"Error selecting database: {e}", exc_info=True)
            raise DatabaseSelectionError(f"Failed to select database: {e}") from e
