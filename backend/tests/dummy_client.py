import re
from app.llm.llm_client import LLMClient
from app.models.patch import ExtractionResult, PatchItem, Ambiguity
from app.models.state import SessionFields

class DummyLLMClient(LLMClient):
    def extract(self, current_fields, user_message: str, last_asked_field: str | None) -> ExtractionResult:
        msg = user_message.lower()
        patch = []
        ambiguities = []

        if "jane smith" in msg or "sarah smith" in msg:
            val = "Jane Smith" if "jane smith" in msg else "Sarah Smith"
            patch.append(PatchItem(field="full_name", value=val, status="confirmed", reasoning="name"))
        if "12 elm street" in msg or "10 downing street" in msg:
            val = "12 Elm Street" if "12 elm street" in msg else "10 Downing Street"
            patch.append(PatchItem(field="home_address", value=val, status="confirmed", reasoning="address"))
        if "no kids" in msg or "don't have children" in msg or "don't have any kids" in msg:
            patch.append(PatchItem(field="has_children", value=False, status="confirmed", reasoning="no kids"))
            if "son tom" in msg:
                patch.pop()
                ambiguities.append(Ambiguity(field="has_children", reason="contradictory"))
        elif "yes, i have two children" in msg:
            patch.append(PatchItem(field="has_children", value=True, status="confirmed", reasoning="has kids"))
        if "worldwide" in msg:
            patch.append(PatchItem(field="covers_worldwide_assets", value=True, status="confirmed", reasoning="worldwide"))
        if "james" in msg and "brother" in msg:
            patch.append(PatchItem(field="executor_relationship", value="brother", status="confirmed", reasoning="rel"))
            patch.append(PatchItem(field="executor_name", value="James", status="confirmed", reasoning="name"))
        if "no specific gifts" in msg:
            patch.append(PatchItem(field="specific_gifts", value=[], status="confirmed", reasoning="no gifts"))
        if "nothing else" in msg:
            patch.append(PatchItem(field="additional_wishes", value="", status="confirmed", reasoning="no wishes"))
            
        if "sort of" in msg:
            ambiguities.append(Ambiguity(field="has_children", reason="vague"))
            
        return ExtractionResult(patch=patch, ambiguities=ambiguities)

    def respond(self, validated_fields, ambiguities, missing_fields, corrections) -> str:
        if validated_fields.is_complete():
            return "ready for review"
        return "Could you please tell me your full name?"
