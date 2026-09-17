# Document Intake Assistant — Full Technical & Product Plan

This is the complete build plan: architecture, schema, API contracts, conversation flow, LLM interaction pattern, validation, error handling, UI/UX, testing, and a build order you can follow top to bottom without getting stuck.

---

## 1. Guiding Principles (read this before writing code)

1. **The LLM never writes directly to state.** Every model output is a *proposal* that passes through a validator before it can change anything the user sees as "confirmed."
2. **Conversation text is disposable. Structured state is not.** You could delete the whole chat transcript and still reconstruct the document from state alone.
3. **Every field has a status, not just a value.** `missing`, `unconfirmed`, `confirmed`. This is the single idea that makes the whole app feel trustworthy instead of "an AI guessing."
4. **Two model responsibilities, never mixed in one call:** (a) extract structured updates, (b) decide what to say next. Mixing these is the #1 cause of hallucinated state.
5. **Fail loud internally, fail soft externally.** Malformed model output should be logged and retried — the user should just see "let me ask that differently," never a stack trace.

---

## 2. Architecture Overview

```
┌─────────────────────┐
│   Frontend (UI)      │  React/Vue/plain — chat pane + live preview pane
└──────────┬───────────┘
           │ REST/JSON (or WebSocket)
┌──────────▼───────────┐
│  API Layer            │  Thin controllers, no business logic
│  (FastAPI/Express)    │
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  Conversation Engine  │  Orchestrates the turn: decides what to ask,
│  (application logic)  │  calls extractor, applies validated patches,
│                        │  calls responder, updates session
└──────┬───────────┬────┘
       │           │
┌──────▼─────┐ ┌───▼────────────┐
│ LLM Client  │ │ Document        │
│ Interface   │ │ Generator       │
│ (extract +  │ │ (state → draft) │
│  respond)   │ └─────────────────┘
└──────┬──────┘
       │
┌──────▼──────────────┐
│ Real Provider  OR    │  Swappable behind one interface
│ Deterministic Mock   │
└───────────────────────┘
```

**Why this shape:** every arrow is a seam you can test independently. You can unit test the Conversation Engine with a fake LLM Client. You can unit test the Document Generator with a fake state object. You never need a real API key to run your test suite.

### Layer responsibilities (be strict about this)

| Layer | Owns | Must NOT do |
|---|---|---|
| Frontend | Rendering chat + preview, sending user input | Any validation logic, any "business" decisions |
| API layer | HTTP concerns, request/response shape, auth (if any) | Talking to the LLM directly, generating documents |
| Conversation Engine | Turn orchestration, deciding next question, merging patches into state | Knowing *how* the LLM is called (that's the client's job) |
| LLM Client Interface | Sending prompts, parsing raw output into typed objects | Deciding what's "true" — it can propose, not confirm |
| Validator | Checking a proposed patch against the schema before it's applied | Talking to the LLM or the UI |
| Document Generator | Turning confirmed state into the draft text | Talking to the LLM at all — this should be pure templating, deterministic and testable |

---

## 3. The Data Model (Structured State)

This is the single most important artifact in the project. Design it once, carefully.

### 3.1 Field-level shape

Every collected field is wrapped, not stored as a raw value:

```json
{
  "value": "James Smith",
  "status": "confirmed",       // "missing" | "unconfirmed" | "confirmed"
  "source_turn": 4,             // which conversation turn last touched it
  "last_updated": "2026-09-17T10:04:21Z"
}
```

- `missing` — never mentioned.
- `unconfirmed` — the model extracted a value but it was inferred/implicit, or the user gave a partial/ambiguous answer. The UI should visibly flag this.
- `confirmed` — either explicitly confirmed by the user, or extracted with high confidence from a direct, unambiguous statement (e.g., "My name is Jane Smith" → confirmed immediately; "My brother James" → executor.name confirmed, but consider relationship "inferred," still confirmed because it's unambiguous — you decide the exact confidence rules and document them).

### 3.2 Full schema

```json
{
  "session_id": "uuid",
  "created_at": "iso-datetime",
  "updated_at": "iso-datetime",
  "fields": {
    "full_name": Field<string>,
    "home_address": Field<string>,
    "covers_worldwide_assets": Field<boolean>,
    "has_children": Field<boolean>,
    "children_names": Field<string[]>,        // only meaningful if has_children = true
    "executor": Field<{
       "name": string,
       "relationship": string
    }>,
    "specific_gifts": Field<string[]>,         // free-text list, each item a gift
    "additional_wishes": Field<string>
  },
  "conversation_log": [ ... ],   // append-only, for display + debugging, NOT source of truth
  "status": "in_progress" | "ready_for_review" | "completed"
}
```

Where `Field<T>` is the wrapper object from 3.1, generic over the value type.

### 3.3 Validation rules baked into the schema (use a real validator: Pydantic / Zod / JSON Schema)

- `full_name`: non-empty string, min length 2.
- `home_address`: non-empty string.
- `covers_worldwide_assets`: strict boolean, never inferred from silence.
- `has_children`: strict boolean.
- `children_names`: array of strings; **conditionally required** — if `has_children.value === true` and this is still `missing`, the app must ask for it.
- `executor.value.name`: non-empty string.
- `executor.value.relationship`: non-empty string, free text (don't over-constrain — "family friend," "solicitor," etc. are all valid).
- `specific_gifts`: array, can be empty (optional field), each item non-empty string.
- `additional_wishes`: string, optional, can be empty.

**Dependent-field rule** (important, easy to miss): `children_names` should only be *required* when `has_children` is `confirmed: true`. If `has_children` is `false`, mark `children_names` as `"not_applicable"` (a 4th status, or just short-circuit it) rather than leaving it dangling as `missing` forever — otherwise your "fields remaining" counter will never reach zero.

---

## 4. LLM Interaction Pattern (the reliability core)

### 4.1 Two distinct calls per turn (do not combine)

**Call A — Extractor** (structured output, deterministic-leaning, low temperature)
- Input: current state (fields only, not full chat history — keep it lean), the last user message, and the field the assistant most recently asked about (helps disambiguate short answers like "yes").
- Output: a **patch** — only the fields this message actually touched, each with a proposed value and a proposed status (`unconfirmed`/`confirmed`) and, ideally, the model's own short justification (helps you debug and can power an "inferred from: ..." tooltip).
- Force structured output via function-calling / tool-use / strict JSON mode if your provider supports it. If not, ask for JSON only and parse defensively (see §5).

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

If the user's message is ambiguous, the model should return an `ambiguities` array instead of guessing:
```json
{
  "patch": [],
  "ambiguities": [
    { "field": "has_children", "reason": "user said 'sort of' which is not a clear yes/no" }
  ]
}
```

**Call B — Responder** (natural language, can be slightly higher temperature)
- Input: the *validated, post-patch* state (never the raw model output from Call A — always what actually got applied), plus any `ambiguities` that need clarifying, plus a short list of which fields are still `missing`.
- Output: the next thing to say to the user — one clear question, or an acknowledgement + next question. This call should never be allowed to state a fact about the user; it only asks/confirms.
- System prompt should hard-constrain: pick **one** missing/unconfirmed field to ask about next (prioritize order below), acknowledge what was just captured, keep it to 1–3 sentences, warm and plain-language tone.

**Suggested field priority order** (feels natural, and resolves dependencies first):
1. full_name
2. home_address
3. has_children → children_names (if true)
4. covers_worldwide_assets
5. executor.name + relationship
6. specific_gifts
7. additional_wishes

### 4.2 Why splitting these two calls matters

- Extraction that's forced into strict JSON tends to be much more reliable than "chatty JSON."
- The Responder never sees raw, unvalidated model output — it only ever talks about state that has already passed your validator. This structurally prevents hallucinated facts from reaching the user in conversational form.
- You can unit test Call A and Call B completely independently, with fixtures.

### 4.3 Handling multi-field answers and out-of-order answers

Because Call A always receives the *full current state snapshot*, not just "the last question asked," it can extract several fields from one message regardless of order — e.g., "I'm Jane Smith, I live at 12 Elm Street, and no kids" in one go produces a 3-field patch. Your prompt for Call A should explicitly say: *"Extract every field mentioned in the user's message, even if it wasn't the field you most recently asked about."*

### 4.4 Handling corrections

Corrections are just another patch — no special-casing needed in Call A, **but** your Conversation Engine should diff old vs. new value before applying, and:
- Log the change (`old_value → new_value`) into a `corrections` list in state.
- Pass that diff to Call B so it can acknowledge the correction naturally ("Got it, updating your executor to Sarah.").
- Surface the diff in the UI (see §6).

---

## 5. Validation & Error Handling (this is where reviewers will look hardest)

### 5.1 Validation layers, in order

1. **JSON parse check** — if Call A doesn't return valid JSON, retry once with a stricter "return ONLY JSON, no prose" instruction. If it fails again, fall back to a scripted clarifying question ("Sorry, could you say that again?") rather than crashing.
2. **Schema validation** — every patch item is checked against the field's type/shape (Pydantic model / Zod schema). Reject patch items that don't match; accept the rest (partial success, don't throw away a whole valid patch because one field was malformed).
3. **Business rule validation** — e.g., `children_names` provided but `has_children` is false → flag as an ambiguity rather than silently applying it.
4. **Status downgrade rule** — if the same field is proposed twice with different values across turns without an explicit correction context, downgrade to `unconfirmed` and ask the user directly rather than silently overwriting.

### 5.2 Error scenarios to explicitly handle (and test)

| Scenario | Behavior |
|---|---|
| LLM API times out / network error | Retry once with backoff; if still failing, show a friendly "having trouble right now, try again" message; don't lose conversation state |
| LLM returns malformed JSON | Retry with stricter instruction once; then fall back to a generic clarifying question |
| LLM returns a field not in the schema | Drop that field, log a warning, continue with the rest of the valid patch |
| LLM returns a wrong type (e.g., string for a boolean) | Reject that single field, keep rest of patch, treat that field as still needing clarification |
| Missing API key / config at startup | Fail fast at boot with a clear error message, not a runtime 500 mid-conversation |
| User provides contradictory info in one message (e.g., "I have no kids, my son is Tom") | Extractor returns this as an ambiguity, not a guess; Responder asks for clarification |

### 5.3 Never invent facts — enforcement, not just a prompt instruction

Prompting "don't make things up" is necessary but not sufficient. Enforce it structurally:
- The schema validator refuses any field update that isn't traceable to something the extractor claims came from the user's message.
- Fields default to `missing` and can only move to `unconfirmed`/`confirmed` via an actual patch — there is no code path that sets a "default guess."

---

## 6. UI / UX Plan

### 6.1 Layout

Two-pane layout (side-by-side on desktop, stacked/tabbed on mobile):

**Left: Conversation pane**
- Standard chat bubbles, assistant left-aligned, user right-aligned.
- Typing indicator while waiting on Call A + Call B.
- Free-text input, always available (no forced multiple-choice — this is a conversational assistant).

**Right: Live state + draft document, in two tabs or stacked sections**
- **Structured Data view:** a checklist-style rendering of every schema field:
  - ✅ green check + value, for `confirmed`
  - ⚠️ amber flag + value + "please verify" for `unconfirmed`
  - ⬜ grey placeholder + "not yet provided" for `missing`
  - The field just updated this turn briefly highlights (e.g., a soft flash/border) so the user visually connects "what I said" → "what changed."
- **Draft Document view:** the generated Personal Wishes Document text, re-rendered after every confirmed update. Missing fields render as a clearly bracketed placeholder, e.g., `[home address not yet provided]`, so the document is always readable even when incomplete.
- **Progress indicator:** "6 of 9 fields captured" bar/counter at the top of this pane.
- **Correction diff toast:** when a correction happens, a small transient element: `Executor: James (brother) → Sarah (sister)`.
- **Persistent disclaimer banner** pinned above the draft document: *"This is a fictional example document for demonstration purposes only. It is not legal advice and has no legal effect."*

### 6.2 Correcting information

Two ways to support this (implement at least the first):
1. **Conversational correction** — user just types "actually my executor is my sister Sarah" mid-conversation; handled entirely by the normal patch flow (§4.4).
2. *(Optional stretch)* **Direct edit affordance** — a small "edit" icon next to each confirmed field in the Structured Data view that lets the user overwrite it directly, bypassing the LLM entirely. This is a nice reliability fallback: if the model ever gets something wrong and conversational correction doesn't work, the user isn't stuck.

### 6.3 Completion state

When all required fields are `confirmed` (respecting the conditional rule for `children_names`), switch `status` to `ready_for_review`, show a clear "Your document is ready" state, and offer a **download** action (plain text or PDF) for the draft.

---

## 7. API Contract

Keep it small and RESTful. Example:

```
POST /api/sessions
  → creates a new session, returns { session_id, state }

POST /api/sessions/{id}/messages
  body: { "message": "My brother James." }
  → runs Extractor → Validator → apply patch → Responder
  → returns:
    {
      "assistant_message": "Got it — James as your executor, and his relationship is brother. ...",
      "state": { ...full current state... },
      "patch_applied": [ ...what changed this turn... ],
      "ambiguities": [ ... ]
    }

GET /api/sessions/{id}
  → returns current full state (for reload/refresh)

GET /api/sessions/{id}/document
  → returns the current draft document as text (and/or triggers a PDF export)

POST /api/sessions/{id}/fields/{field_name}
  body: { "value": ... }
  → direct manual override of a field (bypasses LLM), re-validates, re-renders document
```

Response shape should be **consistent and typed** — define these as schemas (OpenAPI/Pydantic models or a shared TS types file) so both FE and BE agree, and so your tests can validate against the same contract.

---

## 8. The Mock / Deterministic LLM Layer

Build this **even if you have real API access** — see the value case in the strategy discussion, and the brief explicitly rewards it.

### 8.1 Interface

```
interface LLMClient {
  extract(currentState, lastUserMessage, lastAskedField): ExtractionResult
  respond(validatedState, ambiguities, missingFields): string
}
```

Two implementations: `RealLLMClient` (calls actual provider) and `MockLLMClient` (rule-based / fixture-driven).

### 8.2 Mock behavior

- Simple keyword/regex-based extraction for the mock (e.g., detect "yes"/"no" for booleans, detect "my brother/sister/etc. NAME" patterns for executor) — it doesn't need to be smart, it needs to be **deterministic and demonstrate the contract**.
- Include a config flag (`LLM_PROVIDER=mock|openai|anthropic`) so switching is a one-line env change.

### 8.3 Fixtures to build (required set)

- **Valid response fixtures:** clean single-field answers, multi-field answers, out-of-order answers.
- **Ambiguous response fixtures:** contradictory statements, vague answers ("maybe," "not sure"), partial answers.
- **Malformed response fixtures:** broken JSON, JSON with wrong types, JSON with unknown fields, empty response.

Use these fixtures directly as your automated test inputs (§9) — this dual-purpose is efficient and exactly what the brief asks for.

---

## 9. Testing Plan (small but meaningful, per the brief)

You don't need 100% coverage. Target the *risk* areas:

| Area | Test |
|---|---|
| Validator | Rejects malformed patch items; accepts partial-valid patches; enforces conditional rule (children_names vs has_children) |
| Conversation Engine | Applies a multi-field patch correctly; downgrades conflicting re-statements to unconfirmed; correctly logs corrections |
| Mock LLM fixtures | Each fixture (valid/ambiguous/malformed) produces the expected engine behavior end-to-end |
| Document Generator | Given a fully confirmed state, produces expected text; given partial state, renders correct placeholders |
| API layer | Correct response shape; correct error codes for missing config / bad session id |
| Error handling | Simulated LLM timeout/error triggers retry then graceful fallback message, without losing state |

Aim for maybe 15–25 focused tests total — quality over quantity, and mention in your README *why* each group exists.

---

## 10. Tech Stack Suggestion (pick what you're fastest in — this is illustrative, not mandatory)

- **Backend:** Python + FastAPI (great for Pydantic-based schema validation) or Node + Express/TypeScript (great for Zod).
- **Frontend:** React (simple two-pane layout, no need for heavy state libraries — `useState`/`useReducer` is enough for one session).
- **LLM provider:** OpenAI or Anthropic, using tool-calling/function-calling for the Extractor call specifically (this gets you much more reliable structured output than parsing free text JSON).
- **Persistence:** in-memory or SQLite is plenty for this exercise — don't over-invest here.
- **Testing:** pytest (Python) or vitest/jest (Node).

---

## 11. Build Order (do it in this sequence to avoid getting stuck)

1. Define the schema + validator first, with unit tests, before any LLM code exists.
2. Build the Document Generator as pure templating against a hand-written fake state object (no LLM needed yet) — get the placeholder logic right.
3. Build the `MockLLMClient` and its fixtures.
4. Build the Conversation Engine against the mock — this is where patch-apply, correction, and ambiguity logic all get proven out, fully testable with zero API cost.
5. Wire up the API layer around the Conversation Engine.
6. Build the frontend against the mock backend — get the two-pane UI, confidence states, and correction diff working end-to-end.
7. Only now, plug in the `RealLLMClient` and tune the two prompts (Extractor, Responder) against real output.
8. Add error-handling edge cases (timeouts, malformed real output) once you can see what real failures actually look like.
9. Write the AI log as you go (don't reconstruct it from memory at the end) and the production notes last.

This order means the hardest-to-debug part (real LLM flakiness) is the *last* variable introduced into an otherwise fully-tested system — much easier to isolate problems this way.

---

## 12. What to Write in the AI Log

Keep it honest and short, per the brief. Structure suggestion:
- Prompts used for Extractor and Responder (final versions, plus 1–2 earlier iterations that didn't work and why).
- At least one real example where the model's extraction was wrong or over-confident, and how your validator/status system caught it.
- Any place you used an AI coding tool (Cursor/Copilot/etc.) to generate boilerplate, and what you changed afterward.

## 13. What to Write in the "Improve for Production" Note

Suggested points to include:
- Real auth + per-user session storage instead of in-memory/anonymous sessions.
- Rate limiting and cost controls on LLM calls.
- Structured audit logging of every state transition (important for anything legal-adjacent).
- Human review step before a document is ever treated as "final."
- Replace mock/simple retry logic with a proper queue + exponential backoff and circuit breaker for the LLM provider.
- Internationalization if this were to support more than one legal jurisdiction (out of scope here, but worth naming as a known limitation).

---

## Summary Checklist

- [ ] Schema with field-level status (`missing`/`unconfirmed`/`confirmed`) + conditional rules
- [ ] Two-call LLM pattern (Extractor → validate → Responder)
- [ ] Validator layer with partial-patch acceptance and business-rule checks
- [ ] Mock LLM client + valid/ambiguous/malformed fixtures
- [ ] Conversation Engine with correction/diff handling
- [ ] Document Generator with placeholder rendering for incomplete state
- [ ] Two-pane UI: chat + (structured data view + draft document view), confidence indicators, progress counter, correction diff toast, persistent disclaimer
- [ ] REST API with typed, documented contract
- [ ] Focused automated test suite covering validator, engine, fixtures, generator, error paths
- [ ] README with setup, secrets handling, and how to switch mock ↔ real LLM
- [ ] AI log (prompts, iterations, a caught mistake)
- [ ] Production improvement notes
