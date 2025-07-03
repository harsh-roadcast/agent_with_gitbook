"""Search and query processing routes."""
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.conversation_service import conversation_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])

@router.post("/v1/search")
async def search_endpoint(request: Request):
    """
    LangGraph style search endpoint for querying and retrieving information.

    Args:
        request: HTTP request containing search parameters

    Returns:
        JSON response with search results
    """
    try:
        data = await request.json()
        query = data.get("query", "")
        limit = data.get("limit", 10)
        filters = data.get("filters", {})
        session_id = data.get("session_id", "search_session")
        message_id = data.get("message_id")  # Single message_id from frontend

        if not query:
            return JSONResponse(status_code=400, content={"error": "Query parameter is required"})

        if not message_id:
            return JSONResponse(status_code=400, content={"error": "message_id is required"})

        user_id = "anonymous_user"  # Simplified for search endpoint
        logger.info(f"Search request from user {user_id}: {query[:100]}...")

        # Add to conversation history and get context
        conversation_service.add_user_message(session_id, query, message_id)
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

        # Add response to conversation history using the same message_id
        conversation_service.add_assistant_response(session_id, {"search_results": search_results}, message_id)

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error in search endpoint: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Search error: {str(e)}"})

def list_of_dicts_to_markdown_table(lst):
    """Utility function to convert list of dictionaries to markdown table."""
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
