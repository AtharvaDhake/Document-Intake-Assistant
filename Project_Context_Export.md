# Document Intake Assistant — Full Project Context Export

This file consolidates the entire planning conversation so it can be handed directly to Claude Code (or any coding assistant) as project context. It includes: the original brief, the product/value discussion, the complete technical plan, and a confirmed feature checklist.

---

## 1. Original Brief (from Wenup's technical test PDF)

**Title:** Engineering Candidate Technical Test — LLM Application: Document Intake Assistant

**Objective:** Build a small web application called Document Intake Assistant. It should conduct a conversational interview, maintain structured information collected during that conversation, and produce a draft document from the information supplied. This is not meant to be a sophisticated legal product — the evaluation is about how reliable, well-architected applications are built around LLMs: handling state, ambiguity, and combining conventional software engineering with generative AI. Any LLM provider/framework is allowed; AI dev tools (ChatGPT, Claude, Cursor, Copilot) are encouraged. The solution does not need to be production-ready — engineering decisions and the ability to explain them matter most.

### Scenario — Fictional Product

The app creates a fictional **Personal Wishes Document**, collecting through conversation:
- Full name
- Home address
- Whether the document covers worldwide assets
- Whether the user has children
- Names of children, if applicable
- Name of executor
- Executor's relationship to the user
- Any specific gifts
- Any additional wishes

Example:
> Assistant: "Who would you like to appoint as your executor?"
> User: "My brother James."
(This one message must yield both executor name AND relationship.)

### Requirements — Core Experience

**Application**
- Backend + simple UI
- Multi-turn conversation
- Live preview of structured data AND the draft document
- Allow correcting previously supplied information

**Structured state**
- Explicit schema for collected info (conversation history alone is not sufficient as source of truth)

Example schema shape given in brief:
```json
{
  "full_name": "Jane Smith",
  "covers_worldwide_assets": true,
  "has_children": false,
  "executor": {
    "name": "James Smith",
    "relationship": "brother"
  }
}
```

### LLM Behaviour — Reliability

- Ask sensible follow-ups on missing/unclear/contradictory answers
- Do not invent facts; represent unknown/unconfirmed values explicitly
- Avoid repeating questions already answered
- Handle multi-field answers, in any order
- Validate model output before applying it to state
- Keep preview consistent with latest confirmed state
- Generate a clear draft document
- Clearly label the document as fictional and not legal advice

### Engineering — What to Demonstrate

- Clear separation: UI / application logic / LLM interaction / document generation
- Defined API contract + structured data model
- Graceful handling of model errors, malformed responses, missing configuration
- A small but meaningful automated test suite around the most important behavior
- Straightforward local setup, secrets kept out of source control

### Use of AI Tools

Include a brief **AI log**: key prompts, notable iterations, examples of output you questioned or corrected. Candid beats polished.

### Submission

- Public Git repository
- Complete setup/run instructions
- AI log + a short note on what you'd improve for production

### If No LLM API Access

A deterministic mock/local stub behind a clearly defined LLM interface is acceptable, provided it still demonstrates:
- Structured request/response contracts for the model interaction
- Fixtures covering valid, ambiguous, and malformed model responses
- State updates, corrections, validation, error handling, and document generation
- A short explanation of how the mock would be replaced by a real provider

Paid LLM API access is **not required**.

---

## 2. Product / Value-Add Discussion (what makes this stand out)

The brief explicitly states: *"We value sound judgement more than the number of features completed."* So standing out means executing the few things the brief cares about with unusual rigor, not adding unrelated features.

### The single highest-leverage idea

**Give every field a visible confidence state, not just a value** — `missing` / `unconfirmed` / `confirmed` — surfaced directly in the live preview UI (checkmark / amber flag / grey placeholder). This directly operationalizes the brief's hardest requirement ("do not invent facts, represent unknown/unconfirmed values explicitly") in a way the user can actually see and trust, not just something enforced invisibly in code.

### Other differentiators discussed (implemented in the plan)

1. **Two distinct LLM responsibilities, never mixed in one call:**
   - Call A ("Extractor"): extracts a structured, validated patch from the user's latest message + current state.
   - Call B ("Responder"): generates the next natural-language question/acknowledgement, based only on *already-validated* state — never raw model output.
   - This structurally prevents hallucinated facts from ever reaching the user in conversational form.

2. **Corrections shown as a visible diff**, not a silent overwrite — e.g. `Executor: James (brother) → Sarah (sister)` — proving the correction-handling requirement works instead of just claiming it does.

3. **A real deterministic mock LLM mode, togglable via config even when real API access exists** — proves the LLM interface is a genuinely isolated architectural seam, not just a theoretical abstraction, and removes setup friction for whoever reviews the project.

4. **Product-level care for sensitive subject matter** — calm, plain-language conversational tone (this concerns wills, children, executors), plus a **persistent** disclaimer banner ("fictional, not legal advice") rather than a one-time notice.

### Cheap touches that punch above their weight

- Progress indicator ("5 of 9 fields captured")
- Briefly highlighting the field that was just updated after each turn
- A short "why we ask this" tooltip on a field or two (e.g., worldwide assets) — *flagged as not yet added to the core plan, worth including if time allows*
- Exporting/downloading the finished draft document (txt/PDF)
- Optional: direct manual edit of a field in the UI, bypassing the LLM entirely, as a reliability fallback

### Explicitly avoid

- Unrelated features (auth, multi-user accounts, animations) — dilutes the signal from the few things done well
- Over-engineering the mock/real LLM abstraction into a plugin system nobody asked for
- Building the confidence-state idea into the JSON only and forgetting to surface it in the UI — the visibility *is* the value

### How to make the judgment visible to reviewers

- In the **AI log**, include at least one real moment where the model's extraction was subtly wrong (e.g. inferred a relationship that wasn't stated) and show how the validation layer caught it — more valuable than showing only successes.
- In the **production notes**, mention: rate limiting/cost controls on LLM calls, structured audit logging of state transitions (legal-adjacent context), a human review step before finalizing any real document, and how the mock LLM interface would be swapped for a real provider with function-calling guarantees.

---

## 3. Full Technical Plan

### 3.0 Guiding Principles

1. The LLM never writes directly to state. Every model output is a *proposal* that passes through a validator before it can change anything the user sees as "confirmed."
2. Conversation text is disposable. Structured state is not. You could delete the whole chat transcript and still reconstruct the document from state alone.
3. Every field has a status, not just a value: `missing`, `unconfirmed`, `confirmed`.
4. Two model responsibilities, never mixed in one call: (a) extract structured updates, (b) decide what to say next.
5. Fail loud internally, fail soft externally. Malformed model output should be logged and retried — the user should just see "let me ask that differently," never a stack trace.

### 3.1 Architecture Overview

```
Frontend (UI: chat pane + live preview pane)
        │  REST/JSON (or WebSocket)
API Layer (thin controllers, no business logic)
        │
Conversation Engine (orchestrates the turn: decides what to ask,
                      calls extractor, applies validated patches,
                      calls responder, updates session)
    │                       │
LLM Client Interface   Document Generator (state → draft)
(extract + respond)
    │
Real Provider  OR  Deterministic Mock  (swappable behind one interface)
```

**Layer responsibilities:**

| Layer | Owns | Must NOT do |
|---|---|---|
| Frontend | Rendering chat + preview, sending user input | Any validation logic, any "business" decisions |
| API layer | HTTP concerns, request/response shape, auth (if any) | Talking to the LLM directly, generating documents |
| Conversation Engine | Turn orchestration, deciding next question, merging patches into state | Knowing *how* the LLM is called (that's the client's job) |
| LLM Client Interface | Sending prompts, parsing raw output into typed objects | Deciding what's "true" — it can propose, not confirm |
| Validator | Checking a proposed patch against the schema before it's applied | Talking to the LLM or the UI |
| Document Generator | Turning confirmed state into the draft text | Talking to the LLM at all — pure templating, deterministic and testable |

### 3.2 The Data Model (Structured State)

**Field-level shape** — every collected field is wrapped, not stored raw:

```json
{
  "value": "James Smith",
  "status": "confirmed",
  "source_turn": 4,
  "last_updated": "2026-09-17T10:04:21Z"
}
```

- `missing` — never mentioned.
- `unconfirmed` — extracted but inferred/implicit, or from a partial/ambiguous answer. UI flags this visibly.
- `confirmed` — explicitly confirmed by the user, or extracted with high confidence from an unambiguous statement.

**Full schema:**

```json
{
  "session_id": "uuid",
  "created_at": "iso-datetime",
  "updated_at": "iso-datetime",
  "fields": {
    "full_name": "Field<string>",
    "home_address": "Field<string>",
    "covers_worldwide_assets": "Field<boolean>",
    "has_children": "Field<boolean>",
    "children_names": "Field<string[]>",
    "executor": "Field<{ name: string, relationship: string }>",
    "specific_gifts": "Field<string[]>",
    "additional_wishes": "Field<string>"
  },
  "conversation_log": ["... append-only, for display + debugging, NOT source of truth ..."],
  "status": "in_progress | ready_for_review | completed"
}
```

**Validation rules:**
- `full_name`: non-empty string, min length 2
- `home_address`: non-empty string
- `covers_worldwide_assets`: strict boolean, never inferred from silence
- `has_children`: strict boolean
- `children_names`: array of strings; conditionally required if `has_children.value === true` and still `missing`
- `executor.value.name`: non-empty string
- `executor.value.relationship`: non-empty string, free text
- `specific_gifts`: array, can be empty (optional), each item non-empty string
- `additional_wishes`: string, optional, can be empty

**Dependent-field rule:** `children_names` should only be *required* when `has_children` is `confirmed: true`. If `has_children` is `false`, mark `children_names` as `not_applicable` rather than leaving it `missing` forever — otherwise the "fields remaining" counter never reaches zero.

### 3.3 LLM Interaction Pattern

**Two distinct calls per turn (do not combine):**

**Call A — Extractor** (structured output, low temperature)
- Input: current state (fields only, not full chat history), the last user message, and the field most recently asked about.
- Output: a **patch** — only fields the message actually touched, each with a proposed value + status (`unconfirmed`/`confirmed`) and ideally a short reasoning string.
- Use function-calling/tool-use/strict JSON mode if the provider supports it; otherwise request JSON-only and parse defensively.

Example patch:
```json
{
  "patch": [
    { "field": "executor.name", "value": "James Smith", "status": "confirmed", "reasoning": "explicitly named" },
    { "field": "executor.relationship", "value": "brother", "status": "confirmed", "reasoning": "explicitly stated as brother" }
  ],
  "ambiguities": []
}
```

If ambiguous:
```json
{
  "patch": [],
  "ambiguities": [
    { "field": "has_children", "reason": "user said 'sort of' which is not a clear yes/no" }
  ]
}
```

**Call B — Responder** (natural language, can be slightly higher temperature)
- Input: the *validated, post-patch* state (never raw Call A output), any `ambiguities` needing clarification, and the list of still-`missing` fields.
- Output: the next thing to say — one clear question, or acknowledgement + next question. Never states a fact about the user; only asks/confirms.
- System prompt should hard-constrain: pick **one** missing/unconfirmed field to ask next (priority order below), acknowledge what was just captured, 1–3 sentences, warm plain-language tone.

**Field priority order:**
1. full_name
2. home_address
3. has_children → children_names (if true)
4. covers_worldwide_assets
5. executor.name + relationship
6. specific_gifts
7. additional_wishes

**Why splitting matters:** strict-JSON extraction is far more reliable than "chatty JSON." The Responder never sees raw unvalidated output — only state that already passed the validator — which structurally prevents hallucinated facts from reaching the user conversationally. Each call is independently unit-testable.

**Multi-field / out-of-order answers:** Call A always receives the full current state snapshot, so it can extract several fields from one message regardless of order. Prompt instruction: *"Extract every field mentioned in the user's message, even if it wasn't the field you most recently asked about."*

**Corrections:** just another patch. The Conversation Engine diffs old vs. new value before applying, logs the change into a `corrections` list, passes the diff to Call B so it can acknowledge naturally ("Got it, updating your executor to Sarah."), and surfaces the diff in the UI.

### 3.4 Validation & Error Handling

**Validation layers, in order:**
1. **JSON parse check** — if Call A doesn't return valid JSON, retry once with a stricter "return ONLY JSON" instruction; if it fails again, fall back to a scripted clarifying question rather than crashing.
2. **Schema validation** — every patch item checked against the field's type/shape (Pydantic/Zod). Reject malformed items individually; accept the rest (partial success).
3. **Business rule validation** — e.g. `children_names` provided but `has_children` false → flag as ambiguity, don't silently apply.
4. **Status downgrade rule** — same field proposed twice with different values across turns without explicit correction context → downgrade to `unconfirmed` and ask directly rather than silently overwriting.

**Error scenarios to handle and test:**

| Scenario | Behavior |
|---|---|
| LLM API times out / network error | Retry once with backoff; if still failing, friendly "having trouble right now, try again" message; don't lose conversation state |
| LLM returns malformed JSON | Retry with stricter instruction once; then fall back to a generic clarifying question |
| LLM returns a field not in the schema | Drop that field, log a warning, continue with rest of valid patch |
| LLM returns wrong type (e.g. string for boolean) | Reject that single field, keep rest of patch, treat field as needing clarification |
| Missing API key / config at startup | Fail fast at boot with a clear error, not a runtime 500 mid-conversation |
| Contradictory info in one message (e.g. "no kids, my son is Tom") | Extractor returns as ambiguity, not a guess; Responder asks for clarification |

**Never invent facts — enforced structurally, not just via prompt:** the schema validator refuses any field update not traceable to something the extractor claims came from the user's message; fields default to `missing` and can only move to `unconfirmed`/`confirmed` via an actual patch — no code path sets a "default guess."

### 3.5 UI / UX Plan

**Layout:** two-pane (side-by-side desktop, stacked/tabbed mobile).

**Left: Conversation pane** — standard chat bubbles, assistant left / user right, typing indicator while waiting on Call A + B, free-text input always available.

**Right: Live state + draft document**
- **Structured Data view:** checklist rendering of every schema field:
  - ✅ green check + value → `confirmed`
  - ⚠️ amber flag + value + "please verify" → `unconfirmed`
  - ⬜ grey placeholder + "not yet provided" → `missing`
  - The field just updated briefly highlights so the user connects "what I said" → "what changed."
- **Draft Document view:** generated Personal Wishes Document text, re-rendered after every confirmed update. Missing fields render as a bracketed placeholder, e.g. `[home address not yet provided]`, so the document stays readable even incomplete.
- **Progress indicator:** "6 of 9 fields captured" bar/counter.
- **Correction diff toast:** transient element, e.g. `Executor: James (brother) → Sarah (sister)`.
- **Persistent disclaimer banner:** *"This is a fictional example document for demonstration purposes only. It is not legal advice and has no legal effect."*

**Correcting information:**
1. Conversational correction (primary) — normal patch flow.
2. *(Optional stretch)* Direct edit affordance — small "edit" icon next to each confirmed field, overwrites directly, bypassing the LLM — a reliability fallback if conversational correction ever fails.

**Completion state:** when all required fields are `confirmed` (respecting the `children_names` conditional rule), set `status` to `ready_for_review`, show "Your document is ready," and offer a download action (txt or PDF).

**Not yet added (flagged, optional if time allows):** a short "why we ask this" tooltip on a field or two (e.g. worldwide assets) — cheap to add, explains intent to the user.

### 3.6 API Contract

```
POST /api/sessions
  → creates a new session, returns { session_id, state }

POST /api/sessions/{id}/messages
  body: { "message": "My brother James." }
  → runs Extractor → Validator → apply patch → Responder
  → returns:
    {
      "assistant_message": "Got it — James as your executor, and his relationship is brother. ...",
      "state": { "...full current state..." },
      "patch_applied": ["...what changed this turn..."],
      "ambiguities": []
    }

GET /api/sessions/{id}
  → returns current full state (for reload/refresh)

GET /api/sessions/{id}/document
  → returns the current draft document as text (and/or triggers a PDF export)

POST /api/sessions/{id}/fields/{field_name}
  body: { "value": "..." }
  → direct manual override of a field (bypasses LLM), re-validates, re-renders document
```

Define response shapes as schemas (OpenAPI/Pydantic models or a shared TS types file) so frontend and backend agree, and tests validate against the same contract.

### 3.7 The Mock / Deterministic LLM Layer

Build this even with real API access.

**Interface:**
```
interface LLMClient {
  extract(currentState, lastUserMessage, lastAskedField): ExtractionResult
  respond(validatedState, ambiguities, missingFields): string
}
```
Two implementations: `RealLLMClient` (calls actual provider) and `MockLLMClient` (rule-based / fixture-driven).

**Mock behavior:** simple keyword/regex-based extraction (detect yes/no for booleans, detect "my brother/sister/etc. NAME" patterns for executor) — doesn't need to be smart, needs to be deterministic and demonstrate the contract. Config flag `LLM_PROVIDER=mock|openai|anthropic` for one-line switching.

**Required fixture set:**
- Valid response fixtures: clean single-field answers, multi-field answers, out-of-order answers.
- Ambiguous response fixtures: contradictory statements, vague answers ("maybe," "not sure"), partial answers.
- Malformed response fixtures: broken JSON, JSON with wrong types, JSON with unknown fields, empty response.

Use these fixtures directly as automated test inputs.

### 3.8 Testing Plan

| Area | Test |
|---|---|
| Validator | Rejects malformed patch items; accepts partial-valid patches; enforces conditional rule (children_names vs has_children) |
| Conversation Engine | Applies a multi-field patch correctly; downgrades conflicting re-statements to unconfirmed; correctly logs corrections |
| Mock LLM fixtures | Each fixture (valid/ambiguous/malformed) produces the expected engine behavior end-to-end |
| Document Generator | Given a fully confirmed state, produces expected text; given partial state, renders correct placeholders |
| API layer | Correct response shape; correct error codes for missing config / bad session id |
| Error handling | Simulated LLM timeout/error triggers retry then graceful fallback message, without losing state |

Target roughly 15–25 focused tests — quality over quantity; explain in the README why each group exists.

### 3.9 Tech Stack Suggestion (illustrative, not mandatory)

- **Backend:** Python + FastAPI (Pydantic validation) or Node + Express/TypeScript (Zod)
- **Frontend:** React, two-pane layout, `useState`/`useReducer` is enough for one session
- **LLM provider:** OpenAI or Anthropic, using tool-calling/function-calling specifically for the Extractor call
- **Persistence:** in-memory or SQLite is plenty
- **Testing:** pytest (Python) or vitest/jest (Node)

### 3.10 Build Order

1. Define the schema + validator first, with unit tests, before any LLM code exists.
2. Build the Document Generator as pure templating against a hand-written fake state object — get placeholder logic right.
3. Build the `MockLLMClient` and its fixtures.
4. Build the Conversation Engine against the mock — proves patch-apply, correction, and ambiguity logic, fully testable with zero API cost.
5. Wire up the API layer around the Conversation Engine.
6. Build the frontend against the mock backend — get the two-pane UI, confidence states, and correction diff working end-to-end.
7. Plug in the `RealLLMClient` and tune the two prompts (Extractor, Responder) against real output.
8. Add error-handling edge cases (timeouts, malformed real output) once real failures are visible.
9. Write the AI log as you go (don't reconstruct from memory at the end); write production notes last.

This order isolates the hardest-to-debug variable (real LLM flakiness) until the rest of the system is already fully tested.

### 3.11 AI Log — What to Include

- Prompts used for Extractor and Responder (final versions, plus 1–2 earlier iterations that didn't work and why).
- At least one real example where the model's extraction was wrong or over-confident, and how the validator/status system caught it.
- Any place an AI coding tool (Cursor/Copilot/etc.) generated boilerplate, and what was changed afterward.

### 3.12 Production Improvement Notes — Suggested Points

- Real auth + per-user session storage instead of in-memory/anonymous sessions
- Rate limiting and cost controls on LLM calls
- Structured audit logging of every state transition (important for anything legal-adjacent)
- Human review step before a document is ever treated as "final"
- Replace simple retry logic with a proper queue + exponential backoff and circuit breaker for the LLM provider
- Internationalization if supporting more than one legal jurisdiction (named as a known limitation, out of scope here)

---

## 4. Feature Confirmation Checklist (standout features vs. plan coverage)

| Feature discussed | Status | Location in plan |
|---|---|---|
| Confidence-state per field (missing/unconfirmed/confirmed), visible in UI | ✅ Included | §3.2, §3.5 |
| Two separate LLM calls: Extractor vs. Responder, never mixed | ✅ Included | §3.3 |
| Corrections shown as a diff, not silent overwrite | ✅ Included | §3.3, §3.5 |
| Deterministic mock mode, togglable even with real LLM access | ✅ Included | §3.7 |
| Sensitive-subject tone + persistent disclaimer | ✅ Included | §3.5 |
| Progress indicator | ✅ Included | §3.5 |
| Highlight just-updated field after each turn | ✅ Included | §3.5 |
| Export/download draft document | ✅ Included | §3.5 |
| Direct manual edit of a field, bypassing LLM | ✅ Included (optional/stretch) | §3.5, §3.6 |
| "Why we ask this" tooltip on a field | ⚠️ **Not yet added** | Flagged as optional addition |

---

## 5. Suggested Prompt for Claude Code

When handing this file to Claude Code, a good opening instruction is something like:

> "Read this project context file in full. Build the Document Intake Assistant described here, following the architecture, schema, LLM interaction pattern, and build order exactly as specified in Section 3. Start with Section 3.10 (Build Order) step 1 — the schema and validator — and confirm with me before moving to the next step."

This keeps Claude Code working incrementally against the same plan rather than trying to generate the whole app in one pass.
