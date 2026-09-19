"""
FastAPI application — thin API layer, no business logic.
"""
import uuid
import asyncio
import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import Config
from .store import cleanup_old_sessions
from .routes.sessions import router as sessions_router

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate config at startup and start background tasks."""
    Config.validate()
    logger.info(f"LLM Provider: {Config.LLM_PROVIDER}")
    if Config.LLM_PROVIDER == "gemini":
        logger.info(f"Gemini Model: {Config.GEMINI_MODEL}")
    
    task = asyncio.create_task(cleanup_old_sessions())
    yield
    task.cancel()


app = FastAPI(
    title="Document Intake Assistant",
    description="Conversational interview → structured state → draft document",
    version="1.0.0",
    lifespan=lifespan,
)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, lock this down
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router)
