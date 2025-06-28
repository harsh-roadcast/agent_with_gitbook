"""Conversation history management service with Redis support."""
import json
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from util.redis_client import get_redis_client, is_redis_available, store_message_query, get_message_query

logger = logging.getLogger(__name__)


class ConversationService:
    """Service to manage conversation history and context with Redis backend."""

    def __init__(self):
        # Try to use Redis, fall back to in-memory if not available
        self.redis_client = get_redis_client()
        self.use_redis = is_redis_available()

        if self.use_redis:
            logger.info("ConversationService initialized with Redis backend")
        else:
            logger.warning("ConversationService falling back to in-memory storage")
            # Fallback to in-memory storage
            self._conversations: Dict[str, Dict] = {}

        self._max_history_length = 10  # Maximum number of exchanges to keep
        self._session_timeout = timedelta(hours=2)  # Session timeout
        self._redis_prefix = "conversation:"  # Redis key prefix

    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        if self.use_redis:
            return self._get_conversation_history_redis(session_id)
        else:
            return self._get_conversation_history_memory(session_id)

    def _get_conversation_history_redis(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history from Redis."""
        redis_key = f"{self._redis_prefix}{session_id}"

        try:
            # Get conversation data from Redis
            conversation_data = self.redis_client.hgetall(redis_key)

            if not conversation_data:
                return []

            # Check if session has expired
            last_activity_str = conversation_data.get('last_activity')
            if last_activity_str:
                last_activity = datetime.fromisoformat(last_activity_str)
                if self._is_session_expired_time(last_activity):
                    self.clear_conversation(session_id)
                    return []

            # Get messages
            messages = conversation_data.get('messages', [])
            if isinstance(messages, str):
                messages = json.loads(messages)

            return messages if isinstance(messages, list) else []

        except Exception as e:
            logger.error(f"Error getting conversation history from Redis for {session_id}: {e}")
            return []

    def _get_conversation_history_memory(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history from in-memory storage."""
        if session_id not in self._conversations:
            return []

        conversation = self._conversations[session_id]

        # Check if session has expired
        if self._is_session_expired(conversation):
            self.clear_conversation(session_id)
            return []

        return conversation.get('messages', [])

    def add_user_message(self, session_id: str, message: str, message_id: str) -> str:
        """
        Add a user message to conversation history.

        Args:
            session_id: Chat session identifier
            message: User message content
            message_id: Message ID from frontend (required)

        Returns:
            The message ID
        """
        if not message_id:
            raise ValueError("message_id is required and must be provided by the frontend")

        if self.use_redis:
            self._add_user_message_redis(session_id, message, message_id)
        else:
            self._add_user_message_memory(session_id, message, message_id)

        return message_id

    def _add_user_message_redis(self, session_id: str, message: str, message_id: str) -> None:
        """Add user message to Redis."""
        redis_key = f"{self._redis_prefix}{session_id}"

        try:
            # Get existing conversation or create new
            conversation_data = self.redis_client.hgetall(redis_key)

            if not conversation_data:
                # Create new conversation
                messages = []
                created_at = datetime.now().isoformat()
            else:
                # Get existing messages
                messages = conversation_data.get('messages', [])
                if isinstance(messages, str):
                    messages = json.loads(messages)
                if not isinstance(messages, list):
                    messages = []
                created_at = conversation_data.get('created_at', datetime.now().isoformat())

            # Add new user message with message_id
            message_data = {
                'role': 'user',
                'content': message,
                'message_id': message_id,
                'timestamp': datetime.now().isoformat()
            }
            messages.append(message_data)

            # Trim conversation history
            messages = self._trim_messages(messages)

            # Update Redis with new data
            update_data = {
                'messages': json.dumps(messages),
                'created_at': created_at,
                'last_activity': datetime.now().isoformat()
            }

            # Use mapping parameter to set multiple fields at once
            self.redis_client.hset(redis_key, mapping=update_data)

            # Set expiration on the key (session timeout)
            self.redis_client.expire(redis_key, int(self._session_timeout.total_seconds()))

            logger.debug(f"Added user message to Redis conversation {session_id} with message_id {message_id}")

        except Exception as e:
            logger.error(f"Error adding user message to Redis for {session_id}: {e}")

    def _add_user_message_memory(self, session_id: str, message: str, message_id: str) -> None:
        """Add user message to in-memory storage."""
        self._ensure_conversation_exists(session_id)

        message_data = {
            'role': 'user',
            'content': message,
            'message_id': message_id,
            'timestamp': datetime.now().isoformat()
        }

        self._conversations[session_id]['messages'].append(message_data)
        self._conversations[session_id]['last_activity'] = datetime.now()
        self._trim_conversation_history(session_id)

    def add_assistant_response(self, session_id: str, response: str, message_id: Optional[str] = None,
                              es_query: Optional[Dict] = None, user_message_id: Optional[str] = None) -> str:
        """
        Add an assistant response to conversation history.

        Args:
            session_id: Chat session identifier
            response: Assistant response content
            message_id: Optional response message ID, generates one if not provided
            es_query: Optional Elasticsearch query that generated this response
            user_message_id: Optional ID of the user message this responds to

        Returns:
            The response message ID (generated or provided)
        """

        if self.use_redis:
            self._add_assistant_response_redis(session_id, response, message_id, es_query, user_message_id)
        else:
            self._add_assistant_response_memory(session_id, response, message_id, es_query, user_message_id)

        # Store ES query in Redis if provided and user_message_id is available
        if es_query and user_message_id:
            store_message_query(session_id, user_message_id, es_query)
            logger.info(f"Stored ES query for session {session_id}, message {user_message_id}")

        return message_id

    def _add_assistant_response_redis(self, session_id: str, response: str, message_id: str,
                                    es_query: Optional[Dict], user_message_id: Optional[str]) -> None:
        """Add assistant response to Redis."""
        redis_key = f"{self._redis_prefix}{session_id}"

        # Only store elastic query and database name, nothing else
        filtered_response = {}

        # Check if es_query exists before accessing its contents
        if es_query is not None:
            if 'elastic_query' in es_query:
                filtered_response['elastic_query'] = es_query['elastic_query']

            if 'database' in es_query:
                filtered_response['database'] = es_query['database']

        # Only add to history if we have something relevant to store
        if not filtered_response:
            return

        try:
            # Get existing conversation
            conversation_data = self.redis_client.hgetall(redis_key)

            if not conversation_data:
                # Create new conversation if it doesn't exist
                messages = []
                created_at = datetime.now().isoformat()
            else:
                # Get existing messages
                messages = conversation_data.get('messages', [])
                if isinstance(messages, str):
                    messages = json.loads(messages)
                if not isinstance(messages, list):
                    messages = []
                created_at = conversation_data.get('created_at', datetime.now().isoformat())

            # Create assistant message
            summary_content = self._create_minimal_response_summary(filtered_response)
            message_data = {
                'role': 'assistant',
                'content': summary_content,
                'query_info': filtered_response,  # Store only elastic_query and database
                'message_id': message_id,
                'timestamp': datetime.now().isoformat()
            }

            messages.append(message_data)

            # Trim conversation history
            messages = self._trim_messages(messages)

            # Update Redis
            update_data = {
                'messages': json.dumps(messages),
                'created_at': created_at,
                'last_activity': datetime.now().isoformat()
            }

            # Use mapping parameter to set multiple fields at once
            self.redis_client.hset(redis_key, mapping=update_data)

            # Set expiration on the key
            self.redis_client.expire(redis_key, int(self._session_timeout.total_seconds()))

            logger.debug(f"Added assistant response to Redis conversation {session_id} with message_id {message_id}")

        except Exception as e:
            logger.error(f"Error adding assistant response to Redis for {session_id}: {e}")

    def _add_assistant_response_memory(self, session_id: str, response: str, message_id: str,
                                      es_query: Optional[Dict], user_message_id: Optional[str]) -> None:
        """Add assistant response to in-memory storage."""
        self._ensure_conversation_exists(session_id)

        # Only store elastic query and database name, nothing else
        filtered_response = {}

        # Check if es_query exists before accessing its contents
        if es_query is not None:
            if 'elastic_query' in es_query:
                filtered_response['elastic_query'] = es_query['elastic_query']

            if 'database' in es_query:
                filtered_response['database'] = es_query['database']

        # Only add to history if we have something relevant to store
        if filtered_response:
            # Create a summary of just the essential query information
            summary_content = self._create_minimal_response_summary(filtered_response)

            message_data = {
                'role': 'assistant',
                'content': summary_content,
                'query_info': filtered_response,  # Store only elastic_query and database
                'message_id': message_id,
                'timestamp': datetime.now().isoformat()
            }

            self._conversations[session_id]['messages'].append(message_data)
            self._conversations[session_id]['last_activity'] = datetime.now()
            self._trim_conversation_history(session_id)

    def get_context_for_query(self, session_id: str) -> str:
        """Get formatted context string for the current query (only user queries and database info)."""
        history = self.get_conversation_history(session_id)

        if not history:
            return ""

        # Format conversation history for LLM context - only user queries and database selections
        context_parts = []
        for msg in history[-6:]:  # Use last 6 messages for context
            role = msg['role']
            if role == 'user':
                content = msg['content']
                context_parts.append(f"User: {content}")
            elif role == 'assistant' and 'query_info' in msg:
                # Only mention database and query existence, not full details
                query_info = msg['query_info']
                database = query_info.get('database', 'Unknown')
                has_query = 'elastic_query' in query_info
                summary = f"Assistant: Used {database} database"
                if has_query:
                    summary += " with Elasticsearch query"
                context_parts.append(summary)

        return "\n".join(context_parts)

    def clear_conversation(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        if self.use_redis:
            self._clear_conversation_redis(session_id)
        else:
            self._clear_conversation_memory(session_id)

    def _clear_conversation_redis(self, session_id: str) -> None:
        """Clear conversation from Redis."""
        redis_key = f"{self._redis_prefix}{session_id}"
        try:
            self.redis_client.delete(redis_key)
            logger.debug(f"Cleared Redis conversation {session_id}")
        except Exception as e:
            logger.error(f"Error clearing Redis conversation {session_id}: {e}")

    def _clear_conversation_memory(self, session_id: str) -> None:
        """Clear conversation from in-memory storage."""
        if session_id in self._conversations:
            del self._conversations[session_id]

    def get_recent_data_context(self, session_id: str) -> Optional[Dict]:
        """Get recent query context (only database and query info)."""
        history = self.get_conversation_history(session_id)

        # Look for recent query info in assistant responses
        for msg in reversed(history[-3:]):  # Check last 3 messages
            if msg['role'] == 'assistant' and 'query_info' in msg:
                return msg['query_info']  # Only contains elastic_query and database

        return None

    def _trim_messages(self, messages: List[Dict]) -> List[Dict]:
        """Trim messages list to maximum length."""
        max_messages = self._max_history_length * 2  # user + assistant = 2 messages per exchange
        if len(messages) > max_messages:
            return messages[-max_messages:]
        return messages

    def _ensure_conversation_exists(self, session_id: str) -> None:
        """Ensure conversation exists for session (in-memory only)."""
        if session_id not in self._conversations:
            self._conversations[session_id] = {
                'messages': [],
                'created_at': datetime.now(),
                'last_activity': datetime.now()
            }

    def _trim_conversation_history(self, session_id: str) -> None:
        """Trim conversation history to maximum length (in-memory only)."""
        if session_id in self._conversations:
            messages = self._conversations[session_id]['messages']
            if len(messages) > self._max_history_length * 2:  # user + assistant = 2 messages per exchange
                # Keep the most recent exchanges
                self._conversations[session_id]['messages'] = messages[-(self._max_history_length * 2):]

    def _is_session_expired(self, conversation: Dict) -> bool:
        """Check if session has expired (in-memory only)."""
        last_activity = conversation.get('last_activity', datetime.now())
        return datetime.now() - last_activity > self._session_timeout

    def _is_session_expired_time(self, last_activity: datetime) -> bool:
        """Check if session has expired based on last activity time."""
        return datetime.now() - last_activity > self._session_timeout

    def _create_minimal_response_summary(self, query_info: Dict[str, Any]) -> str:
        """Create a minimal summary with only database and query info."""
        summary_parts = []

        if 'database' in query_info:
            summary_parts.append(f"Database: {query_info['database']}")

        if 'elastic_query' in query_info:
            summary_parts.append("Executed Elasticsearch query")

        return "; ".join(summary_parts) if summary_parts else "Processed query"


# Global instance
conversation_service = ConversationService()
