"""Chat service for handling chat completion business logic."""
import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from agents.agent_config import get_agent_config
from agents.query_agent import QueryAgent
from modules.query_models import QueryRequest
from services.conversation_service import ConversationService
from services.gitbook_service import gitbook_service_manager
from util.stream_handler import StreamResponseHandler

logger = logging.getLogger(__name__)

GITBOOK_MODEL_NAME = "gitbook_rag"
DEFAULT_MODEL_NAME = "general_assistant"
AGENT_HINT = "bolt_data_analyst, synco_agent, police_assistant"


class ChatService:
    """Service for handling chat completion logic."""

    def __init__(self):
        self.conversation_service = ConversationService()

    @staticmethod
    def extract_user_message(messages: List[Dict[str, Any]]) -> Optional[str]:
        """Extract the last user message from messages list."""
        if not messages:
            return None
        for message in reversed(messages):
            if message.get("role") == "user" and message.get("content"):
                return message["content"]
        return None

    @staticmethod
    def resolve_message_id(messages: List[Dict[str, Any]]) -> str:
        """Resolve or generate a message ID."""
        if messages:
            message_id = messages[-1].get("message_id")
            if message_id:
                return message_id
        return f"msg-{uuid.uuid4().hex}"

    @staticmethod
    def build_openai_response(
        session_id: str,
        model: str,
        message_content: Any,
        user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Build an OpenAI-compatible response."""
        timestamp = time.time()
        return {
            "id": f"chatcmpl-{session_id}-{timestamp}",
            "object": "chat.completion",
            "created": int(timestamp),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": message_content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "user_id": user_id
        }

    @staticmethod
    def build_query_request(agent_config, user_message: str, conversation_history: Any) -> QueryRequest:
        """Build a query request for the agent."""
        return QueryRequest(
            user_query=user_message,
            system_prompt=agent_config.system_prompt,
            conversation_history=conversation_history,
            es_schemas=agent_config.es_schemas or [],
            vector_db_index=agent_config.vector_db or "docling_documents",
            query_instructions=agent_config.query_instructions,
            goal=agent_config.goal,
            success_criteria=agent_config.success_criteria,
            dsl_rules=agent_config.dsl_rules
        )

    @staticmethod
    def sanitize_gitbook_limit(options: Optional[Dict[str, Any]]) -> int:
        """Clamp GitBook passage limit to a safe window."""
        if not options:
            return 4
        limit = options.get("limit", 4)
        try:
            limit_value = int(limit)
        except (TypeError, ValueError):
            return 4
        return max(1, min(10, limit_value))

    @staticmethod
    async def run_gitbook_answer(query: str, limit: int):
        """Run GitBook answer generation in executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: gitbook_service_manager.generate_gitbook_answer(query, limit))

    async def stream_gitbook_response(
        self,
        query: str,
        limit: int,
        handler: StreamResponseHandler,
        session_id: str,
        message_id: str
    ):
        """Stream GitBook response."""
        gitbook_response = {"answer": "", "references": []}

        try:
            loop = asyncio.get_running_loop()
            events = await loop.run_in_executor(None, lambda: list(gitbook_service_manager.stream_gitbook_answer(query, limit)))
        except ValueError as exc:
            error_payload = {"type": "error", "content": str(exc), "render_type": "error"}
            yield handler.create_sse_response(error_payload, finish_reason="error")
            yield handler.create_final_response()
            return
        except Exception as exc:
            logger.error("GitBook stream failed: %s", exc, exc_info=True)
            error_payload = {"type": "error", "content": "GitBook chat failed", "render_type": "error"}
            yield handler.create_sse_response(error_payload, finish_reason="error")
            yield handler.create_final_response()
            return

        for event in events:
            event_type = event.get("type")
            if event_type == "answer_chunk":
                chunk = event.get("delta", "")
                if not chunk:
                    continue
                gitbook_response["answer"] += chunk
                payload = {
                    "type": "gitbook_answer_chunk",
                    "content": chunk,
                    "render_type": "text"
                }
                yield handler.create_sse_response(payload)
            elif event_type == "references":
                references = event.get("references", [])
                gitbook_response["references"] = references
                payload = {
                    "type": "gitbook_references",
                    "content": references,
                    "render_type": "references"
                }
                yield handler.create_sse_response(payload)
            elif event_type == "status":
                payload = {
                    "type": "gitbook_status",
                    "content": event.get("message", ""),
                    "render_type": "debug"
                }
                yield handler.create_sse_response(payload)
            elif event_type == "error":
                payload = {
                    "type": "error",
                    "content": event.get("message", "GitBook chat failed"),
                    "render_type": "error"
                }
                yield handler.create_sse_response(payload, finish_reason="error")
                yield handler.create_final_response()
                return

        self.conversation_service.add_assistant_response(session_id, gitbook_response, message_id)
        yield handler.create_final_response()

    async def stream_general_response(
        self,
        query: str,
        model: str,
        handler: StreamResponseHandler,
        session_id: str,
        message_id: str
    ):
        """Stream general agent response."""
        conversation_history = self.conversation_service.get_conversation_history(session_id)

        try:
            agent_config = get_agent_config(model)
        except ValueError as exc:
            logger.error("Agent not found for model '%s': %s", model, exc)
            error_payload = {
                "type": "error",
                "content": {
                    "message": f"Agent '{model}' not found. Available agents: {AGENT_HINT}"
                },
                "render_type": "error"
            }
            yield handler.create_sse_response(error_payload, finish_reason="stop")
            yield handler.create_final_response()
            return

        query_request = self.build_query_request(agent_config, query, conversation_history)
        query_agent = QueryAgent()
        handler.log_timing("Starting async processing")
        full_response: Dict[str, Any] = {}

        try:
            async for msg_type, msg_data in query_agent.process_query_async(
                request=query_request,
                session_id=session_id,
                message_id=message_id
            ):
                if msg_type != "message":
                    continue

                message_type = msg_data.get("type")
                message_content = msg_data.get("content")
                if message_type and message_content and message_type != "debug":
                    full_response[message_type] = message_content

                yield handler.create_sse_response(msg_data)
        except Exception as exc:
            logger.error("Error during stream generation: %s", exc)
            error_payload = {
                "type": "error",
                "content": {
                    "message": f"An error occurred: {str(exc)}"
                },
                "render_type": "error"
            }
            yield handler.create_sse_response(error_payload, finish_reason="error")
            yield handler.create_final_response()
            return

        self.conversation_service.add_assistant_response(session_id, full_response, message_id)
        handler.log_timing("Stream completed")
        yield handler.create_final_response()

    async def generate_stream(
        self,
        query: str,
        session_id: str,
        user_info: Dict[str, Any],
        model: str = DEFAULT_MODEL_NAME,
        message_id: Optional[str] = None,
        gitbook_options: Optional[Dict[str, Any]] = None
    ):
        """Generate streaming response."""
        handler = StreamResponseHandler(session_id, user_info.get("user_id", "anonymous_user"), model)
        handler.log_timing("Starting stream generation")

        if not message_id:
            yield handler.create_final_response()
            return

        if model == GITBOOK_MODEL_NAME:
            limit = self.sanitize_gitbook_limit(gitbook_options)
            async for chunk in self.stream_gitbook_response(query, limit, handler, session_id, message_id):
                yield chunk
            return

        async for chunk in self.stream_general_response(query, model, handler, session_id, message_id):
            yield chunk

    async def handle_non_streaming_gitbook(
        self,
        user_message: str,
        session_id: str,
        user_id: Optional[str],
        model: str,
        message_id: str,
        gitbook_options: Optional[Dict[str, Any]] = None
    ):
        """Handle non-streaming GitBook request."""
        limit = self.sanitize_gitbook_limit(gitbook_options)
        result = await self.run_gitbook_answer(user_message, limit)
        self.conversation_service.add_assistant_response(session_id, result, message_id)
        return self.build_openai_response(session_id, model, result, user_id)

    async def handle_non_streaming_general(
        self,
        user_message: str,
        session_id: str,
        user_id: Optional[str],
        model: str,
        message_id: str
    ):
        """Handle non-streaming general agent request."""
        conversation_history = self.conversation_service.get_conversation_history(session_id)
        agent_config = get_agent_config(model)
        query_request = self.build_query_request(agent_config, user_message, conversation_history)
        query_agent = QueryAgent()
        result_dict: Dict[str, Any] = {}

        async for msg_type, msg_data in query_agent.process_query_async(
            request=query_request,
            session_id=session_id,
            message_id=message_id
        ):
            if msg_type != "message":
                continue

            message_type = msg_data.get("type")
            message_content = msg_data.get("content")
            if message_type and message_content:
                result_dict[message_type] = message_content

        self.conversation_service.add_assistant_response(session_id, result_dict, message_id)
        return self.build_openai_response(session_id, model, result_dict, user_id)

chat_service_manager = ChatService()