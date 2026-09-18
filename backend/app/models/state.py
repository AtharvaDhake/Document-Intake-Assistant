import uuid
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field

from .fields import FieldValue, FieldStatus

REQUIRED_FIELDS = {
    "full_name", "home_address", "covers_worldwide_assets",
    "has_children", "executor_name", "executor_relationship",
}

FIELD_PRIORITY = [
    "full_name",
    "home_address",
    "has_children",
    "children_names",
    "covers_worldwide_assets",
    "executor_name",
    "executor_relationship",
    "specific_gifts",
    "additional_wishes",
]


class ConversationEntry(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionFields(BaseModel):
    full_name: FieldValue[str] = Field(default_factory=FieldValue)
    home_address: FieldValue[str] = Field(default_factory=FieldValue)
    covers_worldwide_assets: FieldValue[bool] = Field(default_factory=FieldValue)
    has_children: FieldValue[bool] = Field(default_factory=FieldValue)
    children_names: FieldValue[list[str]] = Field(default_factory=FieldValue)
    executor_name: FieldValue[str] = Field(default_factory=FieldValue)
    executor_relationship: FieldValue[str] = Field(default_factory=FieldValue)
    specific_gifts: FieldValue[list[str]] = Field(default_factory=FieldValue)
    additional_wishes: FieldValue[str] = Field(default_factory=FieldValue)

    def as_dict(self) -> dict[str, FieldValue]:
        return {name: getattr(self, name) for name in type(self).model_fields}

    def missing_fields(self) -> list[str]:
        return [
            name for name, fv in self.as_dict().items()
            if fv.status == FieldStatus.MISSING
        ]

    def progress(self) -> tuple[int, int]:
        fields = self.as_dict()
        total = sum(1 for f in fields.values() if f.status != FieldStatus.NOT_APPLICABLE)
        captured = sum(
            1 for f in fields.values()
            if f.status in (FieldStatus.CONFIRMED, FieldStatus.UNCONFIRMED)
        )
        return captured, total

    def is_complete(self) -> bool:
        entries = self.as_dict()
        for name in FIELD_PRIORITY:
            status = entries[name].status
            if status not in (FieldStatus.CONFIRMED, FieldStatus.NOT_APPLICABLE):
                return False
        return True

    def next_missing_field(self) -> str | None:
        entries = self.as_dict()
        for name in FIELD_PRIORITY:
            fv = entries[name]
            if fv.status == FieldStatus.MISSING:
                return name
            if fv.status == FieldStatus.UNCONFIRMED:
                return name
        return None


class SessionState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fields: SessionFields = Field(default_factory=SessionFields)
    conversation_log: list[ConversationEntry] = Field(default_factory=list)
    corrections: list[dict] = Field(default_factory=list)
    status: str = "in_progress"
