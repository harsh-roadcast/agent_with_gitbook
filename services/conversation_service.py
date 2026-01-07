"""Conversation history management service with Redis support."""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

from util.redis_client import redis_client, store_message_query

logger = logging.getLogger(__name__)


class ConversationService:
    """Service to manage conversation history and context with Redis backend."""

    def __init__(self):
        self._max_history_length = 10
        self._session_timeout = timedelta(hours=2)
        self._redis_prefix = "conversation:"
        self._redis_enabled = redis_client is not None
        self._in_memory_store: Dict[str, Dict[str, Any]] = {}
        backend = "Redis" if self._redis_enabled else "in-memory fallback"
        logger.info(f"ConversationService initialized using {backend} backend")

    def _get_store_key(self, session_id: str) -> str:
        return f"{self._redis_prefix}{session_id}"

    def _get_conversation_data(self, session_id: str) -> Dict[str, Any]:
        if self._redis_enabled:
            redis_key = self._get_store_key(session_id)
            return redis_client.hgetall(redis_key)
        return self._in_memory_store.get(session_id, {}).copy()

    def _persist_conversation_data(self, session_id: str, data: Dict[str, Any]) -> None:
        if self._redis_enabled:
            redis_key = self._get_store_key(session_id)
            redis_client.hset(redis_key, mapping=data)
            redis_client.expire(redis_key, int(self._session_timeout.total_seconds()))
        else:
            self._in_memory_store[session_id] = data.copy()

    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        conversation_data = self._get_conversation_data(session_id)

        if not conversation_data:
            return []

        # Check if session has expired
        last_activity_str = conversation_data.get('last_activity')
        if last_activity_str:
            last_activity = datetime.fromisoformat(last_activity_str)
            if datetime.now() - last_activity > self._session_timeout:
                self.clear_conversation(session_id)
                return []

        # Get messages
        messages = conversation_data.get('messages', [])
        if isinstance(messages, str):
            messages = json.loads(messages)

        return messages if isinstance(messages, list) else []

    def add_user_message(self, session_id: str, message: str, message_id: str) -> str:
        """Add a user message to conversation history."""
        conversation_data = self._get_conversation_data(session_id)

        if not conversation_data:
            messages = []
            created_at = datetime.now().isoformat()
        else:
            messages = conversation_data.get('messages', [])
            if isinstance(messages, str):
                messages = json.loads(messages)
            if not isinstance(messages, list):
                messages = []
            created_at = conversation_data.get('created_at', datetime.now().isoformat())

        # Add new user message
        message_data = {
            'role': 'user',
            'content': message,
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
        self._persist_conversation_data(session_id, update_data)

        logger.debug(f"Added user message to conversation {session_id} with message_id {message_id}")
        return message_id

    def add_assistant_response(self, session_id: str, response: Any, message_id: str,
                              es_query: Dict = None, user_message_id: str = None) -> str:
        """Add an assistant response to conversation history with filtered data."""
        conversation_data = self._get_conversation_data(session_id)

        if not conversation_data:
            messages = []
            created_at = datetime.now().isoformat()
        else:
            messages = conversation_data.get('messages', [])
            if isinstance(messages, str):
                messages = json.loads(messages)
            if not isinstance(messages, list):
                messages = []
            created_at = conversation_data.get('created_at', datetime.now().isoformat())

        # Filter response to only include essential fields
        filtered_content = {}

        if isinstance(response, dict):
            # Only save specific fields, NOT the actual query results
            essential_fields = {
                'detailed_analysis': response.get('detailed_analysis'),
                'user_query': response.get('user_query'),
                'elastic_query': response.get('elastic_query'),
                'elastic_index': response.get('elastic_index'),
                'vector_query': response.get('vector_query'),
                'summary': response.get('summary')
            }

            # Only include fields that have values
            filtered_content = {k: v for k, v in essential_fields.items() if v is not None}
        else:
            # If response is not a dict, just store the summary text
            filtered_content = {'summary': str(response)}

        message_data = {
            'role': 'assistant',
            'content': filtered_content,
            'message_id': message_id,
            'timestamp': datetime.now().isoformat()
        }

        if user_message_id:
            message_data['user_message_id'] = user_message_id

        messages.append(message_data)
        messages = self._trim_messages(messages)

        # Update Redis
        update_data = {
            'messages': json.dumps(messages),
            'created_at': created_at,
            'last_activity': datetime.now().isoformat()
        }
        self._persist_conversation_data(session_id, update_data)

        # Store ES query if provided (separate from conversation history)
        if es_query and user_message_id:
            index_name = "unknown"
            if isinstance(es_query, dict):
                if 'index' in es_query:
                    index_name = es_query['index']
                elif 'index_name' in es_query:
                    index_name = es_query['index_name']
                else:
                    index_name = "vehicle_summary_llm_chatbot"

            store_message_query(session_id, user_message_id, es_query, index_name)

        logger.debug(f"Added filtered assistant response to conversation {session_id} with message_id {message_id}")
        return message_id

    def clear_conversation(self, session_id: str) -> bool:
        """Clear conversation history for a session."""
        if self._redis_enabled:
            redis_key = self._get_store_key(session_id)
            deleted = redis_client.delete(redis_key)
            logger.info(f"Cleared conversation for session {session_id}")
            return deleted > 0
        removed = self._in_memory_store.pop(session_id, None) is not None
        if removed:
            logger.info(f"Cleared in-memory conversation for session {session_id}")
        return removed

    def get_recent_context(self, session_id: str, max_exchanges: int = 3) -> str:
        """Get recent conversation context as formatted string."""
        messages = self.get_conversation_history(session_id)

        if not messages:
            return ""

        # Get the last max_exchanges pairs of user/assistant messages
        context_messages = messages[-(max_exchanges * 2):]

        context_parts = []
        for msg in context_messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if role == 'user':
                context_parts.append(f"User: {content}")
            elif role == 'assistant':
                context_parts.append(f"Assistant: {content}")

        return "\n".join(context_parts)

    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a conversation session."""
        messages = self.get_conversation_history(session_id)

        if not messages:
            return {
                'total_messages': 0,
                'user_messages': 0,
                'assistant_messages': 0,
                'created_at': None,
                'last_activity': None
            }

        user_count = sum(1 for msg in messages if msg.get('role') == 'user')
        assistant_count = sum(1 for msg in messages if msg.get('role') == 'assistant')

        redis_key = f"{self._redis_prefix}{session_id}"
        conversation_data = redis_client.hgetall(redis_key)

        return {
            'total_messages': len(messages),
            'user_messages': user_count,
            'assistant_messages': assistant_count,
            'created_at': conversation_data.get('created_at'),
            'last_activity': conversation_data.get('last_activity')
        }

    def _trim_messages(self, messages: List[Dict]) -> List[Dict]:
        """Trim messages to maximum history length."""
        if len(messages) > self._max_history_length:
            return messages[-self._max_history_length:]
        return messages


# Global conversation service instance
conversation_service = ConversationService()
