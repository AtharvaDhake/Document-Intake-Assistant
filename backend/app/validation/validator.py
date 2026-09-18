from dataclasses import dataclass, field
from typing import Any

from ..models.patch import PatchItem, Ambiguity
from ..models.state import SessionState
from ..models.fields import FieldStatus

VALID_FIELDS = {
    "full_name", "home_address", "covers_worldwide_assets", "has_children",
    "children_names", "executor_name", "executor_relationship",
    "specific_gifts", "additional_wishes",
}


@dataclass
class CorrectionRecord:
    field: str
    old_value: Any
    new_value: Any


@dataclass
class ValidationResult:
    accepted: list[PatchItem] = field(default_factory=list)
    rejected: list[tuple[PatchItem, str]] = field(default_factory=list)
    ambiguities: list[Ambiguity] = field(default_factory=list)
    corrections: list[CorrectionRecord] = field(default_factory=list)


def validate_patch(items: list[PatchItem], state: SessionState) -> ValidationResult:
    outcome = ValidationResult()

    for item in items:
        if item.field not in VALID_FIELDS:
            outcome.rejected.append((item, f"unknown field: {item.field}"))
            continue

        type_error = _check_type(item)
        if type_error:
            outcome.rejected.append((item, type_error))
            continue

        biz_problem = _check_business_rules(item, items, state)
        if biz_problem:
            outcome.ambiguities.append(biz_problem)
            outcome.rejected.append((item, biz_problem.reason))
            continue

        correction = _detect_correction(item, state)
        if correction:
            outcome.corrections.append(correction)
            # Downgrade to unconfirmed — don't silently overwrite a previously set value.
            # The responder will acknowledge the change and the user can re-confirm.
            item = PatchItem(
                field=item.field, value=item.value,
                status="unconfirmed", reasoning=item.reasoning,
            )

        outcome.accepted.append(item)

    return outcome


def _check_type(item: PatchItem) -> str | None:
    v = item.value

    if item.field in ("full_name", "home_address", "executor_name", "executor_relationship"):
        if not isinstance(v, str) or not v.strip():
            return f"{item.field} must be a non-empty string"
        if item.field == "full_name" and len(v.strip()) < 2:
            return "full_name must be at least 2 characters"

    elif item.field in ("covers_worldwide_assets", "has_children"):
        if not isinstance(v, bool):
            return f"{item.field} must be a boolean"

    elif item.field in ("children_names", "specific_gifts"):
        if not isinstance(v, list):
            return f"{item.field} must be a list"
        if any(not isinstance(x, str) or not x.strip() for x in v):
            return f"each item in {item.field} must be a non-empty string"

    elif item.field == "additional_wishes":
        if not isinstance(v, str):
            return "additional_wishes must be a string"
        # empty string is fine — this field is optional

    return None


def _check_business_rules(item: PatchItem, items: list[PatchItem], state: SessionState) -> Ambiguity | None:
    if item.field == "children_names":
        # Check proposed items first
        proposed_has_kids = next((i for i in items if i.field == "has_children"), None)
        
        if proposed_has_kids:
            if proposed_has_kids.value is False and proposed_has_kids.status in ("confirmed", "unconfirmed"):
                return Ambiguity(
                    field="children_names",
                    reason="children_names provided but has_children is being set to false",
                )
        else:
            # Fall back to current state
            has_kids = state.fields.has_children
            if has_kids.status == FieldStatus.CONFIRMED and has_kids.value is False:
                return Ambiguity(
                    field="children_names",
                    reason="children_names provided but has_children is confirmed false",
                )
    return None


def _detect_correction(item: PatchItem, state: SessionState) -> CorrectionRecord | None:
    current = getattr(state.fields, item.field)
    if current.status not in (FieldStatus.CONFIRMED, FieldStatus.UNCONFIRMED):
        return None
    if current.value is None:
        return None

    old = current.value
    if old != item.value:
        return CorrectionRecord(field=item.field, old_value=old, new_value=item.value)
    return None
