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
from services.conversation_service import conversation_service
from services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])

async def generate_stream(query: str, session_id: str, user_info: Dict[str, Any], model="LLM_TEXT_SQL"):
    """Generate streaming response with user context."""
    ad = ActionDecider()
    user_id = user_info.get('user_id', 'anonymous_user')

    logger.info(f"Processing query for user {user_id}: {query[:100]}...")

    # Add user message to conversation history
    conversation_service.add_user_message(session_id, query)

    # Get conversation context for this query
    conversation_context = conversation_service.get_context_for_query(session_id)
    conversation_history = conversation_service.get_conversation_history(session_id)

    try:
        # Use the conversation history in the async processing
        response_data = {}
        async for field, value in ad.process_async(
            user_query=query,
            conversation_history=conversation_history
        ):
            # Skip sending database and chart_config to frontend
            if field in ["database", "chart_config"]:
                logger.debug(f"Skipping field '{field}' - not sent to frontend")
                # Still store for conversation history
                response_data[field] = value
                continue

            # Store response data for conversation history
            response_data[field] = value

            # Check for validation errors that should stop processing
            if field == "error":
                # Check if this is a validation error that should stop processing
                error_msg = str(value)
                if any(phrase in error_msg.lower() for phrase in [
                    "cannot proceed",
                    "elasticsearch query returned 0 results",
                    "vector search returned 0 results",
                    "invalid or missing elasticsearch query",
                    "invalid or missing vector search query",
                    "failed to generate embedding"
                ]):
                    # Add error response to conversation history
                    conversation_service.add_assistant_response(session_id, response_data)

                    # Send the error and stop processing immediately
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
                    return  # Stop processing immediately

            # Format the content based on field type for normal processing
            if field == "elastic_query":
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
                # For other fields (excluding database and chart_config which are filtered above)
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

        # Add complete response to conversation history
        conversation_service.add_assistant_response(session_id, response_data)

        # Final [DONE] chunk for successful completion
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
        # Handle any unexpected errors during streaming
        logger.error(f"Error in generate_stream: {e}", exc_info=True)
        error_content = f"**Error:**\nUnexpected error occurred: {str(e)}\n\n\n"

        # Add error to conversation history
        error_response = {"error": str(e)}
        conversation_service.add_assistant_response(session_id, error_response)

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
        return

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
            # Add user message to conversation history
            conversation_service.add_user_message(session_id, user_message)

            # Get conversation history for context
            conversation_history = conversation_service.get_conversation_history(session_id)

            ad = ActionDecider()
            result_dict = {}

            # Collect all the async results into a dictionary, excluding database and chart_config
            async for field, value in ad.process_async(
                user_query=user_message,
                conversation_history=conversation_history
            ):
                # Skip database and chart_config fields for frontend
                if field not in ["database", "chart_config"]:
                    result_dict[field] = value
                else:
                    logger.debug(f"Skipping field '{field}' - not sent to frontend")

            # Add response to conversation history
            conversation_service.add_assistant_response(session_id, result_dict)

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


# LangGraph Style API Endpoints

@router.post("/v1/search")
async def search_endpoint(request: Request):
    """
    LangGraph style search endpoint for querying and retrieving information.
    """
    try:
        data = await request.json()
        query = data.get("query", "")
        limit = data.get("limit", 10)
        filters = data.get("filters", {})
        session_id = data.get("session_id", "search_session")

        if not query:
            return JSONResponse(status_code=400, content={"error": "Query parameter is required"})

        user_id = "anonymous_user"  # Disabled auth
        logger.info(f"Search request from user {user_id}: {query[:100]}...")

        # Add to conversation history and get context
        conversation_service.add_user_message(session_id, query)
        conversation_history = conversation_service.get_conversation_history(session_id)

        # Use ActionDecider to process the search query
        ad = ActionDecider()
        search_results = []

        # Process the search query and collect results
        async for field, value in ad.process_async(
            user_query=query,
            conversation_history=conversation_history
        ):
            if field == "data" and value:
                # Limit the results based on the limit parameter
                limited_results = value[:limit] if isinstance(value, list) else [value]
                search_results.extend(limited_results)
            elif field == "summary":
                search_results.append({
                    "type": "summary",
                    "content": value,
                    "relevance_score": 0.9
                })

        response = {
            "query": query,
            "results": search_results,
            "total": len(search_results),
            "limit": limit,
            "filters": filters,
            "session_id": session_id,
            "user_id": user_id,
            "timestamp": int(time.time())
        }

        # Add response to conversation history
        conversation_service.add_assistant_response(session_id, {"search_results": search_results})

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error in search endpoint: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Search error: {str(e)}"})


@router.post("/v1/threads/{thread_id}/messages")
async def add_message_to_thread(thread_id: str, request: Request):
    """
    Add a message to a thread and get response with conversation history.
    """
    try:
        data = await request.json()
        message = data.get("message", "")
        stream = data.get("stream", False)

        if not message:
            return JSONResponse(status_code=400, content={"error": "Message is required"})

        user_id = "anonymous_user"  # Disabled auth
        user_info = {"user_id": user_id}  # Create mock user_info for generate_stream
        logger.info(f"Adding message to thread {thread_id} for user {user_id}: {message[:100]}...")

        if stream:
            # Return streaming response with conversation history
            return EventSourceResponse(generate_stream(message, thread_id, user_info, model="LLM_TEXT_SQL"))
        else:
            # Non-streaming response with conversation history
            conversation_service.add_user_message(thread_id, message)
            conversation_history = conversation_service.get_conversation_history(thread_id)

            ad = ActionDecider()
            result_dict = {}

            async for field, value in ad.process_async(
                user_query=message,
                conversation_history=conversation_history
            ):
                if field not in ["database", "chart_config"]:
                    result_dict[field] = value

            # Add response to conversation history
            conversation_service.add_assistant_response(thread_id, result_dict)

            response = {
                "thread_id": thread_id,
                "message_id": f"msg_{thread_id}_{int(time.time())}",
                "user_id": user_id,
                "created_at": int(time.time()),
                "role": "assistant",
                "content": result_dict,
                "status": "completed"
            }

            return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error adding message to thread {thread_id}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Message error: {str(e)}"})


@router.get("/v1/conversations/{session_id}")
async def get_conversation_history(session_id: str):
    """
    Get conversation history for a session.
    """
    try:
        history = conversation_service.get_conversation_history(session_id)
        context = conversation_service.get_context_for_query(session_id)
        recent_data = conversation_service.get_recent_data_context(session_id)

        response = {
            "session_id": session_id,
            "conversation_history": history,
            "context_summary": context,
            "recent_data_context": recent_data,
            "message_count": len(history),
            "timestamp": int(time.time())
        }

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error getting conversation history for {session_id}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Conversation history error: {str(e)}"})


@router.delete("/v1/conversations/{session_id}")
async def clear_conversation_history(session_id: str):
    """
    Clear conversation history for a session.
    """
    try:
        conversation_service.clear_conversation(session_id)

        response = {
            "session_id": session_id,
            "status": "cleared",
            "timestamp": int(time.time())
        }

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error clearing conversation history for {session_id}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Clear conversation error: {str(e)}"})


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
