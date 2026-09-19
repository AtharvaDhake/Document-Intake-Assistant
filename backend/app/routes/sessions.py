from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any
from datetime import datetime, timezone

from ..models.state import SessionState
from ..models.fields import FieldValue, FieldStatus
from ..engine import ConversationEngine
from ..document_generator import generate_document
from ..validation.validator import VALID_FIELDS
from ..store import (
    _save_session, 
    get_session_state, 
    get_engine, 
    create_llm_client_instance, 
    engines
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

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


@router.post("", response_model=SessionResponse)
def create_session():
    """Create a new session and return the opening message."""
    state = SessionState()
    state.updated_at = datetime.now(timezone.utc)
    _save_session(state)
    client = create_llm_client_instance()
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

@router.post("/{session_id}/messages", response_model=SessionResponse)
def send_message(session_id: str, req: MessageRequest):
    """Send a user message and get the assistant's response."""
    state = get_session_state(session_id)
    engine = get_engine(session_id)

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

@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str):
    """Get the current session state."""
    state = get_session_state(session_id)
    
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

@router.get("/{session_id}/document", response_model=DocumentResponse)
def get_document(session_id: str):
    """Get the current draft document as text."""
    state = get_session_state(session_id)
    doc_text = generate_document(state.fields)
    return {"document_text": doc_text}

@router.post("/{session_id}/fields/{field_name}", response_model=SessionResponse)
def override_field(session_id: str, field_name: str, req: FieldOverrideRequest):
    """Direct manual override of a field — bypasses LLM entirely."""
    state = get_session_state(session_id)

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
    engine = get_engine(session_id)
    missing = state.fields.missing_fields()
    msg = f"I've updated {field_name.replace('_', ' ')} for you."
    if state.fields.is_complete():
        msg += " All fields are now complete — your document is ready for review!"
    elif missing:
        msg += f" We still need: {', '.join(f.replace('_', ' ') for f in missing[:2])}."

    from ..models.state import ConversationEntry as CE
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
