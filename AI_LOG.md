# AI Log: Building the Document Intake Assistant

This log details how AI tools (Google DeepMind's Antigravity coding assistant) were used to build this project. Rather than a polished PR document, this is a candid recount of the iterations, the prompts used, and specifically where the AI got things wrong and had to be corrected.

## 1. Project Initialization & Scaffolding
**What was asked:** "Generate a Pydantic schema for a Personal Wishes Document that matches the requirements, and set up a basic FastAPI router."
**What came back:** A solid initial schema, but it used `Optional[str]` for everything.
**The Correction:** I rejected the generic `Optional` abstraction. In a conversational system, "missing" is fundamentally different from "not applicable". I had the AI implement a custom `FieldValue` wrapper to explicitly track states (`missing`, `unconfirmed`, `confirmed`, `not_applicable`).

## 2. The "Sister" Bug (LLM Strictness)
**What was asked:** "Set up the Gemini Extractor prompt to parse user intent into the structured patch schema."
**What came back:** The initial prompt included the instruction: *"Only extract what the user actually said — NEVER infer, guess, or make up values. If they say something vague, do NOT guess."*
**The Correction:** When testing with the input `"Maybe my sister"`, the AI completely dropped the data instead of patching it. Because Gemini 3.5 Flash Lite is extremely literal, "do NOT guess" caused it to discard partial information entirely. I had to explicitly correct the prompt to ensure it still extracts partial statements as `unconfirmed` instead of dropping them entirely.

## 3. Pytest Relative Import Failures
**What was asked:** "Write a suite of unit tests for the validator and engine logic using a dummy LLM client, and run pytest."
**What came back:** A suite of 48 unit tests that looked perfectly correct on paper.
**The Correction:** Running `pytest` on Windows failed immediately with `attempted relative import with no known parent package`. The AI had generated the test files in `backend/tests/` but forgot to make it a package. I had to instruct the AI to create `tests/__init__.py` and use absolute imports `from tests.dummy_client` to fix the module resolution path.

## 4. FastAPI Module Shadowing in Tests
**What was asked:** "Add integration tests for the API endpoints in `test_api.py`."
**What came back:** The AI wrote `from app.main import app` at the top of the file, but later in a test function wrote `import app.main` to monkeypatch the LLM factory (`app.main._create_llm_client = ...`).
**The Correction:** The second import overrode the global `app` variable, binding it to the module itself instead of the FastAPI instance, which broke `TestClient(app)`. I had the AI fix this scoping bug by importing the module with an alias: `from app import main as main_module`.

---

## LLM Provider

**Model:** Gemini 3.5 Flash Lite (`gemini-3.5-flash-lite`)  
**SDK:** `google-genai` (Python)  
**Provider selection:** Gemini was chosen for its structured output support (`response_schema` with Pydantic models), which makes the Extractor call far more reliable than parsing free-form JSON text.

## Prompts — Final Versions

### Extractor System Prompt (Call A)

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

### Responder System Prompt (Call B)

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

## Prompt Iterations

### Iteration 1 — Combined Extraction + Response (abandoned)

Initial approach: single LLM call that extracts data AND generates a response in one JSON blob. **Problem:** The model frequently "hallucinated" field values in the conversational response that weren't actually in its structured extraction. For example, it would say "I've noted that your executor is James, your brother" in the response text, but the extraction patch only had `executor_name` without `executor_relationship`. The user sees the text and believes both were captured, but the structured state only has one.

**Fix:** Split into two calls. The Responder only sees validated state, never its own raw extraction output. This completely eliminated the hallucination-in-conversation problem.

### Iteration 2 — Extractor without `last_asked_field` (improved)

Early Extractor prompt didn't receive the `last_asked_field` context. This caused problems with short answers like "Yes" — the model couldn't tell if "Yes" meant `has_children=true` or `covers_worldwide_assets=true`. Adding `last_asked_field` to the prompt disambiguated short answers without complex context tracking.

### Iteration 3 — Responder asking multiple questions (constrained)

Initially the Responder would ask 2-3 questions at once ("What's your name? And do you have an address?"). This made extraction harder on the next turn because the user might answer only one. Added explicit constraint: "Ask about ONE missing field at a time."

## Example: Model Error Caught by Validator

**User message:** "I have no kids, my son Tom is in school."

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

**What happened:** The model extracted both `has_children=false` AND `children_names=["Tom"]` — a contradiction it didn't flag. Our business rule validator caught this: `children_names` provided but `has_children` is `false` → rejected the `children_names` patch item and generated an ambiguity. The Responder then asked the user to clarify: "I want to make sure I understand — do you have children?"

This demonstrates why structural enforcement (validator layer) matters more than prompt instructions alone. The prompt says "flag contradictions as ambiguities," but the model failed to do so. The validator caught it anyway.
