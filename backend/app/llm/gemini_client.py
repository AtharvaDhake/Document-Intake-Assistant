"""
Real LLM Client — Gemini 3.5 Flash Lite via google-genai SDK.

Two calls per turn:
  Call A (Extractor): structured JSON output, temperature 0.1
  Call B (Responder): natural language, temperature 0.5
"""

import json
import logging

from google import genai
from google.genai import types
from pydantic import BaseModel, Field as PydanticField
from typing import Optional

from .llm_client import LLMClient
from ..models.patch import ExtractionResult, PatchItem, Ambiguity
from ..models.state import SessionFields, FIELD_PRIORITY
from ..models.fields import FieldStatus

logger = logging.getLogger(__name__)


# ── Pydantic models for structured output ────────────────────────────

class PatchItemSchema(BaseModel):
    field: str = PydanticField(description="The field name being updated")
    value: object = PydanticField(description="The extracted value")
    status: str = PydanticField(description="'confirmed' or 'unconfirmed'")
    reasoning: str = PydanticField(description="Brief explanation for this extraction")


class AmbiguitySchema(BaseModel):
    field: str = PydanticField(description="The field that is ambiguous")
    reason: str = PydanticField(description="Why it is ambiguous")


class ExtractionResultSchema(BaseModel):
    patch: list[PatchItemSchema] = PydanticField(
        default_factory=list,
        description="List of field updates extracted from the user's message"
    )
    ambiguities: list[AmbiguitySchema] = PydanticField(
        default_factory=list,
        description="List of fields where the answer was ambiguous or contradictory"
    )


# ── System prompts ───────────────────────────────────────────────────

EXTRACTOR_SYSTEM_PROMPT = """You are a precise data extraction assistant for a Personal Wishes Document intake system.

Your job: extract structured field updates from the user's latest message, given the current state of the document.

RULES:
1. Extract EVERY field mentioned in the user's message, even if it wasn't the field most recently asked about.
2. Only extract what the user actually said — NEVER infer, guess, or make up values.
3. If a statement is clear and unambiguous, mark it "confirmed". If it's vague, inferred, or partially stated (e.g. "maybe my sister"), you MUST STILL extract the field with status "unconfirmed".
4. If the user's answer is vague or unclear, ALSO return it as an ambiguity. Do not drop partial information — extract it as unconfirmed AND flag the ambiguity so the system can ask a follow-up.
5. For boolean fields (has_children, covers_worldwide_assets), only accept clear yes/no — "maybe", "sort of", "I guess" are ambiguities (do not patch booleans unless clear).
6. If the user says "my brother James", extract BOTH executor_name="James" AND executor_relationship="brother".
7. If the user provides contradictory info, extract as unconfirmed AND flag as an ambiguity.

VALID FIELDS: full_name, home_address, covers_worldwide_assets, has_children, children_names, executor_name, executor_relationship, specific_gifts, additional_wishes

TYPE RULES:
- full_name, home_address, executor_name, executor_relationship, additional_wishes: string
- covers_worldwide_assets, has_children: boolean (true/false)
- children_names, specific_gifts: array of strings

Return a JSON object with "patch" (array of updates) and "ambiguities" (array of unclear items)."""

RESPONDER_SYSTEM_PROMPT = """You are a warm, professional assistant helping someone create their Personal Wishes Document.

RULES:
1. Acknowledge what was just captured, briefly.
2. Ask about the specific TARGET FIELD provided in the context below. Do not ask about other fields.
3. Keep responses to 1-3 sentences. Be warm but concise.
4. NEVER state a fact about the user — only ask or confirm what they told you.
5. If there are ambiguities, ask for clarification instead of moving on.
6. If a correction was made, acknowledge the change naturally.
7. If all fields are complete, congratulate and tell them the document is ready for review.
8. Remember this concerns sensitive subject matter — maintain a calm, respectful tone.
9. NEVER mention technical terms like "fields", "schema", "patches", or "status"."""


class GeminiLLMClient(LLMClient):
    """Real Gemini 3.5 Flash Lite implementation."""

    def __init__(self, api_key: str, model: str = "gemini-3.5-flash-lite"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def _fields_summary(self, fields: SessionFields) -> str:
        """Create a compact summary of current field states for the LLM."""
        entries = fields.as_dict()
        lines = []
        for name in FIELD_PRIORITY:
            fv = entries[name]
            if fv.status == FieldStatus.CONFIRMED:
                lines.append(f"  {name}: {fv.value} (confirmed)")
            elif fv.status == FieldStatus.UNCONFIRMED:
                lines.append(f"  {name}: {fv.value} (unconfirmed — needs verification)")
            elif fv.status == FieldStatus.NOT_APPLICABLE:
                lines.append(f"  {name}: N/A")
            else:
                type_hint = "string"
                if name in ("has_children", "covers_worldwide_assets"):
                    type_hint = "boolean (true or false)"
                elif name in ("children_names", "specific_gifts"):
                    type_hint = "array of strings"
                lines.append(f"  {name} ({type_hint}): [missing]")
        return "\n".join(lines)

    def extract(
        self,
        current_fields: SessionFields,
        user_message: str,
        last_asked_field: str | None,
    ) -> ExtractionResult:
        state_summary = self._fields_summary(current_fields)

        prompt = (
            f"CURRENT DOCUMENT STATE:\n{state_summary}\n\n"
            f"LAST FIELD ASKED ABOUT: {last_asked_field or 'none (opening)'}\n\n"
            f"USER'S MESSAGE: \"{user_message}\"\n\n"
            f"Extract all field updates from this message. Return JSON only."
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=EXTRACTOR_SYSTEM_PROMPT,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=ExtractionResultSchema,
            ),
        )

        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        payload = json.loads(text.strip())
        
        patch_items = [
            PatchItem(
                field=p["field"],
                value=p["value"],
                status=p["status"],
                reasoning=p.get("reasoning"),
            )
            for p in payload.get("patch", [])
        ]
        ambiguity_items = [
            Ambiguity(field=a["field"], reason=a["reason"])
            for a in payload.get("ambiguities", [])
        ]
        return ExtractionResult(patch=patch_items, ambiguities=ambiguity_items)

    def respond(
        self,
        validated_fields: SessionFields,
        ambiguities: list[Ambiguity],
        missing_fields: list[str],
        corrections: list[dict] | None = None,
    ) -> str:
        state_summary = self._fields_summary(validated_fields)
        context_parts = [f"CURRENT DOCUMENT STATE:\n{state_summary}"]

        if corrections:
            corr_text = ", ".join(
                f"{c['field']}: \"{c['old_value']}\" → \"{c['new_value']}\""
                for c in corrections
            )
            context_parts.append(f"CORRECTIONS JUST MADE: {corr_text}")

        if ambiguities:
            amb_text = ", ".join(
                f"{a.field}: {a.reason}" for a in ambiguities
            )
            context_parts.append(f"AMBIGUITIES TO CLARIFY: {amb_text}")

        if missing_fields:
            target_field = missing_fields[0]
            context_parts.append(f"TARGET FIELD TO ASK ABOUT: {target_field}")
            context_parts.append(f"OTHER MISSING FIELDS (do not ask about these yet): {', '.join(missing_fields[1:])}")
        else:
            context_parts.append("ALL REQUIRED FIELDS ARE COMPLETE.")

        prompt = "\n\n".join(context_parts) + "\n\nGenerate your response to the user."

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=RESPONDER_SYSTEM_PROMPT,
                temperature=0.5,
                max_output_tokens=300,
            ),
        )
        return response.text.strip()


