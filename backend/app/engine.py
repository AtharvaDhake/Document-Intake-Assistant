"""
Conversation Engine — orchestrates one turn of conversation.

Flow per turn:
  1. Call Extractor → get proposed patches + ambiguities
  2. Validate patches via Validator (partial acceptance)
  3. Apply accepted patches to state (with correction detection)
  4. Handle dependent fields (has_children=false → children_names=not_applicable)
  5. Call Responder with validated state + context
  6. Append to conversation log
  7. Check completion state

Includes retry logic for malformed LLM output.
"""

import json
import structlog
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential

from .llm.llm_client import LLMClient
from .models.state import SessionState, ConversationEntry, FIELD_PRIORITY
from .models.fields import FieldValue, FieldStatus
from .models.patch import ExtractionResult, PatchItem
from .validation.validator import validate_patch, ValidationResult
from .document_generator import generate_document

logger = structlog.get_logger()

# Opening message for new sessions
OPENING_MESSAGE = (
    "Hello! I'm here to help you create your Personal Wishes Document. "
    "I'll ask you a few questions to gather the information we need. "
    "You can answer in any order, and correct anything at any time.\n\n"
    "Let's start — could you please tell me your full name?"
)

FALLBACK_MESSAGE = (
    "I'm sorry, I didn't quite catch that. Could you rephrase what you meant?"
)


class ConversationEngine:
    """Orchestrates the turn-by-turn conversation flow."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def start_session(self, state: SessionState) -> str:
        """Initialize a new session with the opening message."""
        state.conversation_log.append(ConversationEntry(
            role="assistant",
            content=OPENING_MESSAGE,
        ))
        return OPENING_MESSAGE

    def process_turn(
        self, state: SessionState, user_message: str
    ) -> dict:
        """
        Process one user message through the full pipeline.

        Returns a dict with:
          - assistant_message: str
          - patch_applied: list of applied patch dicts
          - ambiguities: list of ambiguity dicts
          - corrections: list of correction dicts
        """
        turn_number = len(state.conversation_log) + 1

        # Record user message
        state.conversation_log.append(ConversationEntry(
            role="user", content=user_message,
        ))

        # Determine what was last asked about
        last_asked = state.fields.next_missing_field()

        extraction = self._safe_extract(state, user_message, last_asked)
        validation = validate_patch(extraction.patch, state)
        all_ambiguities = list(extraction.ambiguities) + list(validation.ambiguities)

        applied_patches = []
        for item in validation.accepted:
            fv = FieldValue(
                value=item.value,
                status=FieldStatus(item.status),
                source_turn=turn_number,
                last_updated=datetime.now(timezone.utc),
            )
            setattr(state.fields, item.field, fv)
            
            applied_patches.append({
                "field": item.field,
                "value": item.value,
                "status": item.status,
                "reasoning": item.reasoning,
            })

        for item, reason in validation.rejected:
            logger.warning(f"Rejected patch: {item.field}={item.value} — {reason}")

        self._handle_dependent_fields(state)

        correction_dicts = [
            {"field": c.field, "old_value": c.old_value, "new_value": c.new_value}
            for c in validation.corrections
        ]

        for c in correction_dicts:
            state.corrections.append(c)

        target_field = state.fields.next_missing_field()
        missing = [target_field] if target_field else []
        assistant_message = self._safe_respond(
            state, all_ambiguities, missing, correction_dicts,
        )

        state.conversation_log.append(ConversationEntry(
            role="assistant", content=assistant_message,
        ))
        state.updated_at = datetime.now(timezone.utc)

        if state.fields.is_complete():
            state.status = "ready_for_review"

        return {
            "assistant_message": assistant_message,
            "patch_applied": applied_patches,
            "ambiguities": [
                {"field": a.field, "reason": a.reason} for a in all_ambiguities
            ],
            "corrections": correction_dicts,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def _extract_with_retry(self, state, user_message, last_asked):
        return self.llm.extract(state.fields, user_message, last_asked)

    def _safe_extract(
        self, state: SessionState, user_message: str, last_asked: str | None,
    ) -> ExtractionResult:
        try:
            return self._extract_with_retry(state, user_message, last_asked)
        except Exception as e:
            logger.error(f"Extraction failed after retries: {e}")
            return ExtractionResult(patch=[], ambiguities=[])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def _respond_with_retry(self, state, ambiguities, missing, corrections):
        return self.llm.respond(state.fields, ambiguities, missing, corrections)

    def _safe_respond(
        self, state, ambiguities, missing, corrections,
    ) -> str:
        try:
            return self._respond_with_retry(
                state, ambiguities, missing, corrections,
            )
        except Exception as e:
            logger.error(f"Responder failed after retries: {e}")
            return FALLBACK_MESSAGE

    def _handle_dependent_fields(self, state: SessionState) -> None:
        """
        Handle field dependencies:
        - If has_children is confirmed false, mark children_names as not_applicable.
        - If has_children is confirmed true, ensure children_names is not not_applicable.
        """
        hc = state.fields.has_children
        cn = state.fields.children_names

        if (hc.status == FieldStatus.CONFIRMED and hc.value is False
                and cn.status != FieldStatus.NOT_APPLICABLE):
            state.fields.children_names = FieldValue(
                status=FieldStatus.NOT_APPLICABLE,
            )

        if (hc.status == FieldStatus.CONFIRMED and hc.value is True
                and cn.status == FieldStatus.NOT_APPLICABLE):
            state.fields.children_names = FieldValue(
                status=FieldStatus.MISSING,
            )

