# AI Log: Building the Document Intake Assistant

This log details how AI tools (Google DeepMind's Antigravity coding assistant) were used to build this project. Rather than a polished PR document, this is a candid recount of the iterations, the prompts used, and specifically where the AI got things wrong and had to be corrected.

## 1. Project Initialization & Scaffolding
**What was asked:** "Generate a Pydantic schema for a Personal Wishes Document that matches the requirements, and set up a basic FastAPI router."
**What came back:** A solid initial schema, but it used `Optional[str]` for everything.
**The Correction:** I rejected the generic `Optional` abstraction. In a conversational system, "missing" is fundamentally different from "not applicable". I had the AI implement a custom `FieldValue` wrapper to explicitly track states (`missing`, `unconfirmed`, `confirmed`, `not_applicable`).

## 2. The "Sister" Bug (LLM Strictness)
**What was asked:** "Set up the Gemini Extractor prompt to parse user intent into the structured patch schema."
**What came back:** The initial prompt included the instruction: *"Only extract what the user actually said — NEVER infer, guess, or make up values. If they say something vague, do NOT guess."*
**The Correction:** When testing with the input `"Maybe my sister"`, the AI completely dropped the data instead of patching it. Because Gemini 3.5 Flash Lite is extremely literal, "do NOT guess" caused it to discard partial information entirely. I had to explicitly correct the prompt: *"If the user's answer is vague, ALSO return it as an ambiguity. Do not drop partial information — extract it as unconfirmed AND flag the ambiguity."*

## 3. Pytest Relative Import Failures
**What was asked:** "Write a suite of unit tests for the validator and engine logic using a dummy LLM client, and run pytest."
**What came back:** A suite of 48 unit tests that looked perfectly correct on paper.
**The Correction:** Running `pytest` on Windows failed immediately with `attempted relative import with no known parent package`. The AI had generated the test files in `backend/tests/` but forgot to make it a package. I had to instruct the AI to create `tests/__init__.py` and use absolute imports `from tests.dummy_client` to fix the module resolution path.

## 4. FastAPI Module Shadowing in Tests
**What was asked:** "Add integration tests for the API endpoints in `test_api.py`."
**What came back:** The AI wrote `from app.main import app` at the top of the file, but later in a test function wrote `import app.main` to monkeypatch the LLM factory (`app.main._create_llm_client = ...`).
**The Correction:** The second import overrode the global `app` variable, binding it to the module itself instead of the FastAPI instance, which broke `TestClient(app)`. I had the AI fix this scoping bug by importing the module with an alias: `from app import main as main_module`.

## Core Prompts (Final vs. Earlier Iterations)

### Extractor Prompt

**Earlier Iteration (Failed on vague inputs):**
> You are a precise data extraction assistant...
> Only extract what the user actually said — NEVER infer, guess, or make up values. If they say something vague, do NOT guess.
> Return a JSON object with "patch" and "ambiguities".

**Final Version:**
> You are a precise data extraction assistant for a Personal Wishes Document intake system.
> Your job: extract structured field updates from the user's latest message, given the current state of the document.
> RULES:
> 1. Extract EVERY field mentioned in the user's message, even if it wasn't the field most recently asked about.
> 2. Only extract what the user actually said — NEVER infer, guess, or make up values.
> 3. If a statement is clear and unambiguous, mark it "confirmed". If it's vague, inferred, or partially stated (e.g. "maybe my sister"), you MUST STILL extract the field with status "unconfirmed".
> 4. If the user's answer is vague or unclear, ALSO return it as an ambiguity. Do not drop partial information — extract it as unconfirmed AND flag the ambiguity so the system can ask a follow-up.
> 5. For boolean fields (has_children, covers_worldwide_assets), only accept clear yes/no — "maybe", "sort of", "I guess" are ambiguities (do not patch booleans unless clear).
> 6. If the user says "my brother James", extract BOTH executor_name="James" AND executor_relationship="brother".
> 7. If the user provides contradictory info, extract as unconfirmed AND flag as an ambiguity.
> VALID FIELDS: full_name, home_address, covers_worldwide_assets, has_children, children_names, executor_name, executor_relationship, specific_gifts, additional_wishes
> TYPE RULES: [omitted for brevity]
> Return a JSON object with "patch" (array of updates) and "ambiguities" (array of unclear items).

### Responder Prompt

**Earlier Iteration (Too robotic):**
> Acknowledge the user. Ask for the next missing field in this order: full_name, home_address...
> Keep it under 2 sentences. Do not mention the state.

**Final Version:**
> You are a warm, professional assistant helping someone create their Personal Wishes Document.
> RULES:
> 1. Acknowledge what was just captured, briefly.
> 2. Ask about ONE missing field at a time, following this priority: full_name, home_address, has_children, children_names (if applicable), covers_worldwide_assets, executor_name, executor_relationship, specific_gifts, additional_wishes.
> 3. Keep responses to 1-3 sentences. Be warm but concise.
> 4. NEVER state a fact about the user — only ask or confirm what they told you.
> 5. If there are ambiguities, ask for clarification instead of moving on.
> 6. If a correction was made, acknowledge the change naturally.
> 7. If all fields are complete, congratulate and tell them the document is ready for review.
> 8. Remember this concerns sensitive subject matter — maintain a calm, respectful tone.
> 9. NEVER mention technical terms like "fields", "schema", "patches", or "status".
