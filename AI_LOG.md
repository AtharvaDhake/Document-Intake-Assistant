# AI Log: Building the Document Intake Assistant

This is a candid account of where AI tools (Google DeepMind Antigravity) were used during development, including where the first outputs were wrong and what had to be corrected. An honest, shorter log is worth more than a padded one.

---

## LLM Provider

**Model:** Gemini 3.5 Flash Lite (`gemini-3.5-flash-lite`)
**SDK:** `google-genai` (Python)

Gemini was chosen specifically for its `response_schema` support with Pydantic models. This makes the Extractor call structurally enforced rather than relying on parsing free-form JSON text, which is unreliable in practice.

---

## Development Timeline: Where AI Was Used and Where It Failed

### 1. Initial Schema Design

**Asked:** Generate a Pydantic schema for a Personal Wishes Document and a basic FastAPI router.

**What came back:** A working schema using `Optional[str]` for every field.

**The problem:** In a conversational system, `None` is ambiguous — it conflates "not yet asked" with "user said it doesn't apply". I rejected this and had the AI implement a `FieldValue` wrapper tracking explicit states: `missing`, `unconfirmed`, `confirmed`, `not_applicable`. This distinction ended up being the backbone of the entire state machine.

---

### 2. The Single-Call LLM Approach (Abandoned)

**Asked:** Build a single LLM call that extracts structured data and generates a response in one JSON blob.

**What came back:** It worked on simple inputs. On complex turns it hallucinated. For example, the model would say *"I've noted your executor is James, your brother"* in the response text, but the extraction patch only contained `executor_name` — `executor_relationship` wasn't there. The user sees the response and believes both were captured. The state only has one.

**The fix:** Split into two calls — Extractor and Responder. The Responder only ever sees *validated* state, never the raw extraction output. This completely eliminated the hallucination-in-conversation problem.

---

### 3. Extractor Prompt — Iteration 1 (Too Strict)

**First version of the Extractor prompt included:**
```
Only extract what the user actually said — NEVER infer, guess, or make up values.
If they say something vague, do NOT guess.
```

**What broke:** Tested with `"Maybe my sister"` as input for executor. The model completely dropped it — extracted nothing. Gemini 3.5 Flash Lite is very literal: "do NOT guess" was interpreted as "discard uncertain input". The field stayed `missing` and the system never followed up.

**The fix:** Rewrote the rule to distinguish between *dropping* data and *flagging* it:
```
If a statement is clear and unambiguous, mark it "confirmed".
If it's vague or partially stated (e.g. "maybe my sister"),
you MUST STILL extract it with status "unconfirmed".
Also return it as an ambiguity so the system asks a follow-up.
Do not drop partial information.
```

---

### 4. Extractor Prompt — Iteration 2 (Missing Context)

The early Extractor didn't receive a `last_asked_field` parameter. Short answers like `"Yes"` broke disambiguation — the model couldn't tell if Yes meant `has_children=true` or `covers_worldwide_assets=true`.

**Fix:** Added `last_asked_field` to the prompt context. Solved without any complex state tracking.

---

### 5. Responder Prompt — Asking Multiple Questions

The initial Responder would ask 2-3 questions in a single turn: *"What's your name? And do you have an address?"*. This made extraction on the next turn unreliable because users often answered only one.

**Fix:** Added an explicit constraint: *"Ask about ONE missing field at a time."*

---

### 6. Validator Catching a Model Contradiction

**User message:** `"I have no kids, my son Tom is in school."`

**Extractor output:**
```json
{
  "patch": [
    {"field": "has_children", "value": false, "status": "confirmed"},
    {"field": "children_names", "value": ["Tom"], "status": "confirmed"}
  ],
  "ambiguities": []
}
```

The prompt explicitly says to flag contradictions as ambiguities. The model didn't. It extracted both and left `ambiguities` empty.

The business rule validator caught it: `children_names` cannot be set when `has_children` is `false`. It rejected the `children_names` patch item, generated an ambiguity internally, and the Responder asked: *"I want to make sure I understand — do you have children?"*

This is the clearest demonstration of why the validator layer exists. Prompt instructions alone are not reliable enough for critical data integrity rules.

---

### 7. Pytest Infrastructure Failures on Windows

**Asked:** Write 48 unit tests using a `DummyLLMClient` and run them.

**What broke immediately:** `attempted relative import with no known parent package`. The AI generated tests in `backend/tests/` without creating `tests/__init__.py`, so Python didn't treat it as a package.

**Fix:** Created `tests/__init__.py` and switched all imports to absolute (`from tests.dummy_client import ...`).

**Second breakage in `test_api.py`:** The file had `from app.main import app` at the top, then later `import app.main` inside a test function to monkeypatch the LLM factory. The second import bound the name `app` to the module object, not the FastAPI instance. `TestClient(app)` silently broke.

**Fix:** Alias the module import: `from app import main as main_module`, then patch `main_module._create_llm_client`.

---

### 8. Self-Correction & Refactoring Phase

During a final review pass before submission, three architectural shortcuts were identified and fixed to harden the system:

1. **Fragile JSON Parsing:** The `json.loads()` call in `gemini_client.py` was vulnerable to the model accidentally outputting Markdown backticks (````json ... ````), which would cause a crash.
   *Fix:* Implemented a robust markdown-stripping pre-parser before deserialization.
2. **In-Memory State Loss:** `main.py` was storing session data in a global Python dictionary.
   *Fix:* Refactored `main.py` to use a localized, disk-backed JSON store (`sessions_data/`). This ensures sessions survive server restarts and allows for easier migration to a real DB volume later.
3. **Implicit Routing in Prompts:** The Responder prompt was given a list of all missing fields and told to "Ask about ONE missing field...". Delegating application routing to an LLM is an anti-pattern.
   *Fix:* Modified `engine.py` to deterministically calculate the *target field* and pass it directly to the prompt context (`TARGET FIELD TO ASK ABOUT: ...`), removing the decision-making burden from the LLM entirely.

---

## Final Prompt Versions (Verbatim)

### Extractor System Prompt (Call A — Temperature 0.1)

```
You are a precise data extraction assistant for a Personal Wishes Document intake system.

Your job: extract structured field updates from the user's latest message, given the current state of the document.

RULES:
1. Extract EVERY field mentioned in the user's message, even if it wasn't the field most recently asked about.
2. Only extract what the user actually said — NEVER infer, guess, or make up values.
3. If a statement is clear and unambiguous, mark it "confirmed". If it's inferred or partially stated, mark it "unconfirmed".
4. If the user's answer is vague, contradictory, or unclear, return it as an ambiguity — do NOT guess.
5. For boolean fields (has_children, covers_worldwide_assets), only accept clear yes/no — "maybe", "sort of", "I guess" are ambiguities.
6. If the user says "my brother James", extract BOTH executor_name="James" AND executor_relationship="brother".
7. If the user provides contradictory info (e.g., "no kids" and "my son Tom"), flag as an ambiguity.
```

### Responder System Prompt (Call B — Temperature 0.5)

```
You are a warm, professional assistant helping someone create their Personal Wishes Document.

RULES:
1. Acknowledge what was just captured, briefly.
2. Ask about ONE missing field at a time, following priority order.
3. Keep responses to 1-3 sentences. Be warm but concise.
4. NEVER state a fact about the user — only ask or confirm what they told you.
5. If there are ambiguities, ask for clarification instead of moving on.
6. If a correction was made, acknowledge the change naturally.
7. Remember this concerns sensitive subject matter — maintain a calm, respectful tone.
8. NEVER mention technical terms like "fields", "schema", "patches", or "status".
```

---

## What Was Not AI-Assisted

- The decision to use two separate LLM calls (that came from observing the hallucination bug firsthand, not from a prompt)
- The field-level confidence state model (`FieldValue` wrapper) — the AI's first output was wrong, this was a deliberate design correction
- The validator business rules — written by hand to be deterministic and testable regardless of LLM output

