import logging
from typing import Dict, Any, Optional, Tuple, AsyncGenerator

import dspy

# Import new modular components
from core.container import get_query_agent
from core.exceptions import DSPyAgentException
from core.interfaces import IQueryAgent

# Configure logging
logger = logging.getLogger(__name__)


# Modern ActionDecider using clean modular architecture
class ActionDecider(dspy.Module):
    """
    DSPy module that decides which database to query based on the user query,
    processes the query, and returns relevant data including summaries and visualizations.

    This class uses a clean modular architecture with dependency injection for better
    testability, maintainability, and extensibility.
    """

    def __init__(self, query_agent: Optional[IQueryAgent] = None):
        """
        Initialize the ActionDecider with optional dependency injection.

        Args:
            query_agent: Optional query agent instance for dependency injection
        """
        super().__init__()

        # Use dependency injection or fall back to factory
        self._query_agent = query_agent or get_query_agent()

    def forward(self, user_query: str, conversation_history: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a user query and return all results.

        Args:
            user_query: The user's query string
            conversation_history: Optional conversation history for context

        Returns:
            Dictionary with database, data, summary, and visualization information
        """
        try:
            # Use modular architecture
            processed_result = self._query_agent.process_query(user_query, conversation_history)

            # Convert to API response format
            response = {
                "database": processed_result.query_result.database_type.value,
                "data": processed_result.query_result.data
            }

            if processed_result.query_result.error:
                response["error"] = processed_result.query_result.error

            if processed_result.summary:
                response["summary"] = processed_result.summary

            if processed_result.chart_config:
                response["chart_config"] = processed_result.chart_config

            if processed_result.chart_html:
                response["chart_html"] = processed_result.chart_html

            return response

        except DSPyAgentException as e:
            logger.error(f"Error in ActionDecider: {e}", exc_info=True)
            return {"database": "Vector", "action": "default", "error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error in ActionDecider: {e}", exc_info=True)
            return {"database": "Vector", "action": "default", "error": str(e)}

    async def process_async(self, user_query: str, conversation_history: Optional[list] = None,
                         session_id: Optional[str] = None, message_id: Optional[str] = None) -> AsyncGenerator[Tuple[str, Any], None]:
        """
        Asynchronously process a user query and yield results as they become available.

        Args:
            user_query: The user's query string
            conversation_history: Optional conversation history for context
            session_id: Optional session identifier for storing ES queries
            message_id: Optional message identifier for storing ES queries

        Yields:
            Tuples of (field_name, field_value) as results are generated
        """
        try:
            # Convert list to JSON string for compatibility if needed
            history_str = None
            if conversation_history:
                if isinstance(conversation_history, list):
                    import json
                    history_str = json.dumps(conversation_history)
                else:
                    history_str = conversation_history

            # Use modular architecture - directly iterate over the async generator
            async for field_name, field_value in self._query_agent.process_query_async(
                user_query, history_str, session_id=session_id, message_id=message_id
            ):
                yield field_name, field_value

        except Exception as e:
            logger.error(f"Error in ActionDecider async processing: {e}", exc_info=True)
            yield "error", str(e)
