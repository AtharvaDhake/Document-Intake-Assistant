"""
Abstract LLM Client Interface.

Two distinct responsibilities, never mixed:
  - extract(): structured data extraction from user message → patch
  - respond(): generate next conversational question/acknowledgement

Both real (Gemini) and mock implementations must follow this interface.
"""

from abc import ABC, abstractmethod

from ..models.patch import ExtractionResult, Ambiguity
from ..models.state import SessionFields


class LLMClient(ABC):

    @abstractmethod
    def extract(
        self,
        current_fields: SessionFields,
        user_message: str,
        last_asked_field: str | None,
    ) -> ExtractionResult:
        """
        Call A — Extractor.

        Given the current state, the user's latest message, and which field
        was most recently asked about, return a structured patch of proposed
        field updates plus any ambiguities.
        """
        ...

    @abstractmethod
    def respond(
        self,
        validated_fields: SessionFields,
        ambiguities: list[Ambiguity],
        missing_fields: list[str],
        corrections: list[dict] | None = None,
    ) -> str:
        """
        Call B — Responder.

        Given the validated (post-patch) state, any ambiguities that need
        clarifying, and the list of still-missing fields, generate the next
        natural-language message for the user.
        """
        ...
