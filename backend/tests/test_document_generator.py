"""Tests for the Document Generator."""

from app.models.fields import FieldValue, FieldStatus
from app.models.state import SessionFields
from app.document_generator import generate_document


def _complete_fields() -> SessionFields:
    """Helper: return a fully confirmed state."""
    return SessionFields(
        full_name=FieldValue(value="Jane Smith", status=FieldStatus.CONFIRMED),
        home_address=FieldValue(value="12 Elm Street, London", status=FieldStatus.CONFIRMED),
        covers_worldwide_assets=FieldValue(value=True, status=FieldStatus.CONFIRMED),
        has_children=FieldValue(value=True, status=FieldStatus.CONFIRMED),
        children_names=FieldValue(value=["Tom", "Alice"], status=FieldStatus.CONFIRMED),
        executor_name=FieldValue(value="James Smith", status=FieldStatus.CONFIRMED),
        executor_relationship=FieldValue(value="brother", status=FieldStatus.CONFIRMED),
        specific_gifts=FieldValue(value=["Watch to Tom", "Piano to Alice"], status=FieldStatus.CONFIRMED),
        additional_wishes=FieldValue(value="A simple ceremony with close family.", status=FieldStatus.CONFIRMED),
    )


def test_complete_state_produces_full_document():
    fields = _complete_fields()
    doc = generate_document(fields)

    assert "Jane Smith" in doc
    assert "12 Elm Street, London" in doc
    assert "cover all of my assets worldwide" in doc  # worldwide assets
    assert "Tom" in doc
    assert "Alice" in doc
    assert "James Smith" in doc
    assert "brother" in doc
    assert "Watch to Tom" in doc
    assert "Piano to Alice" in doc
    assert "simple ceremony" in doc
    assert "DISCLAIMER" in doc


def test_empty_state_shows_all_placeholders():
    fields = SessionFields()
    doc = generate_document(fields)

    assert "[full name not yet provided]" in doc
    assert "[home address not yet provided]" in doc
    assert "[executor name not yet provided]" in doc
    assert "[executor relationship not yet provided]" in doc
    assert "DISCLAIMER" in doc


def test_partial_state_mixes_values_and_placeholders():
    fields = SessionFields(
        full_name=FieldValue(value="Jane Smith", status=FieldStatus.CONFIRMED),
        has_children=FieldValue(value=False, status=FieldStatus.CONFIRMED),
    )
    doc = generate_document(fields)

    assert "Jane Smith" in doc
    assert "I do not have children" in doc
    assert "[home address not yet provided]" in doc
    assert "[executor name not yet provided]" in doc


def test_no_children_section():
    fields = SessionFields(
        has_children=FieldValue(value=False, status=FieldStatus.CONFIRMED),
        children_names=FieldValue(status=FieldStatus.NOT_APPLICABLE),
    )
    doc = generate_document(fields)
    assert "I do not have children" in doc


def test_no_gifts_renders_correctly():
    fields = SessionFields(
        specific_gifts=FieldValue(value=[], status=FieldStatus.CONFIRMED),
    )
    doc = generate_document(fields)
    assert "no specific gifts" in doc


def test_no_additional_wishes():
    fields = SessionFields(
        additional_wishes=FieldValue(value="", status=FieldStatus.CONFIRMED),
    )
    doc = generate_document(fields)
    assert "no additional wishes" in doc
