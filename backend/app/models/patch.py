from typing import Any, Literal
from pydantic import BaseModel


class PatchItem(BaseModel):
    field: str
    value: Any
    status: Literal["unconfirmed", "confirmed"]
    reasoning: str | None = None


class Ambiguity(BaseModel):
    field: str
    reason: str


class ExtractionResult(BaseModel):
    patch: list[PatchItem] = []
    ambiguities: list[Ambiguity] = []
