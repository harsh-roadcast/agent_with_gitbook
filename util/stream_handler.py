"""SSE stream response handler for chat completions."""
import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StreamResponseHandler:
    """Handles SSE streaming responses with consistent format for frontend."""

    def __init__(self, session_id: str, user_id: str, model: str):
        self.session_id = session_id
        self.user_id = user_id
        self.model = model
        self.stream_start = time.time()

    def log_timing(self, event: str, field: Optional[str] = None):
        """Log timing information for stream events."""
        current_time = time.time()
        elapsed = (current_time - self.stream_start) * 1000
        if field:
            logger.info("📦 [TIMING] %s '%s' at %.2fms from start", event, field, elapsed)
        else:
            logger.info("🚀 [TIMING] %s at %.2fms from start", event, elapsed)

    def create_sse_response(self, content: Any, finish_reason: Optional[str] = None) -> str:
        """Create an SSE-formatted response chunk."""
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
        """Create the final SSE response marker."""
        return "[DONE]\n\n"
