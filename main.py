import logging
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
import pathlib
import os
from functools import lru_cache

from routes import query_routes, main_routes
from services.llm_service import init_llm
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the FastAPI application
app = FastAPI(title="DSPy Agent API", description="FastAPI application with DSPy for natural language processing")

# Set up static files directory
static_dir = pathlib.Path(__file__).parent / "static"
if not static_dir.exists():
    static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Initialize DSPy with local LLM
llm = init_llm(model_name="ollama_chat/qwen3:8b")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify your allowed frontend URLs
    allow_credentials=True,
    allow_methods=["*"],  # Or ["GET", "POST", "OPTIONS"]
    allow_headers=["*"],
)

# Middleware dependency to inject static_dir into routes that need it
def get_static_dir():
    return static_dir


# Set up routes directly
@app.post("/v1/chat/completions")
@app.options("/v1/chat/completions")
async def process_query_with_deps(request: Request):
    """Process a query with the query processor dependency injected"""
    return await query_routes.process_query(request)


@app.get("/")
async def root_with_static():
    """Serve the web UI with static_dir injected"""
    return await main_routes.root(static_dir=static_dir)

# Add the history route
@app.get("/history/{session_id}")
async def history_with_deps(session_id: str):
    """Get conversation history for a session"""
    return await query_routes.get_history(session_id)

# Add the stats route
@app.get("/stats")
async def stats_with_deps():
    """Get LLM usage statistics"""
    return await query_routes.get_llm_stats()

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("DSPy Agent API starting up")
    # Initialize any other resources here

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("DSPy Agent API shutting down")
    # Clean up any resources here

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, debug=True)
