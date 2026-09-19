# AI Implementation & Production Log

### Document Intake Assistant

_AI tooling: Google DeepMind Antigravity · Model: `gemini-3.1-Pro`_

This is a candid, detailed account of how AI tools (Google DeepMind Antigravity) were used to design, build, secure, and refactor the Document Intake Assistant. The core architecture — the dual-call extraction/response pipeline, the explicit state-value model, and the validator-as-safety-net pattern — was designed upfront; the AI was directed as an implementation engine and, for targeted phases, as a set of strictly constrained agent personas. This log records where AI output was correct, where it was wrong, exactly how prompts were iterated to fix it, and how agentic workflows were orchestrated for debugging, security, and refactoring work. An honest, detailed log is worth more than a padded one, so failures are documented alongside successes.

---

## 1. Core Architecture

### 1.1 LLM Provider & SDK

**Model:** `gemini-3.5-flash-lite` | **SDK:** `google-genai` (Python)

Gemini was chosen specifically for its `response_schema` support with Pydantic models. This makes the Extractor call structurally enforced rather than relying on parsing free-form JSON text, which is unreliable in practice.

### 1.2 The Dual-Call LLM Pattern

The first attempt used a single LLM call that extracted structured data and generated a conversational response in one JSON blob. This worked on simple inputs but hallucinated on complex turns — the model would say, for example, that it had "noted the executor is James, your brother," while the extraction patch it returned in the same response contained only `executor_name` and was missing `executor_relationship` entirely. The response text and the structured data it was supposed to be grounded in had silently diverged.

To eliminate this, the workload was explicitly split into two distinct, purpose-built calls:

- **The Extractor (structured data, temperature 0.1):** highly constrained, zero conversational output, optimized purely for deterministic JSON-schema adherence. It analyzes the user's raw text against the current `SessionState` and outputs a strict JSON patch of newly captured fields — nothing else.
- **The Responder (conversational tone, temperature 0.5):** sees only the validated state after the Extractor's patch has passed the business-rules validator. It identifies missing fields by priority order, factors in any ambiguities the validator raised, and generates a natural, empathetic response to guide the user to the next step.

Because the Responder is architecturally prevented from seeing raw, unvalidated user input, it cannot fabricate confirmations for data that was never actually captured. This split entirely eliminated the hallucination-in-conversation problem.

---

## 2. Advanced Prompt Engineering & Agentic Orchestration

Rather than generic, open-ended prompts (e.g. "build an app" or "fix the bug"), the AI was directed using specialized, strictly constrained agent personas, drawing on industry best practices from [Agentpedia's Agentic AI Rules](https://agentpedia.codes/rules/agentic-ai). Each persona defined the AI's reasoning framework, rules of engagement, and step-by-step methodology before any code was touched, so the AI acted as a senior engineering partner rather than a simple code generator.

### 2.1 Debugging Agent — Systematic Bug Hunter

Rather than asking the AI to "fix the bug," it was forced into a rigorous Systematic Bug Hunter persona: apply abductive reasoning, generate ranked hypotheses, and use a binary-search approach — with blind code changes explicitly forbidden until the root cause was confirmed.

- **Target:** a silent failure where contradictory fields submitted simultaneously (e.g. setting `has_children=False` and `children_names=["Tom"]` at once) bypassed the business rules engine.
- **Prompting strategy:** the AI was instructed to map the complete data flow of `SessionState` and pinpoint exactly where in the patch lifecycle validation was occurring, before writing any fix.
- **Result:** the AI traced the root cause — `_check_business_rules` was evaluating against the _previous_ state rather than the _proposed_ patch state — and surgically modified `validator.py` to pre-scan incoming patches for field dependencies (e.g. verifying `has_children` before accepting `children_names`) ahead of falling back to saved state. This resolved the edge case while preserving the integrity of the full 48-test suite.

### 2.2 Security Audit Agent — Vulnerability Detection

To move the app from MVP to production-ready, the AI was primed with an Expert Security Audit Agent persona, requiring a methodical OWASP Top 10 review, trust-boundary mapping, and a Severity × Likelihood risk assessment before any code changes — with the explicit instruction to assume all user input is hostile, and to specifically analyze API endpoint parameter binding, filesystem I/O, and the React DOM rendering lifecycle.

- **Critical — Stored XSS:** `StatePane.jsx` was passing user input straight into `dangerouslySetInnerHTML` to render the legal document text. The AI secured this by integrating `DOMPurify` into the HTML-rendering pipeline, sanitizing content before it reaches the DOM.
- **High — Path Traversal (LFI):** `backend/app/main.py` was concatenating the `session_id` URL parameter directly into file paths when loading sessions. The AI hardened `_load_session` by enforcing strict `uuid.UUID` parsing on incoming requests, so a malformed or malicious ID now returns a safe HTTP 404 instead of enabling arbitrary file reads.

### 2.3 Code Review Agent — Thorough & Constructive Reviewer

To pay down technical debt, a Refactoring & Code Review Agent persona was applied: identify code smells (Large Class, Feature Envy, Single Responsibility Principle violations) against DRY/SRP standards, require 100% test coverage before any change, and proceed only in atomic, incremental commits. The AI was strictly mandated to run the full pytest suite before and after every single file modification to guarantee zero behavioral change.

- **Frontend decomposition:** a monolithic ~300-line React component (`StatePane.jsx`) was sliced into focused, single-purpose components — `DataTab.jsx`, `DocumentTab.jsx`, and `FieldEditorRow.jsx` — with state passed cleanly via props.
- **Backend decoupling:** `main.py` was split by abstracting all filesystem I/O and state persistence into a dedicated `store.py`, then moving all endpoints into a cleanly separated `routes/sessions.py` using FastAPI's `APIRouter`.
- **Test-driven safety net:** because of the strict pre-refactor testing constraint, the AI actually surfaced and fixed two dormant, pre-existing test failures in `test_models.py` before it began refactoring at all — resulting in a clean baseline and a flawless deployment pipeline afterward.

---

## 3. Structuring State Over Free-Text

Instead of asking the AI to "handle state" ambiguously, it was explicitly directed to generate a Pydantic schema for the Personal Wishes Document using a dedicated `FieldValue` wrapper with four explicit states: `missing`, `unconfirmed`, `confirmed`, `not_applicable`.

The AI's first pass returned a basic schema using `Optional[str]` for every field. This was rejected: in a conversational system, `None` is ambiguous, since it conflates "not yet asked" with "user said it doesn't apply." Forcing the four-state `FieldValue` model instead ended up being the backbone of the entire conversational state machine — every later feature (ambiguity resolution, priority-ordered questioning, correction handling) was built on top of this distinction.

---

## 4. Development Timeline: Iteration, Failure, and Correction

### 4.1 Extractor Prompt — Iteration 1 (Too Strict)

First version instructed: _"Only extract what the user actually said — NEVER infer... If they say something vague, do NOT guess."_

**What broke:** tested with the input _"Maybe my sister"_, the model dropped it completely. Gemini Flash Lite is very literal: "do NOT guess" was interpreted as "discard uncertain input" rather than "don't fabricate values."

**The fix:** rewrote the rule to distinguish dropping data from flagging it: _"If it's vague or partially stated, you MUST STILL extract it with status 'unconfirmed'. Also return it as an ambiguity so the system asks a follow-up. Do not drop partial information."_

### 4.2 Extractor Prompt — Iteration 2 (Missing Context)

Short answers like "Yes" broke disambiguation — the model had no way to tell whether "Yes" meant `has_children=true` or `covers_worldwide_assets=true`, since both could plausibly be the field just asked about.

**The fix:** the prompt context was extended to dynamically inject the field most recently asked about (the "TARGET FIELD TO ASK ABOUT" / `last_asked_field`). This gave the LLM the exact context needed to resolve short answers deterministically, without building any additional stateful reasoning into the model itself.

### 4.3 Responder Prompt — Asking Multiple Questions

The initial Responder routinely asked two or three questions in a single turn. Users only ever answered one of them, which broke extraction on the next turn because the Extractor had no way to tell which question the reply was answering.

**The fix:** added an explicit constraint: _"Ask about ONE missing field at a time, following priority order."_

### 4.4 Validator Catching a Model Contradiction

**User message:** _"I have no kids, my son Tom is in school."_

The Extractor grabbed both `has_children=false` and `children_names=["Tom"]` and failed to flag the contradiction on its own. The hand-written business-rules validator caught the dependency failure, rejected the patch, and generated an internal ambiguity for the Responder to raise with the user. This was the clearest evidence in the whole project that a deterministic validator layer is mandatory alongside LLM output — prompting alone could not be trusted to reliably enforce this kind of cross-field business rule, so the rule (`children_names` cannot exist if `has_children` is false) was enforced in code rather than in the prompt.

### 4.5 Pytest Infrastructure Failures on Windows

**Asked:** write 48 unit tests using a `DummyLLMClient`.

**What broke:** "attempted relative import with no known parent package." The AI had forgotten `tests/__init__.py`. After adding that, `from app.main import app` broke separately, because a later mock import in the same run overwrote the module binding.

**The fix:** created the missing `__init__.py` and aliased imports (`from app import main as main_module`) to allow safe monkeypatching without clobbering the shared module binding.

### 4.6 Self-Correction & Refactoring Phase

Three architectural shortcuts were identified and fixed during final review:

1. **Fragile JSON parsing:** `json.loads()` crashed whenever the model accidentally wrapped its output in Markdown code fences. Fixed with a robust regex pre-parser that strips fencing before parsing.
2. **In-memory state loss:** `main.py` was storing session data in a global in-memory dict, which meant a server restart wiped every in-progress session. Refactored to a disk-backed JSON store (`sessions_data/`) so sessions survive restarts.
3. **Implicit routing in prompts:** delegating "which field to ask about next" to the LLM is an anti-pattern — it's a deterministic decision being made non-deterministically. `engine.py` was modified to calculate the `TARGET FIELD` explicitly in code and pass it into the prompt context, removing the routing decision from the LLM entirely.

---

## 5. Production Readiness & Cost Optimization

### 5.1 Cost-Aware Model Selection

Rather than defaulting to the heaviest, most expensive model available — a common trap in AI application development — the system was specifically architected to run on `gemini-3.5-flash-lite`. Because the Dual-Call architecture breaks the workload into small, highly focused micro-tasks (strict JSON extraction vs. simple response generation), a lightweight model performs the job flawlessly. Combined with the strict Pydantic schemas, this achieved highly accurate, complex extractions on a low-latency, low-cost model — demonstrating that robust system design and precise prompting trump raw model size.

### 5.2 Zero-Cost Deterministic Testing

Relying on live LLM calls for unit tests is slow, expensive, and flaky (non-deterministic by nature). To solve this, the LLM client was abstracted behind a common interface, and the AI was directed to build a `DummyLLMClient` that mocks structured JSON responses and is injected via dependency injection. This allows the full suite of 48 backend unit and integration tests — covering the conversational state machine, correction handling, and business-rule validation — to run instantly, deterministically, and for zero API cost on every Git push, keeping CI/CD robust and cheap.

---

## 6. Future Improvements for Enterprise Scale

If this application were migrating to a true enterprise-grade production environment, the following technical improvements would be prioritized next:

- **Persistence & data-tier migration:** replace the local JSON file store with a managed database — either a relational store such as PostgreSQL (via SQLAlchemy/SQLModel) for querying and schema migrations, or a managed NoSQL store such as Google Cloud Firestore or MongoDB for horizontal scaling, distributed locking, and concurrent state updates.
- **Latency & UX:** transition the HTTP POST endpoint to a WebSocket protocol and stream the LLM's response tokens directly to the UI, eliminating perceived latency and creating a more responsive, human-like chat experience.
- **Enhanced validation tooling:** refactor the LLM client to integrate a structured-extraction library such as Instructor, capitalizing on guaranteed schema enforcement and automatic JSON-validation retry loops to further harden the extraction pipeline against formatting errors.
- **Security & compliance:** implement OAuth2/JWT authentication for tenant isolation, and introduce pre-processing middleware to scrub PII (Personally Identifiable Information) before any payload enters the LLM context window.
- **Abuse prevention:** add IP-based rate limiting (via Redis or FastAPI middleware) on the `/api/sessions` endpoint to prevent denial-of-service attacks and API quota exhaustion.

---

## 7. Final Prompt Versions (Verbatim)

### Extractor System Prompt — Call A (Temperature 0.1)

```text
You are a precise data extraction assistant for a Personal Wishes
Document intake system.

Your job: extract structured field updates from the user's latest
message, given the current state of the document.

RULES:
1. Extract EVERY field mentioned in the user's message, even if it
   wasn't the field most recently asked about.
2. Only extract what the user actually said — NEVER infer, guess,
   or make up values.
3. If a statement is clear and unambiguous, mark it "confirmed".
   If it's inferred or partially stated, mark it "unconfirmed".
4. If the user's answer is vague, contradictory, or unclear, return
   it as an ambiguity — do NOT guess.
5. For boolean fields (has_children, covers_worldwide_assets), only
   accept clear yes/no — "maybe", "sort of", "I guess" are
   ambiguities.
6. If the user says "my brother James", extract BOTH
   executor_name="James" AND executor_relationship="brother".
7. If the user provides contradictory info (e.g., "no kids" and
   "my son Tom"), flag as an ambiguity.
```

### Responder System Prompt — Call B (Temperature 0.5)

```text
You are a warm, professional assistant helping someone create their
Personal Wishes Document.

RULES:
1. Acknowledge what was just captured, briefly.
2. Ask about ONE missing field at a time, following priority order.
3. Keep responses to 1-3 sentences. Be warm but concise.
4. NEVER state a fact about the user — only ask or confirm what
   they told you.
5. If there are ambiguities, ask for clarification instead of
   moving on.
6. If a correction was made, acknowledge the change naturally.
7. Remember this concerns sensitive subject matter — maintain a
   calm, respectful tone.
8. NEVER mention technical terms like "fields", "schema",
   "patches", or "status".
```
