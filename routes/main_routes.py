import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.get("/")
async def root(static_dir):
    """Serve the web UI"""
    index_path = static_dir / "index.html"

    if not index_path.exists():
        return {"message": "Web UI not found. Please check the 'static' directory."}

    try:
        with open(index_path) as f:
            content = f.read()
        return HTMLResponse(content=content)
    except Exception as e:
        logger.error(f"Error serving index page: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving index page: {str(e)}")

@router.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
