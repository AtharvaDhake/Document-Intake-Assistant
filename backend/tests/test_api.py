"""Tests for the FastAPI API layer."""

from fastapi.testclient import TestClient

from app.main import app
from app.store import create_llm_client_instance
from tests.dummy_client import DummyLLMClient

app.dependency_overrides[create_llm_client_instance] = DummyLLMClient

from app import store as store_module
store_module.create_llm_client_instance = lambda: DummyLLMClient()

client = TestClient(app)


def test_create_session():
    resp = client.post("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "state" in data
    assert "assistant_message" in data
    assert "full name" in data["assistant_message"].lower()


def test_send_message():
    # Create session first
    create_resp = client.post("/api/sessions")
    sid = create_resp.json()["session_id"]

    # Send a message
    resp = client.post(
        f"/api/sessions/{sid}/messages",
        json={"message": "My name is Jane Smith."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "assistant_message" in data
    assert "state" in data
    assert "patch_applied" in data
    assert "ambiguities" in data


def test_get_session():
    create_resp = client.post("/api/sessions")
    sid = create_resp.json()["session_id"]

    resp = client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == sid
    assert "fields" in data["state"]
    assert "status" in data["state"]


def test_get_document():
    create_resp = client.post("/api/sessions")
    sid = create_resp.json()["session_id"]

    resp = client.get(f"/api/sessions/{sid}/document")
    assert resp.status_code == 200
    data = resp.json()
    assert "document_text" in data
    assert "PERSONAL WISHES DOCUMENT" in data["document_text"]
    assert "DISCLAIMER" in data["document_text"]


def test_field_override():
    create_resp = client.post("/api/sessions")
    sid = create_resp.json()["session_id"]

    resp = client.post(
        f"/api/sessions/{sid}/fields/full_name",
        json={"value": "Direct Override Name"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"]["fields"]["full_name"]["value"] == "Direct Override Name"
    assert data["state"]["fields"]["full_name"]["status"] == "confirmed"


def test_unknown_session_returns_404():
    resp = client.get("/api/sessions/nonexistent-id")
    assert resp.status_code == 404


def test_unknown_field_override_returns_400():
    create_resp = client.post("/api/sessions")
    sid = create_resp.json()["session_id"]

    resp = client.post(
        f"/api/sessions/{sid}/fields/favorite_color",
        json={"value": "blue"},
    )
    assert resp.status_code == 400


def test_empty_message_returns_400():
    create_resp = client.post("/api/sessions")
    sid = create_resp.json()["session_id"]

    resp = client.post(
        f"/api/sessions/{sid}/messages",
        json={"message": "   "},
    )
    assert resp.status_code == 400


def test_full_conversation_flow():
    """End-to-end: create session, answer all questions, check completion."""
    create_resp = client.post("/api/sessions")
    sid = create_resp.json()["session_id"]

    messages = [
        "My name is Jane Smith.",
        "I live at 12 Elm Street, London.",
        "No, I don't have children.",
        "Yes, worldwide please.",
        "My brother James Smith.",
        "No specific gifts.",
        "Nothing else, thanks.",
    ]

    for msg in messages:
        resp = client.post(
            f"/api/sessions/{sid}/messages",
            json={"message": msg},
        )
        assert resp.status_code == 200

    # Check final state
    state_resp = client.get(f"/api/sessions/{sid}")
    data = state_resp.json()
    assert data["state"]["status"] == "ready_for_review"

    # Check document
    doc_resp = client.get(f"/api/sessions/{sid}/document")
    doc = doc_resp.json()["document_text"]
    assert "Jane Smith" in doc
    assert "12 Elm Street" in doc
