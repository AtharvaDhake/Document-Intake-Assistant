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

    # Worldwide Assets section
    if fields.covers_worldwide_assets.status in (FieldStatus.CONFIRMED, FieldStatus.UNCONFIRMED):
        ww_val = fields.covers_worldwide_assets.value
        if ww_val:
            worldwide_text = "This document is intended to cover all of my assets worldwide, regardless of jurisdiction."
        else:
            worldwide_text = "This document is restricted to assets within my primary jurisdiction and does not cover worldwide assets."
    else:
        worldwide_text = "Worldwide assets coverage: [not yet provided]"
        
    worldwide_section = (
        "───────────────────────────────────────────────────────\n"
        "SECTION 2 — ASSETS SCOPE\n"
        "───────────────────────────────────────────────────────\n\n"
        f"{worldwide_text}"
    )

    # Children section
    if (fields.has_children.status == FieldStatus.CONFIRMED
            and fields.has_children.value is True):
        children = _render(fields.children_names, "children's names")
        children_section = f"I have children. Their names are: {children}."
    elif (fields.has_children.status == FieldStatus.CONFIRMED
            and fields.has_children.value is False):
        children_section = "I do not have children."
    else:
        children_section = f"Children: [{has_children}]."

    # Gifts section
    if fields.specific_gifts.status in (FieldStatus.CONFIRMED, FieldStatus.UNCONFIRMED):
        gifts = fields.specific_gifts.value
        if gifts:
            gift_lines = "\n".join(f"  • {g}" for g in gifts)
            gifts_section = f"I would like to make the following specific gifts:\n{gift_lines}"
        else:
            gifts_section = "I have no specific gifts to declare at this time."
    else:
        gifts_section = "Specific gifts: [not yet provided]."

    # Additional wishes
    if fields.additional_wishes.status in (FieldStatus.CONFIRMED, FieldStatus.UNCONFIRMED):
        wishes = fields.additional_wishes.value
        if wishes:
            wishes_section = f"Additional wishes:\n{wishes}"
        else:
            wishes_section = "I have no additional wishes to declare at this time."
    else:
        wishes_section = "Additional wishes: [not yet provided]."

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
