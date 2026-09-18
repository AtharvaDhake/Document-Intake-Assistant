# Document Intake Assistant

**The application is live on: http://13.60.181.158**

## Project Summary
The Document Intake Assistant is a conversational web application designed to help users draft a fictional Personal Wishes Document. Rather than relying on a fragile chat transcript, the application employs a reliability-first architecture where an explicit, strictly typed state object acts as the single source of truth, updated incrementally via LLM-driven structured extraction and deterministic business logic validation.

## Architecture Overview
The codebase enforces a strict separation of concerns, ensuring the LLM is treated as an untrusted data provider rather than the core application controller.

* **UI (`frontend/`)**: React + Vite SPA. Manages optimistic chat updates and renders a dual-pane view (Chat vs. Live Document).
* **API (`backend/app/main.py`)**: FastAPI layer handling HTTP requests and CORS. Contains zero domain logic.
* **Conversation Engine (`backend/app/engine.py`)**: The orchestrator. It manages the turn-by-turn pipeline: extraction → validation → state mutation → generation. Includes exponential backoff retries using `tenacity`.
* **LLM Client (`backend/app/llm/`)**: Encapsulates the Gemini API SDK. Splits interactions into two distinct calls (Extraction vs. Responding).
* **Validator (`backend/app/validation/validator.py`)**: Pure Python functions that enforce business rules (e.g., rejecting children's names if `has_children` is false) and detect user corrections.
* **Document Generator (`backend/app/document_generator.py`)**: A deterministic templating engine that converts the structured state into the final `.txt` draft.

## Key Design Decisions

* **Field-Level Confidence States:** Instead of a simple key-value store, every field is wrapped in a `FieldValue` object tracking its status (`missing`, `unconfirmed`, `confirmed`, `not_applicable`). This prevents the LLM from hallucinating final answers from vague user input.
* **The Two-Call LLM Pattern:** 
  1. **Extractor:** Runs at Temperature 0.1, forced to output strict JSON matching a Pydantic schema.
  2. **Responder:** Runs at Temperature 0.5 to generate a natural, empathetic reply based on the *validated* state, not the raw chat history.
* **Diff-Based Corrections:** If a user changes their mind (e.g., "Actually, my executor is Sarah"), the system doesn't silently overwrite the database. The `validator.py` detects the value change, downgrades the field status back to `unconfirmed`, and logs a `CorrectionRecord`. This triggers the UI to show a strike-through notification and forces the LLM to explicitly acknowledge the change.
* **Strict Real-LLM Enforcement (No Mock Mode):** While the project originally used a deterministic keyword-based Mock LLM for local development, the production codebase was deliberately stripped of it. `config.py` now hard-fails if `LLM_PROVIDER != "gemini"`. The deterministic mock logic was moved entirely into `tests/dummy_client.py` and injected via dependency injection to keep the CI pipeline fast and free.

## API Contract (Divergence Noted)
* `POST /api/sessions`: Initialize a session.
* `POST /api/sessions/{id}/messages`: Submit a chat turn.
* `GET /api/sessions/{id}`: Poll current state.
* `GET /api/sessions/{id}/document`: Get the formatted draft text.
* `POST /api/sessions/{id}/fields/{field_name}`: **(Divergence from plan)** I added a dedicated endpoint to manually override fields directly from the UI pane, bypassing the LLM entirely for a better UX.

## Setup and Run Instructions

### Backend
1. `cd backend`
2. `python -m venv venv`
3. Activate venv: `source venv/bin/activate` (Mac/Linux) or `venv\Scripts\activate` (Windows)
4. `pip install -r requirements.txt`
5. Create a `.env` file in the root directory (see Secrets below).
6. Run the server: `uvicorn app.main:app --reload` (Runs on port 8000).

### Frontend
1. `cd frontend`
2. `npm install`
3. `npm run dev` (Runs on port 5173).

## Environment Variables / Secrets
The application requires the following environment variables. A `.env` file should be placed in the project root (note: `.env` is safely covered in `.gitignore`).

* `GEMINI_API_KEY`: Your Google Gemini API key.
* `LLM_PROVIDER`: Must be set to `gemini`.

## Running the Tests
```bash
cd backend
venv\Scripts\pytest tests/ -v
```
The test suite consists of **48 unit and integration tests**. I chose to aggressively test the `validator.py` and `engine.py` state machines using a dependency-injected `DummyLLMClient`. This guarantees that our business logic, correction detection, and dependency cascading (e.g., `has_children=False`) work flawlessly without incurring LLM API costs or dealing with non-deterministic test flakes.

## CI/CD Pipeline
The project utilizes a fully automated CI/CD pipeline via **GitHub Actions**.
On every push to `main`:
1. **Build & Push:** Docker images for the frontend and backend are built and pushed to **Amazon ECR**.
2. **Deploy:** A self-hosted GitHub Actions runner on an **AWS EC2** instance pulls the latest images and orchestrates them via `docker-compose`. Environment variables are injected securely at runtime via GitHub Secrets.

## Known Limitations
* **In-Memory State:** Sessions are stored in a python dictionary in `main.py`. If the server restarts, all active sessions are lost.
* **No Authentication:** Anyone with the URL can create a session.
* **Memory Leaks:** While a background task cleans up sessions older than 24 hours, a high-traffic attack could OOM the server.

## What I'd Improve for Production
1. **Persistent Storage:** Swap the in-memory dictionary for Redis (for active session state) and PostgreSQL (for finalized documents).
2. **WebSocket Streaming:** Replace the standard POST request for messages with WebSockets. Streaming the LLM's tokens directly to the UI dramatically improves perceived latency.
3. **Pydantic V2 Instructor:** Replace the manual `json.loads` parsing with the `instructor` library for guaranteed schema validation and automatic LLM retries on schema mismatches.
