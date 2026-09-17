from enum import Enum
from datetime import datetime
from typing import TypeVar, Optional, Generic
from pydantic import BaseModel

T = TypeVar('T')


class FieldStatus(str, Enum):
    MISSING = "missing"
    UNCONFIRMED = "unconfirmed"
    CONFIRMED = "confirmed"
    # Used for children_names when has_children is false — without this,
    # the "fields remaining" counter never reaches zero.
    NOT_APPLICABLE = "not_applicable"


class FieldValue(BaseModel, Generic[T]):
    value: Optional[T] = None
    status: FieldStatus = FieldStatus.MISSING
    source_turn: Optional[int] = None
    last_updated: Optional[datetime] = None
