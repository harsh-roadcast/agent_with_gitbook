"""Chat completion API routes - OpenAI compatible endpoints."""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from services.auth_service import get_current_user
from services.chat_service import chat_service_manager, GITBOOK_MODEL_NAME, DEFAULT_MODEL_NAME


logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, user_info: Dict[str, Any] = Depends(get_current_user)):
    """OpenAI-compatible chat completion endpoint for streaming and non-streaming."""
    data = await request.json()
    messages = data.get("messages", [])

    user_message = chat_service_manager.extract_user_message(messages)
    if not user_message:
        error_response = {
            "error": {
                "message": "Chat completion payload must include at least one user message with content",
                "type": "invalid_request_error",
                "code": "missing_user_message"
            }
        }
        return JSONResponse(content=error_response, status_code=400)

    message_id = chat_service_manager.resolve_message_id(messages)
    stream = data.get("stream", False)
    session_id = data.get("session_id", "default")
    model = data.get("model", DEFAULT_MODEL_NAME)
    gitbook_options = data.get("gitbook_options")
    user_id = user_info.get("user_id")

    chat_service_manager.conversation_service.add_user_message(session_id, user_message, message_id)

    logger.info(
        "Chat completion request from user %s: stream=%s, session=%s, model=%s",
        user_id,
        stream,
        session_id,
        model
    )

    if stream:
        return EventSourceResponse(
            chat_service_manager.generate_stream(
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
            response = await chat_service_manager.handle_non_streaming_gitbook(
                user_message, session_id, user_id, model, message_id, gitbook_options
            )
            return JSONResponse(content=response)

        response = await chat_service_manager.handle_non_streaming_general(
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
