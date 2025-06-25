from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import json
import time
import logging
import asyncio

# Replace with your actual model call/imports
from modules.models import ActionDecider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])

async def generate_stream(query: str, session_id: str, model="LLM_TEXT_SQL"):
    ad = ActionDecider()
    raw_result = ad(user_query=query, conversation_history=[])
    # Assume raw_result is dict-like:
    result_dict = {
        "database": raw_result.get("database"),
        "data": raw_result.get("data"),
        "summary": raw_result.get("summary"),
        "chart_config": raw_result.get("chart_config"),
        "html": raw_result.get("chart_html"),
    }

    # Stream each field: send as plain string, not JSON string!
    for field in ["database", "data", "summary", "chart_config", "html"]:
        value = result_dict[field]
        if value is not None:
            # For chart_html, send HTML string directly
            if field == "html":
                content = f"**Chart:**\n{value}\n\n\n"   # already a HTML string
            # For summary/data, send as pretty string or markdown
            elif field == "summary":
                content = f"**Summary:**\n{value}\n\n\n"
            elif field == "data":
                # If data is dict/list, pretty print as markdown table (optional)
                content = f"**Data:**\n{list_of_dicts_to_markdown_table(value)}\n\n\n"
            else:
                content = f"Database: \n{str(value)}\n\n\n"
            # OpenAI-compatible chunk
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
                ]
            }
            yield f"event: delta\n"
            yield f"{json.dumps(response)}\n\n"
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
        ]
    }
    yield f"data: {json.dumps(response)}\n\n"
    yield "data: [DONE]\n\n"

@router.post("/v1/chat/completions")
async def process_query(request: Request):
    """
    OpenAI-compatible chat completion endpoint for streaming and non-stream.
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
        logger.info(f"Received chat completion request with model: {model}, stream: {stream}")

        if stream:
            return EventSourceResponse(generate_stream(user_message, session_id, model=model))

        else:
            # Non-streaming: just return the full dict as one message
            ad = ActionDecider()
            raw_result = ad(user_query=user_message, conversation_history=[])
            result_dict = {
                "database": raw_result.get("database"),
                "data": raw_result.get("data"),
                "summary": raw_result.get("summary"),
                "chart_config": raw_result.get("chart_config"),
                "chart_html": raw_result.get("chart_html"),
            }
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
                            "content": json.dumps(result_dict, ensure_ascii=False, indent=2)
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }
            return JSONResponse(content=response)
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
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

