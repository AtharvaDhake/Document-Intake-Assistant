# Document Intake Assistant

**The application is live on: http://13.60.181.158**

## 1. Live Testing Script

To evaluate the system's robustness, multi-field extraction, and ambiguity handling, we recommend running this exact script in the live app:

### 1.1. Step 1: Multi-field Extraction

- **What you do:** The Assistant asks for your full name.
- **You type:** `"I'm Sarah Connor. My address is 123 Cyberdyne Blvd."`
- **What happens:** In the State Pane, Full Name and Home Address instantly turn green (✅ Confirmed). The Assistant skips asking about them and jumps to Priority #4 ("Do you have any children?").
- **Architectural Highlight:**
  > _Notice what just happened here. The user provided multiple distinct pieces of information at once. Because we use a **Dual-Call LLM Architecture**, the backend first runs an 'Extractor' prompt to parse the raw text into a strict Pydantic JSON schema. The conversational engine sees that those fields are now populated, so it dynamically skips them and moves to the next missing priority. We aren't relying on the LLM to remember what it asked; it's driven purely by the deterministic backend state machine._

### 1.2. Step 2: Smart State Resolution

- **What you do:** The Assistant asks if you have children.
- **You type:** `"Yes, I have one son. His name is John."`
- **What happens:** _Has Children_ becomes ✅ (Yes), and _Children's Names_ captures "John" and becomes ✅ Confirmed.
- **Architectural Highlight:**
  > _The Extractor successfully populates a string array (`children_names`) in the same turn it resolves the Boolean flag, demonstrating complex type handling._

### 1.3. Step 3: Ambiguity Handling & Schema Noise Reduction

- **What you do:** The Assistant asks about worldwide assets.
- **You type:** `"I have a hidden bank account in Mexico, does that count as worldwide?"`
- **What happens:** The system flags this as ⚠️ Unconfirmed because it's not a clear yes/no, and asks a follow-up question.
- **Architectural Highlight:**
  > _If this was a basic ChatGPT wrapper, it would have hallucinated an entire new section in the document called "Foreign Bank Accounts" just because the user mentioned Mexico. Because our document generation is tied strictly to our defined database schema (which only tracks a Boolean for `covers_worldwide_assets`), the AI filters out the conversational noise and waits for a definitive Yes/No._

### 1.4. Step 4: Resolving the Ambiguity

- **What you do:** The Assistant asks to clarify the assets.
- **You type:** `"Yes, include the worldwide assets."`
- **What happens:** The _Worldwide Assets_ field flips to ✅ Confirmed.

### 1.5. Step 5: Confidence States & Hesitation

- **What you do:** The Assistant asks for an executor.
- **You type:** `"I guess my friend Miles could be the executor."`
- **What happens:** _Executor Relationship_ captures "friend", and _Executor Name_ captures "Miles", but they are flagged as ⚠️ Unconfirmed with a yellow background. The Assistant asks a follow-up.
- **Architectural Highlight:**
  > _This is a critical safety feature. If the user uses hesitation words like "maybe" or "I guess", the Extractor is instructed to pull the data but flag it as 'Unconfirmed' and log an 'Ambiguity' reason. Before the data is ever allowed to hit the final document, the system forces a conversational follow-up to resolve that ambiguity._

### 1.6. Step 6: Diff-Based Correction & Strict Validation

- **What you do:** The Assistant asks to clarify the executor choice.
- **You type:** `"Actually, I changed my mind. Make my son John the executor."`
- **What happens:** The system updates the name to John and the relationship to son. However, because this is a _Correction_ (overwriting previous data), the Validator intentionally sets both fields to ⚠️ Unconfirmed. The system will now rigorously ask you to confirm _both_ the name and the relationship individually in the next few turns.
- **Architectural Highlight:**
  > _If a user changes their mind, our Python Validator intercepts the patch. It detects a diff between the old value and the new value, logs a `CorrectionRecord`, and intentionally forces the system to re-verify the new data. You will notice the Assistant asking multiple granular questions here to ensure the correction is 100% accurate before it turns green._

### 1.7. Step 7: Completing the Correction Loop

- **What you do:** Answer the Assistant's follow-up questions to confirm the executor.
- **You type:** `"Yess name john as the executor"` (when asked to confirm John), then `"He is my son."` (when asked for relationship).
- **What happens:** The fields turn ✅ Confirmed one by one.
- **Architectural Highlight:**
  > _This double-confirmation loop is a direct result of strict field-level confidence states. When the user corrected the executor to "son John", the system extracted two distinct fields (`executor_name` and `executor_relationship`). Because it was a destructive correction, the Python validator strictly set both to 'Unconfirmed', forcing the LLM to independently verify the name and the relationship before allowing the state to proceed. This guarantees no assumptions are made when overwriting data._

### 1.8. Step 8: Out-of-Order Extraction

- **What you do:** The Assistant asks for specific gifts.
- **You type:** `"No other wishes, just protect the future."`
- **What happens:** The Assistant captures this into the _Additional Wishes_ field, but notices you still haven't answered the _Specific Gifts_ question, so it asks about gifts again!
- **Architectural Highlight:**
  > _Because the user answered the wrong question (providing additional wishes instead of gifts), the Extractor saved the data to the correct field (`additional_wishes`), but the State Machine realized `specific_gifts` was still missing and re-prompted the user._

### 1.9. Step 9: Multi-Item Arrays & Completion

- **What you do:** The Assistant asks for specific gifts again.
- **You type:** `"I want to leave my motorcycle to John, and my sunglasses to the Terminator."`
- **What happens:** The _Specific Gifts_ array correctly populates with both items, completing the required intake process. The system state updates to `ready_for_review`, which automatically switches the UI to the Draft Document tab and instantly triggers a download of your completed `.pdf` document.

## 2. Project Overview

The Document Intake Assistant is a reliable, conversational web application designed to help users draft a fictional Personal Wishes Document.

Rather than relying on a fragile chat transcript to maintain context, the application employs a **reliability-first architecture**. An explicit, strictly typed state object acts as the single source of truth. This state is updated incrementally via LLM-driven structured extraction and deterministic business logic validation, ensuring the final generated document is always perfectly synchronized with verified facts.

---

## 3. Architectural Layers

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

### 3.1. User Interface (`frontend/`)

A React + Vite single-page application that manages optimistic chat updates and renders a dual-pane view:

- **Chat Pane:** A multi-turn conversation interface.
- **Live State Pane:** A real-time view of the structured data, exposing explicit confidence states (Missing, Unconfirmed, Confirmed, N/A). Users can manually override fields here, completely bypassing the LLM.

### 3.2. API Layer (`backend/app/main.py`)

A thin FastAPI layer handling HTTP requests, CORS, and routing. It contains absolutely zero domain logic and acts merely as a transport layer between the React frontend and the backend engine.

### 3.3. Conversation Engine (`backend/app/engine.py`)

The core orchestrator. It manages the turn-by-turn pipeline:

1. **Extraction:** Ask the LLM to extract JSON patches from the user's message.
2. **Validation:** Pass the patch to the Validator.
3. **State Mutation:** Apply accepted patches and handle dependent fields (e.g., if `has_children` is false, `children_names` becomes N/A).
4. **Generation:** Ask the LLM to generate the next conversational reply based on the newly validated state.

### 3.4. LLM Client (`backend/app/llm/`)

Encapsulates the Gemini API SDK. It strictly separates interactions into two distinct calls to prevent context mixing and hallucinations.

### 3.5. Validator (`backend/app/validation/validator.py`)

Pure Python functions that enforce business rules, validate data types, and gracefully detect user corrections before any data touches the core state.

### 3.6. Document Generator (`backend/app/document_generator.py`)

A deterministic templating engine that converts the structured state into the final `.pdf` draft.

---

## 4. Key Engineering Decisions

### 4.1. Field-Level Confidence States

Instead of a simple key-value store, every field is wrapped in a `FieldValue` object tracking its exact status (`missing`, `unconfirmed`, `confirmed`, `not_applicable`). This prevents the LLM from hallucinating final answers from vague user input. If a user says "maybe my sister", the system extracts the relationship as `unconfirmed`, and the UI displays a warning icon until explicitly verified.

### 4.2. The Two-Call LLM Pattern

1. **Extractor:** Runs at Temperature 0.1, forced to output strict JSON matching a Pydantic schema. It is instructed to extract _everything_ it sees, without generating conversational text.
2. **Responder:** Runs at Temperature 0.5 to generate a natural, empathetic reply. It generates this reply based _only_ on the validated state and active ambiguities, ignoring the raw, unverified chat history.

### 4.3. Auto-Save & Reset

Reviewers and users can click the "Save & Restart" button in the chat header to instantly download their current generated `.pdf` document and wipe the session clean. This allows for rapid iteration and testing without needing to manually clear browser LocalStorage.

### 4.4. Diff-Based Corrections

In real-world legal and medical intake, users frequently overshare information that isn't required by the form (e.g., "I have a bank account in Mexico, does that count as worldwide?"). Because the final document generation is tied strictly to the typed Pydantic schema (which only tracks a simple Boolean `True`/`False` for worldwide assets), the Extractor LLM is physically incapable of injecting hallucinated or unrequested asset lists into the final document. The system elegantly answers the user's question, extracts the required boolean, and ignores the conversational fluff, preventing the final legal document from becoming bloated with unstructured chatter.

### 4.5. Strict Real-LLM Enforcement

While the project originally utilized a deterministic keyword-based Mock LLM for local development, the production codebase was deliberately stripped of it. `config.py` now hard-fails if `LLM_PROVIDER != "gemini"`. The deterministic mock logic was moved entirely into `tests/dummy_client.py` and is injected via dependency injection solely to keep the CI pipeline fast and free.

---

## 5. API Contract Reference

The system exposes a clean REST API. (Note: The field override endpoint is a divergence from the original plan, added to support direct UI editing for a vastly superior user experience).

- **`POST /api/sessions`**
  Initializes a session and returns the opening conversational turn.
- **`POST /api/sessions/{id}/messages`**
  Submit a chat turn. Returns the updated state, the assistant's reply, and lists of any applied patches, corrections, or ambiguities.
- **`GET /api/sessions/{id}`**
  Poll current state. Used for restoring sessions on page reload.
- **`GET /api/sessions/{id}/document`**
  Get the deterministically formatted draft text.
- **`POST /api/sessions/{id}/fields/{field_name}`**
  Manually override a field directly from the UI, bypassing the LLM entirely.

---

## 6. Local Setup & Development Instructions

### 6.1. Prerequisites

- Node.js (v18+)
- Python 3.11+
- A valid Google Gemini API Key.

### 6.2. Environment Configuration

Create a `.env` file in the root directory. This file is ignored by git.

```env
GEMINI_API_KEY=your_api_key_here
LLM_PROVIDER=gemini
ENVIRONMENT=development
```

### 6.3. Backend Setup

```bash
cd backend
python -m venv venv
# On Mac/Linux: source venv/bin/activate
# On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### 6.4. Frontend Setup

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The application will be available at `http://localhost:5173`.

---

## 7. Testing Strategy

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

## 8. CI/CD and Deployment Architecture

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

### 8.1. Build & Push

On every push to the `main` branch, the pipeline builds separate Docker images for the Frontend and Backend, tags them with the git SHA, and pushes them to **Amazon ECR (Elastic Container Registry)**.

### 8.2. Continuous Deployment

A self-hosted GitHub Actions runner residing on an **AWS EC2** instance listens for successful builds. It automatically:

1. Pulls the latest images from ECR.
2. Dynamically generates a production `.env` file containing the `GEMINI_API_KEY` and EC2 public IP injected securely via GitHub Secrets.
3. Orchestrates the containers via `docker-compose up -d`, ensuring zero-downtime rolling restarts.

---

## 9. Production Roadmap

While the current architecture securely and reliably demonstrates complex intake logic, migrating to a true enterprise-grade production environment would involve the following strategic upgrades:

### 9.1. Persistence & Data Tier Migration
- **Relational Database Transition:** Replace the local file-based `sessions_data` store with **PostgreSQL**, leveraging SQLAlchemy or SQLModel for robust session persistence, querying, and schema migrations.
- **Caching Layer:** Introduce **Redis** to cache LLM context and rapidly serve in-flight session state without hitting the primary database.

### 9.2. Latency & User Experience
- **WebSocket Streaming:** Transition the `/api/sessions/{id}/messages` HTTP POST endpoint to a **WebSocket protocol**. Streaming the LLM's response tokens directly to the UI will eliminate perceived latency and create a more responsive, human-like chat experience.
- **Optimistic UI Refinements:** Implement more granular typing indicators and field-level loading states while the validator runs diff-checks in the background.

### 9.3. Backend Robustness & Tooling
- **Pydantic V2 & Instructor:** Refactor the LLM Client to utilize the `instructor` library, capitalizing on its guaranteed schema enforcement and automatic JSON-validation retry loops to further harden the extraction pipeline.
- **Observability & APM:** Integrate Datadog or OpenTelemetry to instrument LLM response times, token usage, and API latency across the conversational pipeline.

### 9.4. Security & Compliance
- **Auth & Tenant Isolation:** Implement OAuth2 / JWT authentication (e.g., Auth0 or AWS Cognito) to isolate user sessions and securely associate legal drafts with verified user accounts.
- **PII Scrubbing:** Add a pre-processing middleware that scrubs or masks highly sensitive Personally Identifiable Information (PII) before the payload hits the LLM context.
