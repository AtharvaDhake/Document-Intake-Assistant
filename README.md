# Document Intake Assistant

A conversational AI application that interviews users to gather information for a **Personal Wishes Document**. Built with Python/FastAPI backend, React frontend, and Gemini 3.5 Flash Lite for natural language understanding.

> **⚠️ Disclaimer:** This is a fictional example document for demonstration purposes only. It is not legal advice and has no legal effect.

## Architecture

```
Frontend (React + Vite)          ← Chat pane + live preview pane
    │  REST/JSON
API Layer (FastAPI)              ← Thin controllers, no business logic
    │
Conversation Engine              ← Orchestrates: extract → validate → apply → respond
    │                │
LLM Client          Document Generator  ← State → draft text (pure templating)
    │
Gemini 3.5 Flash Lite  OR  Deterministic Mock  ← Swappable via env var
```

### Key Design Decisions

1. **Every field has a status** (`missing` / `unconfirmed` / `confirmed` / `not_applicable`) — not just a value. This makes the system trustworthy and transparent.

2. **Two distinct LLM calls per turn** — Extractor (structured JSON, low temperature) and Responder (natural language). The Responder never sees raw model output, only validated state. This structurally prevents hallucinated facts from reaching the user.

3. **The LLM never writes directly to state.** Every model output is a *proposal* that passes through a validator before anything changes.

4. **Mock LLM client** — fully functional, deterministic, keyword-based. Proves the architecture works without any API key. Toggle with one env var.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+

### Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

# Copy env template and configure
copy ..\.env.example .env     # Windows
# cp ../.env.example .env     # macOS/Linux

# Run with mock LLM (no API key needed)
set LLM_PROVIDER=mock         # Windows
# export LLM_PROVIDER=mock    # macOS/Linux

uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

### Using Real Gemini API

```bash
set LLM_PROVIDER=gemini
set GEMINI_API_KEY=your-api-key-here
uvicorn app.main:app --reload --port 8000
```

Get an API key at https://aistudio.google.com/apikey

## Switching Mock ↔ Real LLM

Set the `LLM_PROVIDER` environment variable:

| Value | Behavior |
|---|---|
| `mock` | Deterministic keyword/regex-based extraction. No API key needed. Fully demonstrates the architecture. |
| `gemini` | Real Gemini 3.5 Flash Lite via google-genai SDK. Requires `GEMINI_API_KEY`. |

The mock client uses pattern matching (regex) instead of AI, but follows the exact same interface contract — proving the LLM is a genuinely isolated architectural seam.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/sessions` | Create a new session |
| `POST` | `/api/sessions/{id}/messages` | Send user message, get response |
| `GET` | `/api/sessions/{id}` | Get current session state |
| `GET` | `/api/sessions/{id}/document` | Get draft document text |
| `POST` | `/api/sessions/{id}/fields/{name}` | Direct field override (bypasses LLM) |

## Running Tests

```bash
cd backend
pytest tests/ -v
```

### Test Suite Overview

| Test File | What It Tests | Why It Exists |
|---|---|---|
| `test_models.py` | Field status, progress counting, completion logic, priority ordering | Core data model correctness — everything else depends on this |
| `test_validator.py` | Type checking, business rules, partial patch acceptance, correction detection | Validator is the safety layer between LLM output and state — must be bulletproof |
| `test_document_generator.py` | Full/partial/empty state rendering, placeholder logic | Document output must always be readable regardless of completion state |
| `test_engine.py` | Turn orchestration, multi-field extraction, corrections, ambiguities, completion | The engine is the most complex component — integration-tests the full pipeline |
| `test_api.py` | Response shapes, error codes, end-to-end conversation flow | Ensures the HTTP contract matches what the frontend expects |

## Project Structure

```
backend/
  app/
    models/          ← Data models: fields, patches, session state
    validation/      ← Patch validator with type + business rule checks
    llm/             ← LLM client interface + Gemini + Mock implementations
    engine.py        ← Conversation engine (turn orchestration)
    document_generator.py  ← State → draft document (pure templating)
    main.py          ← FastAPI application
    config.py        ← Environment configuration
  tests/             ← Focused test suite (~30 tests)

frontend/
  src/
    components/      ← ChatPane, StatePane
    api.js           ← API client
    App.jsx          ← Main layout
```
