import asyncio
import json
import logging
import time
from typing import Dict, Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

# Replace with your actual model call/imports
from modules.models import ActionDecider
from services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])

async def generate_stream(query: str, session_id: str, user_info: Dict[str, Any], model="LLM_TEXT_SQL"):
    """Generate streaming response with user context."""
    ad = ActionDecider()
    user_id = user_info.get('user_id')

    logger.info(f"Processing query for user {user_id}: {query[:100]}...")

    # Use the new async version that yields results as they become available
    async for field, value in ad.process_async(user_query=query, conversation_history=[]):
        # Format the content based on field type
        if field == "database":
            content = f"Database: {value}\n\n\n"
        elif field == "elastic_query":
            content = f"**Elasticsearch Query:**\n{value}\n\n\n"
        elif field == "data":
            content = f"**Data:**\n{list_of_dicts_to_markdown_table(value)}\n\n\n"
        elif field == "summary":
            content = f"**Summary:**\n{value}\n\n\n"
        elif field == "chart_html":
            content = f"**Chart:**\n{value}\n\n\n"   # already a HTML string
        elif field == "error":
            content = f"**Error:**\n{value}\n\n\n"
        else:
            # For other fields like chart_config
            content = f"**{field.capitalize()}:**\n{str(value)}\n\n\n"

        # Create OpenAI-compatible chunk with user context
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
            "user_id": user_id  # Include user context in response
        }
        yield f"event: delta\n"
        yield f"data: {json.dumps(response)}\n\n"

        # Small delay to prevent overwhelming the client
        await asyncio.sleep(0.1)

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

@router.post("/v1/chat/completions")
async def process_query(request: Request, user_info: Dict[str, Any] = Depends(get_current_user)):
    """
    OpenAI-compatible chat completion endpoint for streaming and non-stream.
    Now includes JWT authentication.
    """
    try:
        data = await request.json()
        messages = data.get("messages", [])
        if not messages:
            return JSONResponse(status_code=400, content={"error": "No messages provided"})

        user_message = next((msg["content"] for msg in reversed(messages)
                             if msg.get("role") == "user"), None)
        if not user_message:
            return JSONResponse(status_code=400, content={"error": "No user message found"})

        stream = data.get("stream", False)
        session_id = data.get("session_id", "default")
        model = data.get("model", "default")
        user_id = user_info.get('user_id')

        logger.info(f"Received chat completion request from user {user_id} with model: {model}, stream: {stream}")

        if stream:
            return EventSourceResponse(generate_stream(user_message, session_id, user_info, model=model))

        else:
            # Non-streaming: collect all results and return as one response
            ad = ActionDecider()
            result_dict = {}

            # Collect all the async results into a dictionary
            async for field, value in ad.process_async(user_query=user_message, conversation_history=[]):
                result_dict[field] = value

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
                "user_id": user_id  # Include user context in response
            }
            return JSONResponse(content=response)
    except Exception as e:
        logger.error(f"Error processing query for user {user_info.get('user_id', 'unknown')}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}"})


def list_of_dicts_to_markdown_table(lst):
    if not lst:
        return "No data"
    # Use keys of the first element for header
    header = list(lst[0].keys())
    md = "| " + " | ".join(header) + " |\n"
    md += "| " + " | ".join(['---'] * len(header)) + " |\n"
    for row in lst:
        values = [str(row.get(col, "")) for col in header]
        md += "| " + " | ".join(values) + " |\n"
    return md
