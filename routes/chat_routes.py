"""Chat completion API routes - OpenAI compatible endpoints."""
import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
import uuid

from services.auth_service import get_current_user
from services.conversation_service import ConversationService
from agents.query_agent import QueryAgent
from agents.agent_config import get_agent_config
from modules.query_models import QueryRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Initialize conversation service
conversation_service = ConversationService()


class StreamResponseHandler:
    """Handles SSE streaming responses with consistent format for frontend."""

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

    def create_sse_response(self, content: Any, finish_reason: Optional[str] = None) -> str:
        """Create SSE response chunk in simple, flat format for frontend."""
        response = {
            "id": f"chunk-{time.time()}",
            "message": content,
            "render_type": content.get("render_type", 'text'),
            "timestamp": time.time(),
            "finish_reason": finish_reason
        }
        return f"{json.dumps(response)}\n\n"

    def create_final_response(self) -> str:
        """Create final [DONE] response."""
        # Simple format for the final response to match other messages
        return "[DONE]\n\n"


async def generate_stream(query: str, session_id: str, user_info: Dict[str, Any], model="LLM_TEXT_SQL", message_id: Optional[str] = None):
    """Generate streaming response with user context - simplified for standardized query_agent format."""

    # Initialize handler and validate inputs
    handler = StreamResponseHandler(session_id, user_info.get('user_id', 'anonymous_user'), model)
    handler.log_timing("Starting stream generation")

    if not message_id:
        yield "[DONE]\n\n"
        return

    # Setup conversation context
    conversation_service.add_user_message(session_id, query, message_id)
    conversation_history = conversation_service.get_conversation_history(session_id)

    # Get agent configuration based on model name
    try:
        agent_config = get_agent_config(model)
    except ValueError as e:
        logger.error(f"Agent not found for model '{model}': {e}")
        error_payload = {
            "type": "error",
            "content": {
                "message": f"Agent '{model}' not found. Available agents: bolt_data_analyst, synco_agent, police_assistant"
            },
            "render_type": "error"
        }
        yield handler.create_sse_response(error_payload, finish_reason="stop")
        yield handler.create_final_response()
        return

    # Create QueryRequest with agent configuration
    query_request = QueryRequest(
        user_query=query,
        system_prompt=agent_config.system_prompt,
        conversation_history=conversation_history,
        es_schemas=agent_config.es_schemas or [],
        vector_db_index=agent_config.vector_db or "docling_documents",
        query_instructions=agent_config.query_instructions,
        goal=agent_config.goal,
        success_criteria=agent_config.success_criteria,
        dsl_rules=agent_config.dsl_rules
    )

    # Process query asynchronously
    query_agent = QueryAgent()
    handler.log_timing("Starting async processing")

    # For storing the full response to save at the end
    full_response = {}

    try:
        async for msg_type, msg_data in query_agent.process_query_async(
            request=query_request,
            session_id=session_id,
            message_id=message_id
        ):
            if msg_type != "message":
                # Skip non-message yields (e.g. query_result, which is for internal use)
                continue

            # Store all non-debug messages in full_response
            message_type = msg_data.get("type")
            message_content = msg_data.get("content")
            if message_type and message_content and message_type != "debug":
                full_response[message_type] = message_content

            yield handler.create_sse_response(msg_data)

        # Save full response
        conversation_service.add_assistant_response(session_id, full_response, message_id)
        logger.info(f"Stored complete assistant response for session {session_id}")

    except Exception as e:
        logger.error(f"Error during stream generation: {str(e)}")
        error_payload = {
            "type": "error",
            "content": {
                "message": f"An error occurred: {str(e)}"
            },
            "render_type": "error"
        }
        yield handler.create_sse_response(error_payload, finish_reason="error")

    # Always send final response
    handler.log_timing("Stream completed")
    yield handler.create_final_response()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, user_info: Dict[str, Any] = Depends(get_current_user)):
    """OpenAI-compatible chat completion endpoint for streaming and non-streaming."""
    data = await request.json()
    messages = data.get("messages", [])

    user_message = next((msg.get("content") for msg in reversed(messages)
                         if msg.get("role") == "user" and msg.get("content")), None)

    if not user_message:
        error_response = {
            "error": {
                "message": "Chat completion payload must include at least one user message with content",
                "type": "invalid_request_error",
                "code": "missing_user_message"
            }
        }
        return JSONResponse(content=error_response, status_code=400)

    message_id = None
    if messages:
        message_id = messages[-1].get('message_id')

    if not message_id:
        message_id = f"msg-{uuid.uuid4().hex}"
    stream = data.get("stream", False)
    session_id = data.get("session_id", "default")
    model = data.get("model", "general_assistant")  # Default to general_assistant
    user_id = user_info.get('user_id')

    logger.info(f"Chat completion request from user {user_id}: stream={stream}, session={session_id}, model={model}")

    if stream:
        return EventSourceResponse(generate_stream(user_message, session_id, user_info, model=model, message_id=message_id))
    else:
        return await handle_non_streaming_request(user_message, session_id, user_id, model, message_id)


async def handle_non_streaming_request(user_message: str, session_id: str, user_id: str, model: str, message_id: str):
    """Handle non-streaming chat completion requests."""
    conversation_service.add_user_message(session_id, user_message, message_id)
    conversation_history = conversation_service.get_conversation_history(session_id)

    # Get agent configuration based on model name
    try:
        agent_config = get_agent_config(model)
    except ValueError as e:
        logger.error(f"Agent not found for model '{model}': {e}")
        error_response = {
            "error": {
                "message": f"Agent '{model}' not found. Available agents: bolt_data_analyst, synco_agent, police_assistant",
                "type": "invalid_request_error",
                "code": "agent_not_found"
            }
        }
        return JSONResponse(content=error_response, status_code=400)

    # Create QueryRequest with agent configuration
    query_request = QueryRequest(
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

    # Initialize query agent
    query_agent = QueryAgent()
    result_dict = {}

    try:
        # Process all messages from query agent
        async for msg_type, msg_data in query_agent.process_query_async(
            request=query_request,
            session_id=session_id,
            message_id=message_id
        ):
            if msg_type != "message":
                # Skip non-message yields
                continue

            message_type = msg_data.get("type")
            message_content = msg_data.get("content")

            # Store all non-debug messages in result dictionary
            if message_type and message_content:
                # Use the message type as the key
                result_dict[message_type] = message_content

        # Save the complete response
        conversation_service.add_assistant_response(session_id, result_dict, message_id)

    except Exception as e:
        logger.error(f"Error during non-streaming request: {str(e)}")
        error_response = {
            "error": {
                "message": f"Error processing request: {str(e)}",
                "type": "processing_error"
            }
        }
        return JSONResponse(content=error_response, status_code=500)

    # Return OpenAI-like response format
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
