"""Chat completion API routes - OpenAI compatible endpoints."""
import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from modules.models import ActionDecider
from services.conversation_service import conversation_service
from services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

async def generate_stream(query: str, session_id: str, user_info: Dict[str, Any], model="LLM_TEXT_SQL", message_id: Optional[str] = None):
    """Generate streaming response with user context."""
    ad = ActionDecider()
    user_id = user_info.get('user_id', 'anonymous_user')

    logger.info(f"Processing query for user {user_id}: {query[:100]}...")

    # Add user message to conversation history with message_id
    if not message_id:
        yield "data: [DONE]\n\n"
        return

    conversation_service.add_user_message(session_id, query, message_id)

    # Get conversation context for this query
    conversation_context = conversation_service.get_context_for_query(session_id)
    conversation_history = conversation_service.get_conversation_history(session_id)

    try:
        # Use the conversation history in the async processing
        response_data = {}
        assistant_response_stored = False

        try:
            async for field, value in ad.process_async(
                user_query=query,
                conversation_history=conversation_history,
                session_id=session_id,
                message_id=message_id
            ):
                # Skip sending database to frontend
                if field in ["database"]:
                    logger.debug(f"Skipping field '{field}' - not sent to frontend")
                    response_data[field] = value
                    continue

                response_data[field] = value

                # Check for validation errors that should stop processing
                if field == "error":
                    error_msg = str(value)
                    if any(phrase in error_msg.lower() for phrase in [
                        "cannot proceed",
                        "elasticsearch query returned 0 results",
                        "vector search returned 0 results",
                        "invalid or missing elasticsearch query",
                        "invalid or missing vector search query",
                        "failed to generate embedding"
                    ]):
                        # Store assistant response with error data
                        try:
                            conversation_service.add_assistant_response(session_id, response_data, message_id)
                            assistant_response_stored = True
                            logger.info(f"Stored assistant response with error for session {session_id}, message {message_id}")
                        except Exception as store_error:
                            logger.error(f"Failed to store assistant response with error: {store_error}")

                        content = f"**Error:**\n{value}\n\n\n"
                        response = {
                            "id": f"chatcmpl-{session_id}-{time.time()}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "content": content,
                                        "field": field,
                                    },
                                    "finish_reason": "stop"
                                }
                            ],
                            "user_id": user_id
                        }
                        yield f"event: delta\n"
                        yield f"data: {json.dumps(response)}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                # Format the content based on field type
                if field == "elastic_query":
                    content = f"**Elasticsearch Query:**\n{value}\n\n\n"
                elif field == "data_markdown":
                    content = f"{value}\n\n"
                elif field == "summary":
                    content = f"**Summary:**\n{value}\n\n\n"
                elif field == "chart_config":
                    content = f"{json.dumps(value)}\n\n"
                elif field == "error":
                    content = f"**Error:**\n{value}\n\n\n"
                else:
                    content = f"**{field.capitalize()}:**\n{str(value)}\n\n\n"

                # Create OpenAI-compatible chunk
                response = {
                    "id": f"chatcmpl-{session_id}-{time.time()}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "content": content,
                                "field": field,
                            },
                            "finish_reason": None
                        }
                    ],
                    "user_id": user_id
                }
                yield f"event: delta\n"
                yield f"data: {json.dumps(response)}\n\n"
                await asyncio.sleep(0.1)

            # Add complete response to conversation history using the same message_id
            if not assistant_response_stored:
                try:
                    conversation_service.add_assistant_response(session_id, response_data, message_id)
                    logger.info(f"Stored complete assistant response for session {session_id}, message {message_id}")
                except Exception as store_error:
                    logger.error(f"Failed to store complete assistant response: {store_error}")
                    # Store a minimal response to maintain conversation continuity
                    try:
                        conversation_service.add_assistant_response(session_id, {"error": "Failed to store response"}, message_id)
                    except Exception as fallback_error:
                        logger.error(f"Failed to store fallback assistant response: {fallback_error}")

        except Exception as processing_error:
            logger.error(f"Error during async processing: {processing_error}", exc_info=True)
            # Ensure we store some assistant response even if processing fails
            if not assistant_response_stored:
                try:
                    error_response = {"error": str(processing_error)}
                    conversation_service.add_assistant_response(session_id, error_response, message_id)
                    logger.info(f"Stored error assistant response for session {session_id}, message {message_id}")
                except Exception as store_error:
                    logger.error(f"Failed to store error assistant response: {store_error}")

        # Final [DONE] chunk
        response = {
            "id": f"chatcmpl-{session_id}-{time.time()}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": ""},
                    "finish_reason": "stop"
                }
            ],
            "user_id": user_id
        }
        yield f"data: {json.dumps(response)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Error in generate_stream: {e}", exc_info=True)
        error_content = f"**Error:**\nUnexpected error occurred: {str(e)}\n\n\n"

        error_response = {"error": str(e)}
        conversation_service.add_assistant_response(session_id, error_response, message_id)

        response = {
            "id": f"chatcmpl-{session_id}-{time.time()}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": error_content,
                        "field": "error",
                    },
                    "finish_reason": "stop"
                }
            ],
            "user_id": user_id
        }
        yield f"event: delta\n"
        yield f"data: {json.dumps(response)}\n\n"
        yield "data: [DONE]\n\n"

@router.post("/v1/chat/completions")
async def chat_completions(request: Request, user_info: Dict[str, Any] = Depends(get_current_user)):
    """OpenAI-compatible chat completion endpoint for streaming and non-streaming."""
    try:
        data = await request.json()
        messages = data.get("messages", [])
        if not messages:
            return JSONResponse(status_code=400, content={"error": "No messages provided"})

        user_message = next((msg["content"] for msg in reversed(messages)
                             if msg.get("role") == "user"), None)
        if not user_message:
            return JSONResponse(status_code=400, content={"error": "No user message found"})

        message_id = messages[-1]['message_id']
        stream = data.get("stream", False)
        session_id = data.get("session_id", "default")
        model = data.get("model", "default")
        user_id = user_info.get('user_id')

        logger.info(f"Chat completion request from user {user_id}: stream={stream}, session={session_id}")

        if stream:
            # For streaming, assistant_message_id is required
            if not message_id:
                return JSONResponse(status_code=400, content={"error": "message_id is required for streaming"})
            return EventSourceResponse(generate_stream(user_message, session_id, user_info, model=model, message_id=message_id))
        else:
            # Non-streaming response
            if not message_id:
                return JSONResponse(status_code=400, content={"error": "message_id is required"})

            conversation_service.add_user_message(session_id, user_message, message_id)

            conversation_history = conversation_service.get_conversation_history(session_id)
            ad = ActionDecider()
            result_dict = {}

            async for field, value in ad.process_async(
                user_query=user_message,
                conversation_history=conversation_history,
                session_id=session_id,
                message_id=message_id
            ):
                # Skip database and chart_html fields for frontend, but include chart_config
                if field not in ["database", "chart_html"]:
                    result_dict[field] = value

            conversation_service.add_assistant_response(session_id, result_dict, message_id)

            response = {
                "id": f"chatcmpl-{session_id}-{time.time()}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": result_dict
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                },
                "user_id": user_id
            }
            return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error in chat completions: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}"})
