"""
Document Generator — pure templating, no LLM involved.

Turns the current SessionFields into a draft Personal Wishes Document.
Confirmed fields render their values; anything else renders as a bracketed
placeholder so the document is always readable, even when incomplete.
"""

from .models.fields import FieldStatus
from .models.state import SessionFields


def _render(field_value, label: str) -> str:
    if field_value.status in (FieldStatus.CONFIRMED, FieldStatus.UNCONFIRMED):
        v = field_value.value
        if isinstance(v, list):
            return ", ".join(v) if v else f"[{label} not yet provided]"
        if isinstance(v, bool):
            return "Yes" if v else "No"
        return str(v) if v else f"[{label} not yet provided]"
    return f"[{label} not yet provided]"


def generate_document(fields: SessionFields) -> str:

    full_name = _render(fields.full_name, "full name")
    home_address = _render(fields.home_address, "home address")
    has_children = _render(fields.has_children, "children status")
    executor_name = _render(fields.executor_name, "executor name")
    executor_rel = _render(fields.executor_relationship, "executor relationship")

def _build_worldwide_section(field_value) -> str:
    if field_value.status in (FieldStatus.CONFIRMED, FieldStatus.UNCONFIRMED):
        ww_val = field_value.value
        if ww_val:
            text = "This document is intended to cover all of my assets worldwide, regardless of jurisdiction."
        else:
            text = "This document is restricted to assets within my primary jurisdiction and does not cover worldwide assets."
    else:
        text = "Worldwide assets coverage: [not yet provided]"
        
    return (
        "───────────────────────────────────────────────────────\n"
        "SECTION 2 — ASSETS SCOPE\n"
        "───────────────────────────────────────────────────────\n\n"
        f"{text}"
    )

def _build_children_section(has_children_field, children_names_field) -> str:
    if has_children_field.status == FieldStatus.CONFIRMED and has_children_field.value is True:
        children = _render(children_names_field, "children's names")
        return f"I have children. Their names are: {children}."
    elif has_children_field.status == FieldStatus.CONFIRMED and has_children_field.value is False:
        return "I do not have children."
    
    has_children_text = _render(has_children_field, "children status")
    return f"Children: [{has_children_text}]."

def _build_gifts_section(specific_gifts_field) -> str:
    if specific_gifts_field.status in (FieldStatus.CONFIRMED, FieldStatus.UNCONFIRMED):
        gifts = specific_gifts_field.value
        if gifts:
            gift_lines = "\n".join(f"  • {g}" for g in gifts)
            return f"I would like to make the following specific gifts:\n{gift_lines}"
        return "I have no specific gifts to declare at this time."
    return "Specific gifts: [not yet provided]."

def _build_wishes_section(additional_wishes_field) -> str:
    if additional_wishes_field.status in (FieldStatus.CONFIRMED, FieldStatus.UNCONFIRMED):
        wishes = additional_wishes_field.value
        if wishes:
            return f"Additional wishes:\n{wishes}"
        return "I have no additional wishes to declare at this time."
    return "Additional wishes: [not yet provided]."


def generate_document(fields: SessionFields) -> str:

    full_name = _render(fields.full_name, "full name")
    home_address = _render(fields.home_address, "home address")
    executor_name = _render(fields.executor_name, "executor name")
    executor_rel = _render(fields.executor_relationship, "executor relationship")

    worldwide_section = _build_worldwide_section(fields.covers_worldwide_assets)
    children_section = _build_children_section(fields.has_children, fields.children_names)
    gifts_section = _build_gifts_section(fields.specific_gifts)
    wishes_section = _build_wishes_section(fields.additional_wishes)

    document = f"""═══════════════════════════════════════════════════════
              PERSONAL WISHES DOCUMENT
═══════════════════════════════════════════════════════

DISCLAIMER: This is a fictional example document for
demonstration purposes only. It is not legal advice
and has no legal effect.

───────────────────────────────────────────────────────
SECTION 1 — PERSONAL DETAILS
───────────────────────────────────────────────────────

Full Name:      {full_name}
Home Address:   {home_address}

{worldwide_section}

───────────────────────────────────────────────────────
SECTION 3 — FAMILY
───────────────────────────────────────────────────────

{children_section}

───────────────────────────────────────────────────────
SECTION 4 — EXECUTOR
───────────────────────────────────────────────────────

I appoint {executor_name} (my {executor_rel}) as the
executor of this document.

───────────────────────────────────────────────────────
SECTION 5 — SPECIFIC GIFTS
───────────────────────────────────────────────────────

{gifts_section}

───────────────────────────────────────────────────────
SECTION 6 — ADDITIONAL WISHES
───────────────────────────────────────────────────────

{wishes_section}

───────────────────────────────────────────────────────

Signed: ________________________  Date: ______________

═══════════════════════════════════════════════════════
"""
    return document
