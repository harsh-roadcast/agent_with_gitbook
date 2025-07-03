"""Chat completion API routes - OpenAI compatible endpoints."""
import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from services.auth_service import get_current_user
from services.conversation_service import ConversationService
from agents.query_agent import QueryAgent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Initialize conversation service
conversation_service = ConversationService()


class StreamResponseHandler:
    """Handles SSE streaming responses with timing and formatting."""

    def __init__(self, session_id: str, user_id: str, model: str):
        self.session_id = session_id
        self.user_id = user_id
        self.model = model
        self.stream_start = time.time()
        self.response_data = {}

    def log_timing(self, event: str, field: str = None):
        """Log timing information for debugging."""
        current_time = time.time()
        elapsed = (current_time - self.stream_start) * 1000
        if field:
            logger.info(f"📦 [TIMING] {event} '{field}' at {elapsed:.2f}ms from start")
        else:
            logger.info(f"🚀 [TIMING] {event} at {elapsed:.2f}ms from start")

    def should_skip_field(self, field: str) -> bool:
        """Check if field should be skipped from frontend."""
        skip_fields = []  # Can add fields to skip here if needed
        return field in skip_fields

    def is_priority_field(self, field: str) -> bool:
        """Check if field should be sent immediately (ES data)."""
        return field in ["data", "data_markdown"]

    def is_error_field(self, field: str, value: Any) -> bool:
        """Check if this is a critical error that should stop processing."""
        if field != "error":
            return False

        error_msg = str(value).lower()
        critical_errors = [
            "cannot proceed",
            "elasticsearch query returned 0 results",
            "vector search returned 0 results",
            "invalid or missing elasticsearch query",
            "invalid or missing vector search query",
            "failed to generate embedding"
        ]
        return any(phrase in error_msg for phrase in critical_errors)

    def format_content(self, field: str, value: Any) -> str:
        """Format field content for frontend display."""
        if field == "data":
            return None  # Skip raw data, only send markdown
        elif field == "data_markdown":
            return f"{value}\n\n"
        elif field == "elastic_query":
            return f"**Elasticsearch Query:**\n{value}\n\n\n"
        elif field == "summary":
            return f"**Summary:**\n{value}\n\n\n"
        elif field == "chart_config":
            return f"{json.dumps(value)}\n\n"
        elif field == "error":
            return f"**Error:**\n{value}\n\n\n"
        elif field == "database":
            return f"**Database Selected:**\n{value}\n\n\n"
        elif field == "completed":
            return None  # Skip completed status
        else:
            return f"**{field.capitalize()}:**\n{str(value)}\n\n\n"

    def create_sse_response(self, content: str, field: str, finish_reason: Optional[str] = None) -> str:
        """Create SSE response chunk."""
        response = {
            "id": f"chatcmpl-{self.session_id}-{time.time()}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": content,
                    "field": field,
                },
                "finish_reason": finish_reason
            }],
            "user_id": self.user_id
        }
        return f"event: delta\ndata: {json.dumps(response)}\n\n"

    def create_final_response(self) -> str:
        """Create final [DONE] response."""
        response = {
            "id": f"chatcmpl-{self.session_id}-{time.time()}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {"content": ""},
                "finish_reason": "stop"
            }],
            "user_id": self.user_id
        }
        return f"data: {json.dumps(response)}\n\ndata: [DONE]\n\n"


async def generate_stream(query: str, session_id: str, user_info: Dict[str, Any], model="LLM_TEXT_SQL", message_id: Optional[str] = None):
    """Generate streaming response with user context - simplified and focused."""

    # Initialize handler and validate inputs
    handler = StreamResponseHandler(session_id, user_info.get('user_id', 'anonymous_user'), model)
    handler.log_timing("Starting stream generation")

    if not message_id:
        yield "data: [DONE]\n\n"
        return

    # Setup conversation context
    conversation_service.add_user_message(session_id, query, message_id)
    conversation_history = conversation_service.get_conversation_history(session_id)

    # Process query asynchronously - Initialize query agent (no parameters needed)
    query_agent = QueryAgent()
    assistant_response_stored = False

    handler.log_timing("Starting async processing")

    async for field, value in query_agent.process_query_async(
        user_query=query,
        conversation_history=conversation_history,
        session_id=session_id,
        message_id=message_id
    ):
        handler.log_timing("Received field", field)
        handler.response_data[field] = value

        # Skip fields that shouldn't be sent to frontend
        if handler.should_skip_field(field):
            continue

        # Handle critical errors immediately
        if handler.is_error_field(field, value):
            yield handle_critical_error(handler, field, value, session_id, message_id)
            return

        # Format and send field to frontend
        content = handler.format_content(field, value)
        if content is not None:
            sse_response = handler.create_sse_response(content, field)
            yield sse_response

            # Add timing logs for important fields
            if handler.is_priority_field(field):
                handler.log_timing(f"ES data sent for {field}")
            elif field == "summary":
                handler.log_timing("Summary sent")

            # Small delay for SSE processing
            sleep_time = 0.5 if handler.is_priority_field(field) else 0.1
            await asyncio.sleep(sleep_time)

    # Store complete response and send final chunk
    if not assistant_response_stored:
        conversation_service.add_assistant_response(session_id, handler.response_data, message_id)
        logger.info(f"Stored complete assistant response for session {session_id}")

    handler.log_timing("Stream completed")
    yield handler.create_final_response()


async def handle_critical_error(handler: StreamResponseHandler, field: str, value: Any, session_id: str, message_id: str):
    """Handle critical errors that should stop processing."""
    # Store error response
    conversation_service.add_assistant_response(session_id, handler.response_data, message_id)
    logger.info(f"Stored assistant response with error for session {session_id}")

    # Send error to frontend
    content = handler.format_content(field, value)
    error_response = handler.create_sse_response(content, field, finish_reason="stop")
    yield error_response
    yield "data: [DONE]\n\n"


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, user_info: Dict[str, Any] = Depends(get_current_user)):
    """OpenAI-compatible chat completion endpoint for streaming and non-streaming."""
    data = await request.json()
    messages = data.get("messages", [])

    user_message = next((msg["content"] for msg in reversed(messages)
                         if msg.get("role") == "user"), None)

    message_id = messages[-1]['message_id']
    stream = data.get("stream", False)
    session_id = data.get("session_id", "default")
    model = data.get("model", "default")
    user_id = user_info.get('user_id')

    logger.info(f"Chat completion request from user {user_id}: stream={stream}, session={session_id}")

    if stream:
        return EventSourceResponse(generate_stream(user_message, session_id, user_info, model=model, message_id=message_id))
    else:
        return await handle_non_streaming_request(user_message, session_id, user_id, model, message_id)


async def handle_non_streaming_request(user_message: str, session_id: str, user_id: str, model: str, message_id: str):
    """Handle non-streaming chat completion requests."""
    conversation_service.add_user_message(session_id, user_message, message_id)
    conversation_history = conversation_service.get_conversation_history(session_id)

    # Initialize query agent (no parameters needed)
    query_agent = QueryAgent()
    result_dict = {}

    async for field, value in query_agent.process_query_async(
        user_query=user_message,
        conversation_history=conversation_history,
        session_id=session_id,
        message_id=message_id
    ):
        if field not in ["database", "chart_html"]:
            result_dict[field] = value

    conversation_service.add_assistant_response(session_id, result_dict, message_id)

    response = {
        "id": f"chatcmpl-{session_id}-{time.time()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": result_dict
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
    return JSONResponse(content=response)
