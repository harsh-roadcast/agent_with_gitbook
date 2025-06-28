"""Conversation history management routes."""
import logging
import time
from typing import Dict, Any

from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import JSONResponse

from services.auth_service import get_current_user
from services.conversation_service import conversation_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversations"])

@router.get("/v1/conversations/{session_id}")
async def get_conversation_history(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get conversation history for a session.

    Args:
        session_id: Chat session identifier
        current_user: Authenticated user information

    Returns:
        JSON response containing conversation history and context
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
        return JSONResponse(
            status_code=500,
            content={"error": f"Conversation history error: {str(e)}"}
        )

@router.delete("/v1/conversations/{session_id}")
async def clear_conversation_history(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Clear conversation history for a session.

    Args:
        session_id: Chat session identifier
        current_user: Authenticated user information

    Returns:
        JSON response confirming deletion
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
        return JSONResponse(
            status_code=500,
            content={"error": f"Clear conversation error: {str(e)}"}
        )

@router.post("/v1/threads/{thread_id}/messages")
async def add_message_to_thread(
    thread_id: str,
    request: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Add a message to a thread and get response with conversation history.

    Args:
        thread_id: Thread/session identifier
        request: Message request data
        current_user: Authenticated user information

    Returns:
        JSON response with assistant response
    """
    try:
        message = request.get("message", "")
        stream = request.get("stream", False)
        message_id = request.get("message_id")  # Single message_id from frontend

        if not message:
            return JSONResponse(status_code=400, content={"error": "Message is required"})

        if not message_id:
            return JSONResponse(status_code=400, content={"error": "message_id is required"})

        user_id = current_user.get('user_id', 'anonymous_user')
        logger.info(f"Adding message to thread {thread_id} for user {user_id}")

        if stream:
            # Import here to avoid circular imports
            from routes.chat_routes import generate_stream
            from sse_starlette.sse import EventSourceResponse

            return EventSourceResponse(
                generate_stream(message, thread_id, current_user, model="LLM_TEXT_SQL", message_id=message_id)
            )
        else:
            # Non-streaming response
            from modules.models import ActionDecider

            conversation_service.add_user_message(thread_id, message, message_id)
            conversation_history = conversation_service.get_conversation_history(thread_id)

            ad = ActionDecider()
            result_dict = {}

            async for field, value in ad.process_async(
                user_query=message,
                conversation_history=conversation_history
            ):
                if field not in ["database", "chart_html"]:
                    result_dict[field] = value

            conversation_service.add_assistant_response(thread_id, result_dict, message_id)

            response = {
                "thread_id": thread_id,
                "message_id": message_id,  # Use the same message ID
                "user_id": user_id,
                "created_at": int(time.time()),
                "role": "assistant",
                "content": result_dict,
                "status": "completed"
            }

            return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error adding message to thread {thread_id}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Message error: {str(e)}"}
        )
