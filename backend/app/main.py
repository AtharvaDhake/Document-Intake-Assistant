"""
FastAPI application — thin API layer, no business logic.
"""
import uuid
import asyncio
import logging
import structlog
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any

from .config import Config
from .models.state import SessionState
from .models.fields import FieldValue, FieldStatus
from .engine import ConversationEngine
from .document_generator import generate_document
from .llm import create_llm_client
from .validation.validator import VALID_FIELDS

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
)
logger = structlog.get_logger()

import os
import json
from pathlib import Path

SESSIONS_DIR = Path("sessions_data")
SESSIONS_DIR.mkdir(exist_ok=True)

def _save_session(state: SessionState):
    file_path = SESSIONS_DIR / f"{state.session_id}.json"
    file_path.write_text(state.model_dump_json(), encoding="utf-8")

def _load_session(session_id: str) -> SessionState | None:
    file_path = SESSIONS_DIR / f"{session_id}.json"
    if file_path.exists():
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return SessionState(**data)
    return None

engines: dict[str, ConversationEngine] = {}
engines: dict[str, ConversationEngine] = {}

async def cleanup_old_sessions():
    """Background task to remove sessions older than 24 hours."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=24)
            to_delete = [
                sid for sid, state in sessions.items()
                if getattr(state, 'updated_at', now) < cutoff
            ]
            for sid in to_delete:
                sessions.pop(sid, None)
                engines.pop(sid, None)
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
        await asyncio.sleep(3600)  # Check every hour


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


class MessageRequest(BaseModel):
    message: str

class FieldOverrideRequest(BaseModel):
    value: Any

class SessionResponse(BaseModel):
    session_id: str
    state: dict
    assistant_message: str
    conversation_log: list = []
    patch_applied: list = []
    ambiguities: list = []
    corrections: list = []

class DocumentResponse(BaseModel):
    document_text: str


def _get_session(session_id: str) -> SessionState:
    state = _load_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return state

def _get_engine(session_id: str) -> ConversationEngine:
    if session_id not in engines:
        state = _load_session(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="Session not found")
        client = _create_llm_client()
        engines[session_id] = ConversationEngine(client)
    return engines[session_id]

def _create_llm_client():
    kwargs = {}
    if Config.LLM_PROVIDER == "gemini":
        kwargs["api_key"] = Config.GEMINI_API_KEY
        kwargs["model"] = Config.GEMINI_MODEL
    return create_llm_client(Config.LLM_PROVIDER, **kwargs)


@app.post("/api/sessions", response_model=SessionResponse)
def create_session():
    """Create a new session and return the opening message."""
    state = SessionState()
    state.updated_at = datetime.now(timezone.utc)
    _save_session(state)
    client = _create_llm_client()
    engine = ConversationEngine(client)

    _save_session(state)
    engines[state.session_id] = engine

    opening = engine.start_session(state)
    _save_session(state)

    return {
        "session_id": state.session_id,
        "state": state.model_dump(mode="json"),
        "assistant_message": opening,
        "conversation_log": [entry.model_dump(mode="json") for entry in state.conversation_log],
    }

@app.post("/api/sessions/{session_id}/messages", response_model=SessionResponse)
def send_message(session_id: str, req: MessageRequest):
    """Send a user message and get the assistant's response."""
    state = _get_session(session_id)
    engine = _get_engine(session_id)

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    turn_output = engine.process_turn(state, req.message)
    state.updated_at = datetime.now(timezone.utc)
    _save_session(state)

    return {
        "session_id": session_id,
        "state": state.model_dump(mode="json"),
        "assistant_message": turn_output["assistant_message"],
        "patch_applied": turn_output["patch_applied"],
        "ambiguities": turn_output["ambiguities"],
        "corrections": turn_output["corrections"],
        "conversation_log": [entry.model_dump(mode="json") for entry in state.conversation_log],
    }

@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str):
    """Get the current session state."""
    state = _get_session(session_id)
    
    last_assistant_message = ""
    for entry in reversed(state.conversation_log):
        if entry.role == "assistant":
            last_assistant_message = entry.content
            break

    return {
        "session_id": session_id,
        "state": state.model_dump(mode="json"),
        "assistant_message": last_assistant_message,
        "conversation_log": [entry.model_dump(mode="json") for entry in state.conversation_log],
    }

@app.get("/api/sessions/{session_id}/document", response_model=DocumentResponse)
def get_document(session_id: str):
    """Get the current draft document as text."""
    state = _get_session(session_id)
    doc_text = generate_document(state.fields)
    return {"document_text": doc_text}

@app.post("/api/sessions/{session_id}/fields/{field_name}", response_model=SessionResponse)
def override_field(session_id: str, field_name: str, req: FieldOverrideRequest):
    """Direct manual override of a field — bypasses LLM entirely."""
    state = _get_session(session_id)

    if field_name not in VALID_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown field: {field_name}. Valid fields: {sorted(VALID_FIELDS)}",
        )

    # Apply the override
    old_field = getattr(state.fields, field_name)
    new_fv = FieldValue(
        value=req.value,
        status=FieldStatus.CONFIRMED,
        source_turn=len(state.conversation_log),
        last_updated=datetime.now(timezone.utc),
    )
    setattr(state.fields, field_name, new_fv)

    # Handle dependent fields
    if field_name == "has_children":
        if req.value is False:
            state.fields.children_names = FieldValue(
                status=FieldStatus.NOT_APPLICABLE,
            )
        elif req.value is True and state.fields.children_names.status == FieldStatus.NOT_APPLICABLE:
            state.fields.children_names = FieldValue(
                status=FieldStatus.MISSING,
            )

    state.updated_at = datetime.now(timezone.utc)
    _save_session(state)

    # Check completion
    if state.fields.is_complete():
        state.status = "ready_for_review"

    # Generate an acknowledgement message
    engine = _get_engine(session_id)
    missing = state.fields.missing_fields()
    msg = f"I've updated {field_name.replace('_', ' ')} for you."
    if state.fields.is_complete():
        msg += " All fields are now complete — your document is ready for review!"
    elif missing:
        msg += f" We still need: {', '.join(f.replace('_', ' ') for f in missing[:2])}."

    from .models.state import ConversationEntry as CE
    state.conversation_log.append(
        CE(role="assistant", content=msg)
    )

    return {
        "session_id": session_id,
        "state": state.model_dump(mode="json"),
        "assistant_message": msg,
        "conversation_log": [entry.model_dump(mode="json") for entry in state.conversation_log],
        "patch_applied": [{"field": field_name, "value": req.value, "status": "confirmed", "reasoning": "manual override"}],
        "ambiguities": [],
        "corrections": []
    }


