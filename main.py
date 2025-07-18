import logging
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import all the new separated route modules
from routes import (
    main_routes,
    auth_routes,
    chat_routes,
    elasticsearch_routes,
    conversation_routes,
    search_routes,
    document_routes,
    bulk_index_routes
)
from services.auth_service import generate_startup_token
from services.llm_service import init_llm
from services.mapping_service import initialize_index_schema
from middleware.auth_context import AuthContextMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the FastAPI application
app = FastAPI(
    title="DSPy Agent API",
    description="FastAPI application with DSPy for natural language processing and JWT authentication",
)

# Set up static files directory
static_dir = pathlib.Path(__file__).parent / "static"
if not static_dir.exists():
    static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Initialize DSPy with local LLM
llm = init_llm()

# Add authorization context middleware (must be added before other middleware)
app.add_middleware(AuthContextMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware dependency to inject static_dir into routes that need it
def get_static_dir():
    return static_dir

# Include all the separated routers
app.include_router(main_routes.router)
app.include_router(auth_routes.router)
app.include_router(chat_routes.router)
app.include_router(elasticsearch_routes.router)
app.include_router(conversation_routes.router)
app.include_router(search_routes.router)
app.include_router(document_routes.router)
app.include_router(bulk_index_routes.router)

@app.get("/")
async def root_with_static():
    """Serve the web UI with static_dir injected"""
    return await main_routes.root(static_dir=static_dir)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
