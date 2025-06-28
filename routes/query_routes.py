"""Query routes for handling search and query-related endpoints."""
import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

# Replace with your actual model call/imports
from modules.models import ActionDecider
from services.conversation_service import conversation_service
from services.auth_service import get_current_user
from util.redis_client import get_message_query, get_session_message_queries

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])

async def generate_stream(query: str, session_id: str, user_info: Dict[str, Any], model="LLM_TEXT_SQL", message_id: Optional[str] = None):
    """Generate streaming response with user context."""
    ad = ActionDecider()
    user_id = user_info.get('user_id', 'anonymous_user')

    logger.info(f"Processing query for user {user_id}: {query[:100]}...")

    # Add user message to conversation history with message_id
    if not message_id:
        message_id = conversation_service.add_user_message(session_id, query)
    else:
        conversation_service.add_user_message(session_id, query, message_id)

    # Get conversation context for this query
    conversation_context = conversation_service.get_context_for_query(session_id)
    conversation_history = conversation_service.get_conversation_history(session_id)

    try:
        # Use the conversation history in the async processing
        response_data = {}
        async for field, value in ad.process_async(
            user_query=query,
            conversation_history=conversation_history,
            session_id=session_id,
            message_id=message_id
        ):
            # Skip sending database and chart_config to frontend
            if field in ["database"]:
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
                # Send chart HTML without markdown wrapping to avoid escaping
                content = value  # Raw HTML string
            elif field == "error":
                content = f"**Error:**\n{value}\n\n\n"
            elif field == "chart_config":
                content = f"{json.dumps(value)}\n\n"
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
        message_id = data.get("message_id")  # Extract message_id from API request
        model = data.get("model", "default")
        user_id = user_info.get('user_id')

        logger.info(f"Received chat completion request from user {user_id} with model: {model}, stream: {stream}, session_id: {session_id}, message_id: {message_id}")

        if stream:
            return EventSourceResponse(generate_stream(user_message, session_id, user_info, model=model, message_id=message_id))

        else:
            # Non-streaming: collect all results and return as one response
            # Add user message to conversation history with message_id
            if not message_id:
                message_id = conversation_service.add_user_message(session_id, user_message)
            else:
                conversation_service.add_user_message(session_id, user_message, message_id)

            # Get conversation history for context
            conversation_history = conversation_service.get_conversation_history(session_id)

            ad = ActionDecider()
            result_dict = {}

            # Collect all the async results into a dictionary, excluding database and chart_html
            async for field, value in ad.process_async(
                user_query=user_message,
                conversation_history=conversation_history,
                session_id=session_id,
                message_id=message_id
            ):
                # Skip database and chart_html fields for frontend, but include chart_config
                if field not in ["database", "chart_html"]:
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



@router.get("/query/elasticsearch")
async def get_elasticsearch_query(
    session_id: str = Query(..., description="Chat session identifier"),
    message_id: str = Query(..., description="Individual message identifier"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve Elasticsearch query for a specific message from Redis, execute it in scan mode,
    and return all data as a CSV file.

    Args:
        session_id: Chat session identifier
        message_id: Individual message identifier
        current_user: Authenticated user information

    Returns:
        CSV file containing all Elasticsearch query results
    """
    import pandas as pd
    import tempfile
    import os
    from fastapi.responses import FileResponse
    from services.search_service import get_es_client

    try:
        logger.info(f"Retrieving and executing ES query for session {session_id}, message {message_id} by user {current_user.get('user_id', 'unknown')}")

        # Retrieve the query from Redis
        es_query = get_message_query(session_id, message_id)

        if es_query is None:
            raise HTTPException(
                status_code=404,
                detail=f"No Elasticsearch query found for session {session_id}, message {message_id}"
            )

        # Get Elasticsearch client
        es_client = get_es_client()

        # Extract query details
        index = es_query.get('index')
        body = es_query.get('body', {})
        body.pop("size")  # Set size for each scroll batch

        if not index:
            raise HTTPException(
                status_code=400,
                detail="Invalid Elasticsearch query: missing index"
            )

        logger.info(f"Executing ES query in scan mode for index: {index}")

        # Execute query with scan mode to get all data
        all_data = []

        # Use scroll/scan to get all results
        response = es_client.search(
            index=index,
            body=body,
            scroll='2m',  # Keep the scroll context alive for 2 minutes
            size=1000,    # Process 1000 documents at a time
            request_timeout=60
        )

        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']

        # Process first batch
        for hit in hits:
            source_data = hit.get('_source', {})
            # Add document metadata if needed
            source_data['_id'] = hit.get('_id')
            source_data['_score'] = hit.get('_score')
            all_data.append(source_data)

        # Continue scrolling through all results
        while len(hits) > 0:
            try:
                response = es_client.scroll(
                    scroll_id=scroll_id,
                    scroll='2m'
                )
                scroll_id = response['_scroll_id']
                hits = response['hits']['hits']

                for hit in hits:
                    source_data = hit.get('_source', {})
                    source_data['_id'] = hit.get('_id')
                    source_data['_score'] = hit.get('_score')
                    all_data.append(source_data)

            except Exception as scroll_error:
                logger.warning(f"Error during scroll: {scroll_error}")
                break

        # Clear the scroll context
        try:
            es_client.clear_scroll(scroll_id=scroll_id)
        except Exception as clear_error:
            logger.warning(f"Error clearing scroll: {clear_error}")

        if not all_data:
            raise HTTPException(
                status_code=404,
                detail="No data found for the given query"
            )

        logger.info(f"Retrieved {len(all_data)} documents from Elasticsearch")

        # Convert to pandas DataFrame
        df = pd.DataFrame(all_data)

        # Create temporary CSV file
        temp_dir = tempfile.gettempdir()
        csv_filename = f"elasticsearch_query_{session_id}_{message_id}_{int(time.time())}.csv"
        csv_path = os.path.join(temp_dir, csv_filename)

        # Export to CSV
        df.to_csv(csv_path, index=False, encoding='utf-8')

        logger.info(f"Created CSV file: {csv_path} with {len(df)} rows and {len(df.columns)} columns")

        # Return CSV file as response
        return FileResponse(
            path=csv_path,
            filename=csv_filename,
            media_type='text/csv',
            headers={
                "Content-Disposition": f"attachment; filename={csv_filename}",
                "X-Total-Records": str(len(df)),
                "X-Session-ID": session_id,
                "X-Message-ID": message_id
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error executing ES query and generating CSV for session {session_id}, message {message_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while processing query: {str(e)}"
        )


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
