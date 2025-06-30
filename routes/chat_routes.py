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
    stream_start = time.time()
    logger.info(f"🌊 [TIMING] Starting stream generation at {stream_start}")

    ad = ActionDecider()
    user_id = user_info.get('user_id', 'anonymous_user')

    logger.info(f"Processing query for user {user_id}: {query[:100]}...")

    if not message_id:
        yield "data: [DONE]\n\n"
        return

    conversation_service.add_user_message(session_id, query, message_id)
    conversation_context = conversation_service.get_recent_context(session_id)
    conversation_history = conversation_service.get_conversation_history(session_id)

    response_data = {}
    assistant_response_stored = False
    es_data_sent = False

    async_start = time.time()
    logger.info(f"🚀 [TIMING] Starting async processing at {async_start}")

    async for field, value in ad.process_async(
        user_query=query,
        conversation_history=conversation_history,
        session_id=session_id,
        message_id=message_id
    ):
        field_received_time = time.time()
        logger.info(f"📦 [TIMING] Received field '{field}' at {field_received_time} ({(field_received_time - stream_start) * 1000:.2f}ms from start)")

        # Store all response data
        response_data[field] = value

        # Skip certain fields from being sent to frontend immediately
        if field in []:
            logger.debug(f"Skipping field '{field}' - not sent to frontend")
            continue

        # Handle ES data fields - send immediately when available
        if field in ["data", "data_markdown"]:
            logger.info(f"📤 [TIMING] Processing {field} for immediate frontend send")

            # Format the content based on field type
            if field == "data":
                # Don't send raw data to frontend, only markdown
                continue
            elif field == "data_markdown":
                content = f"{value}\n\n"
                es_data_sent = True
            else:
                content = f"**{field.capitalize()}:**\n{str(value)}\n\n\n"

            sse_start = time.time()
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
            sse_end = time.time()
            logger.info(f"✅ [TIMING] SSE message sent for {field} in {(sse_end - sse_start) * 1000:.2f}ms")
            await asyncio.sleep(0.1)
            continue

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
                conversation_service.add_assistant_response(session_id, response_data, message_id)
                assistant_response_stored = True
                logger.info(f"Stored assistant response with error for session {session_id}, message {message_id}")

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

        # Format the content based on field type for other fields
        if field == "elastic_query":
            content = f"**Elasticsearch Query:**\n{value}\n\n\n"
        elif field == "summary":
            summary_time = time.time()
            logger.info(f"📝 [TIMING] Summary received at {summary_time} ({(summary_time - stream_start) * 1000:.2f}ms from start)")
            content = f"**Summary:**\n{value}\n\n\n"
        elif field == "chart_config":
            content = f"{json.dumps(value)}\n\n"
        elif field == "error":
            content = f"**Error:**\n{value}\n\n\n"
        elif field == "database":
            # Send database info to frontend
            content = f"**Database Selected:**\n{value}\n\n\n"
        elif field == "completed":
            # Skip completed status - not needed in frontend
            continue
        else:
            content = f"**{field.capitalize()}:**\n{str(value)}\n\n\n"

        sse_start = time.time()
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
        sse_end = time.time()
        logger.info(f"✅ [TIMING] SSE message sent for {field} in {(sse_end - sse_start) * 1000:.2f}ms")
        await asyncio.sleep(0.1)

    # Add complete response to conversation history
    if not assistant_response_stored:
        conversation_service.add_assistant_response(session_id, response_data, message_id)
        logger.info(f"Stored complete assistant response for session {session_id}, message {message_id}")

    # Final [DONE] chunk
    final_time = time.time()
    logger.info(f"🏁 [TIMING] Stream completed at {final_time} - total time: {(final_time - stream_start) * 1000:.2f}ms")

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
