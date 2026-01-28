"""Chat completion API routes - OpenAI compatible endpoints."""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from services.auth_service import get_current_user
from services.chat_service import ChatService, GITBOOK_MODEL_NAME, DEFAULT_MODEL_NAME, AGENT_HINT

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Initialize chat service
chat_service = ChatService()


class StreamResponseHandler:
    """Handles SSE streaming responses with consistent format for frontend."""

    def __init__(self, session_id: str, user_id: str, model: str):
        self.session_id = session_id
        self.user_id = user_id
        self.model = model
        self.stream_start = time.time()

    def log_timing(self, event: str, field: Optional[str] = None):
        current_time = time.time()
        elapsed = (current_time - self.stream_start) * 1000
        if field:
            logger.info("📦 [TIMING] %s '%s' at %.2fms from start", event, field, elapsed)
        else:
            logger.info("🚀 [TIMING] %s at %.2fms from start", event, elapsed)

    def create_sse_response(self, content: Any, finish_reason: Optional[str] = None) -> str:
        render_type = content.get("render_type", "text") if isinstance(content, dict) else "text"
        response = {
            "id": f"chunk-{time.time()}",
            "message": content,
            "render_type": render_type,
            "timestamp": time.time(),
            "finish_reason": finish_reason
        }
        return f"{json.dumps(response)}\n\n"

    def create_final_response(self) -> str:
        return "[DONE]\n\n"


def _extract_user_message(messages: Any) -> Optional[str]:
    if not messages:
        return None
    for message in reversed(messages):
        if message.get("role") == "user" and message.get("content"):
            return message["content"]
    return None


def _resolve_message_id(messages: Any) -> str:
    if messages:
        message_id = messages[-1].get("message_id")
        if message_id:
            return message_id
    return f"msg-{uuid.uuid4().hex}"


def _build_openai_response(
    session_id: str,
    model: str,
    message_content: Any,
    user_id: Optional[str]
) -> Dict[str, Any]:
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


def _build_query_request(agent_config, user_message: str, conversation_history: Any) -> QueryRequest:
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


async def _run_gitbook_answer(query: str, limit: int):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: generate_gitbook_answer(query, limit))


def _sanitize_gitbook_limit(options: Optional[Dict[str, Any]]) -> int:
    """Clamp GitBook passage limit to a safe window."""
    if not options:
        return 4
    limit = options.get("limit", 4)
    try:
        limit_value = int(limit)
    except (TypeError, ValueError):
        return 4
    return max(1, min(10, limit_value))


async def generate_stream(
    query: str,
    session_id: str,
    user_info: Dict[str, Any],
    model: str = DEFAULT_MODEL_NAME,
    message_id: Optional[str] = None,
    gitbook_options: Optional[Dict[str, Any]] = None
):
    handler = StreamResponseHandler(session_id, user_info.get("user_id", "anonymous_user"), model)
    handler.log_timing("Starting stream generation")

    if not message_id:
        yield handler.create_final_response()
        return

    if model == GITBOOK_MODEL_NAME:
        limit = _sanitize_gitbook_limit(gitbook_options)
        async for chunk in _stream_gitbook(query, limit, handler, session_id, message_id):
            yield chunk
        return

    async for chunk in _stream_general(query, model, handler, session_id, message_id):
        yield chunk


async def _stream_gitbook(
    query: str,
    limit: int,
    handler: StreamResponseHandler,
    session_id: str,
    message_id: str
):
    gitbook_response = {"answer": "", "references": []}

    try:
        loop = asyncio.get_running_loop()
        events = await loop.run_in_executor(None, lambda: list(stream_gitbook_answer(query, limit)))
    except ValueError as exc:
        error_payload = {"type": "error", "content": str(exc), "render_type": "error"}
        yield handler.create_sse_response(error_payload, finish_reason="error")
        yield handler.create_final_response()
        return
    except Exception as exc:  # pragma: no cover
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

    conversation_service.add_assistant_response(session_id, gitbook_response, message_id)
    yield handler.create_final_response()


async def _stream_general(
    query: str,
    model: str,
    handler: StreamResponseHandler,
    session_id: str,
    message_id: str
):
    conversation_history = conversation_service.get_conversation_history(session_id)

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

    query_request = _build_query_request(agent_config, query, conversation_history)
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
    except Exception as exc:  # pragma: no cover
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

    conversation_service.add_assistant_response(session_id, full_response, message_id)
    handler.log_timing("Stream completed")
    yield handler.create_final_response()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, user_info: Dict[str, Any] = Depends(get_current_user)):
    """OpenAI-compatible chat completion endpoint for streaming and non-streaming."""
    data = await request.json()
    messages = data.get("messages", [])

    user_message = chat_service.extract_user_message(messages)
    if not user_message:
        error_response = {
            "error": {
                "message": "Chat completion payload must include at least one user message with content",
                "type": "invalid_request_error",
                "code": "missing_user_message"
            }
        }
        return JSONResponse(content=error_response, status_code=400)

    message_id = chat_service.resolve_message_id(messages)
    stream = data.get("stream", False)
    session_id = data.get("session_id", "default")
    model = data.get("model", DEFAULT_MODEL_NAME)
    gitbook_options = data.get("gitbook_options")
    user_id = user_info.get("user_id")

    chat_service.conversation_service.add_user_message(session_id, user_message, message_id)

    logger.info(
        "Chat completion request from user %s: stream=%s, session=%s, model=%s",
        user_id,
        stream,
        session_id,
        model
    )

    if stream:
        return EventSourceResponse(
            chat_service.generate_stream(
                user_message,
                session_id,
                user_info,
                model=model,
                message_id=message_id,
                gitbook_options=gitbook_options
            )
        )

    # Handle non-streaming request
    try:
        if model == GITBOOK_MODEL_NAME:
            response = await chat_service.handle_non_streaming_gitbook(
                user_message, session_id, user_id, model, message_id, gitbook_options
            )
            return JSONResponse(content=response)

        response = await chat_service.handle_non_streaming_general(
            user_message, session_id, user_id, model, message_id
        )
        return JSONResponse(content=response)

    except ValueError as exc:
        logger.error("Invalid request: %s", exc)
        error_response = {
            "error": {
                "message": str(exc),
                "type": "invalid_request_error",
                "code": "agent_not_found" if "not found" in str(exc).lower() else "invalid_request"
            }
        }
        return JSONResponse(content=error_response, status_code=400)

    except Exception as exc:
        logger.error("Error processing request: %s", exc, exc_info=True)
        error_response = {
            "error": {
                "message": f"Error processing request: {str(exc)}",
                "type": "processing_error"
            }
        }
        return JSONResponse(content=error_response, status_code=500)
