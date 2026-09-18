# Document Intake Assistant

**The application is live on: http://13.60.181.158**

## Project Overview
The Document Intake Assistant is a reliable, conversational web application designed to help users draft a fictional Personal Wishes Document. 

Rather than relying on a fragile chat transcript to maintain context, the application employs a **reliability-first architecture**. An explicit, strictly typed state object acts as the single source of truth. This state is updated incrementally via LLM-driven structured extraction and deterministic business logic validation, ensuring the final generated document is always perfectly synchronized with verified facts.

---

## Architectural Layers

The codebase enforces a strict separation of concerns, ensuring the LLM is treated as an untrusted data provider rather than the core application controller.

```text
+-------------------------------------------------------------+
|                        FRONTEND                             |
|  +--------------------+       +--------------------------+  |
|  |     Chat Pane      |       |      Live State Pane     |  |
|  |  (User Messaging)  |       | (Structured Data & Draft)|  |
|  +--------------------+       +--------------------------+  |
+-------------------------------------------------------------+
               | HTTP POST/GET (JSON)
               v
+-------------------------------------------------------------+
|                         BACKEND                             |
|  +-------------------------------------------------------+  |
|  |                 API Layer (FastAPI)                   |  |
|  +-------------------------------------------------------+  |
|                              |                              |
|  +-------------------------------------------------------+  |
|  |              Conversation Engine (Orchestrator)       |  |
|  +-------------------------------------------------------+  |
|      |             |                   |             |      |
|      v             v                   v             v      |
| +---------+  +-------------+  +---------------+ +---------+ |
| |   LLM   |  |  Validator  |  | State Mutator | | Doc Gen | |
| |(Gemini) |  | (Rules/Diff)|  | (In-Memory)   | | (Draft) | |
| +---------+  +-------------+  +---------------+ +---------+ |
+-------------------------------------------------------------+
```

### 1. User Interface (`frontend/`)
A React + Vite single-page application that manages optimistic chat updates and renders a dual-pane view:
* **Chat Pane:** A multi-turn conversation interface.
* **Live State Pane:** A real-time view of the structured data, exposing explicit confidence states (Missing, Unconfirmed, Confirmed, N/A). Users can manually override fields here, completely bypassing the LLM.

### 2. API Layer (`backend/app/main.py`)
A thin FastAPI layer handling HTTP requests, CORS, and routing. It contains absolutely zero domain logic and acts merely as a transport layer between the React frontend and the backend engine.

### 3. Conversation Engine (`backend/app/engine.py`)
The core orchestrator. It manages the turn-by-turn pipeline:
1. **Extraction:** Ask the LLM to extract JSON patches from the user's message.
2. **Validation:** Pass the patch to the Validator.
3. **State Mutation:** Apply accepted patches and handle dependent fields (e.g., if `has_children` is false, `children_names` becomes N/A).
4. **Generation:** Ask the LLM to generate the next conversational reply based on the newly validated state.

### 4. LLM Client (`backend/app/llm/`)
Encapsulates the Gemini API SDK. It strictly separates interactions into two distinct calls to prevent context mixing and hallucinations.

### 5. Validator (`backend/app/validation/validator.py`)
Pure Python functions that enforce business rules, validate data types, and gracefully detect user corrections before any data touches the core state.

### 6. Document Generator (`backend/app/document_generator.py`)
A deterministic templating engine that converts the structured state into the final `.txt` draft.

---

## Key Engineering Decisions

### Field-Level Confidence States
Instead of a simple key-value store, every field is wrapped in a `FieldValue` object tracking its exact status (`missing`, `unconfirmed`, `confirmed`, `not_applicable`). This prevents the LLM from hallucinating final answers from vague user input. If a user says "maybe my sister", the system extracts the relationship as `unconfirmed`, and the UI displays a warning icon until explicitly verified.

### The Two-Call LLM Pattern
1. **Extractor:** Runs at Temperature 0.1, forced to output strict JSON matching a Pydantic schema. It is instructed to extract *everything* it sees, without generating conversational text.
2. **Responder:** Runs at Temperature 0.5 to generate a natural, empathetic reply. It generates this reply based *only* on the validated state and active ambiguities, ignoring the raw, unverified chat history.

### Diff-Based Corrections
If a user changes their mind (e.g., "Actually, my executor is Sarah"), the system doesn't silently overwrite the database. The `validator.py` detects the value change, downgrades the field status back to `unconfirmed`, and logs a `CorrectionRecord`. This triggers the UI to show a strike-through notification and forces the LLM to explicitly acknowledge the change in its next response.

### Schema-Driven Noise Reduction
In real-world legal and medical intake, users frequently overshare information that isn't required by the form (e.g., "I have a bank account in Mexico, does that count as worldwide?"). Because the final document generation is tied strictly to the typed Pydantic schema (which only tracks a simple Boolean `True`/`False` for worldwide assets), the Extractor LLM is physically incapable of injecting hallucinated or unrequested asset lists into the final document. The system elegantly answers the user's question, extracts the required boolean, and ignores the conversational fluff, preventing the final legal document from becoming bloated with unstructured chatter.

### Strict Real-LLM Enforcement
While the project originally utilized a deterministic keyword-based Mock LLM for local development, the production codebase was deliberately stripped of it. `config.py` now hard-fails if `LLM_PROVIDER != "gemini"`. The deterministic mock logic was moved entirely into `tests/dummy_client.py` and is injected via dependency injection solely to keep the CI pipeline fast and free.

---

## API Contract Reference

The system exposes a clean REST API. (Note: The field override endpoint is a divergence from the original plan, added to support direct UI editing for a vastly superior user experience).

* **`POST /api/sessions`** 
  Initializes a session and returns the opening conversational turn.
* **`POST /api/sessions/{id}/messages`** 
  Submit a chat turn. Returns the updated state, the assistant's reply, and lists of any applied patches, corrections, or ambiguities.
* **`GET /api/sessions/{id}`** 
  Poll current state. Used for restoring sessions on page reload.
* **`GET /api/sessions/{id}/document`** 
  Get the deterministically formatted draft text.
* **`POST /api/sessions/{id}/fields/{field_name}`** 
  Manually override a field directly from the UI, bypassing the LLM entirely.

---

## Local Setup & Development Instructions

### Prerequisites
* Node.js (v18+)
* Python 3.11+
* A valid Google Gemini API Key.

### 1. Environment Configuration
Create a `.env` file in the root directory. This file is ignored by git.
```env
GEMINI_API_KEY=your_api_key_here
LLM_PROVIDER=gemini
ENVIRONMENT=development
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
# On Mac/Linux: source venv/bin/activate
# On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
The API will be available at `http://localhost:8000`.

### 3. Frontend Setup
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
The application will be available at `http://localhost:5173`.

---

## Testing Strategy

To run the test suite:
```bash
cd backend
# Activate venv first:
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pytest tests/ -v
```

The suite consists of **48 unit and integration tests**. 
Instead of mocking HTTP calls or using fragile prompt-matching, the tests inject a `DummyLLMClient` into the FastAPI dependency graph. This allows aggressive, deterministic testing of the `validator.py` and `engine.py` state machines. We guarantee that business logic, correction detection, and dependency cascading (e.g., `has_children=False` automatically setting `children_names=N/A`) work flawlessly without incurring LLM API costs or dealing with non-deterministic flakes.

---

## CI/CD and Deployment Architecture

The project utilizes a fully automated CI/CD pipeline orchestrated via **GitHub Actions** (`.github/workflows/deploy.yml`), targeting AWS infrastructure.

```text
[Developer Push]
       |
       v
+--------------+        Build & Push Image         +----------------+
|              | --------------------------------> |                |
|    GitHub    |                                   |   Amazon ECR   |
|   Actions    |        SSH / Trigger Deploy       |                |
|              | --------------------+             +----------------+
+--------------+                     |                     |
                                     v                     | Pull
                            +-----------------+            | Latest
                            | Amazon EC2      | <----------+ Image
                            | (Self-hosted)   |
                            +-----------------+
                                     |
                                     v
                            +-----------------+
                            | docker-compose  |
                            | (Live App)      |
                            +-----------------+
```

### Build & Push
On every push to the `main` branch, the pipeline builds separate Docker images for the Frontend and Backend, tags them with the git SHA, and pushes them to **Amazon ECR (Elastic Container Registry)**.

### Continuous Deployment
A self-hosted GitHub Actions runner residing on an **AWS EC2** instance listens for successful builds. It automatically:
1. Pulls the latest images from ECR.
2. Dynamically generates a production `.env` file containing the `GEMINI_API_KEY` and EC2 public IP injected securely via GitHub Secrets.
3. Orchestrates the containers via `docker-compose up -d`, ensuring zero-downtime rolling restarts.

---

## Production Roadmap
If this were scaled to a true production environment, the following architectural upgrades would be prioritized:
1. **Database Migration:** The current implementation uses local disk storage (`sessions_data/*.json`) to ensure sessions survive restarts without complex setup. For production scaling, this should be swapped to Redis/PostgreSQL.
2. **WebSocket Streaming:** Replace the standard HTTP POST polling for messages with WebSockets. Streaming the LLM's response tokens directly to the UI dramatically improves perceived latency and user trust.
3. **Pydantic V2 Instructor:** Replace the manual `json.loads` parsing in the Gemini client with the `instructor` library, leveraging its guaranteed schema validation and automatic LLM retry loops for schema mismatches.


