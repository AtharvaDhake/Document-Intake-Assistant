import uuid
import json
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

import structlog
from fastapi import HTTPException

from .models.state import SessionState
from .engine import ConversationEngine
from .llm import create_llm_client
from .config import Config

logger = structlog.get_logger()

SESSIONS_DIR = Path("sessions_data")
SESSIONS_DIR.mkdir(exist_ok=True)

engines: dict[str, ConversationEngine] = {}

def _save_session(state: SessionState):
    file_path = SESSIONS_DIR / f"{state.session_id}.json"
    file_path.write_text(state.model_dump_json(), encoding="utf-8")

def _load_session(session_id: str) -> SessionState | None:
    try:
        valid_uuid = str(uuid.UUID(session_id))
    except ValueError:
        return None
        
    file_path = SESSIONS_DIR / f"{valid_uuid}.json"
    if file_path.exists():
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return SessionState(**data)
    return None

def get_session_state(session_id: str) -> SessionState:
    state = _load_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return state

def create_llm_client_instance():
    kwargs = {}
    if Config.LLM_PROVIDER == "gemini":
        kwargs["api_key"] = Config.GEMINI_API_KEY
        kwargs["model"] = Config.GEMINI_MODEL
    return create_llm_client(Config.LLM_PROVIDER, **kwargs)

def get_engine(session_id: str) -> ConversationEngine:
    if session_id not in engines:
        state = _load_session(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="Session not found")
        client = create_llm_client_instance()
        engines[session_id] = ConversationEngine(client)
    return engines[session_id]

async def cleanup_old_sessions():
    """Background task to remove sessions older than 24 hours."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=24)
            to_delete = []
            
            for file_path in SESSIONS_DIR.glob("*.json"):
                try:
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    updated_at_str = data.get("updated_at")
                    if updated_at_str:
                        updated_at = datetime.fromisoformat(updated_at_str)
                        if updated_at < cutoff:
                            to_delete.append(file_path)
                except Exception:
                    pass
                    
            for file_path in to_delete:
                file_path.unlink()
                sid = file_path.stem
                engines.pop(sid, None)
                
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
        await asyncio.sleep(3600)
