"""Tests for the Conversation Engine using the MockLLMClient."""

from app.models.state import SessionState
from app.models.fields import FieldValue, FieldStatus
from app.engine import ConversationEngine
from tests.dummy_client import DummyLLMClient


def _make_engine() -> tuple[ConversationEngine, SessionState]:
    client = DummyLLMClient()
    engine = ConversationEngine(client)
    state = SessionState()
    engine.start_session(state)
    return engine, state


def test_opening_message():
    engine, state = _make_engine()
    assert len(state.conversation_log) == 1
    assert state.conversation_log[0].role == "assistant"
    assert "full name" in state.conversation_log[0].content.lower()


def test_single_field_extraction():
    engine, state = _make_engine()
    result = engine.process_turn(state, "My name is Jane Smith.")
    assert state.fields.full_name.value == "Jane Smith"
    assert state.fields.full_name.status == FieldStatus.CONFIRMED
    assert result["patch_applied"]


def test_multi_field_extraction():
    engine, state = _make_engine()
    result = engine.process_turn(
        state, "I'm Jane Smith, I live at 12 Elm Street, and no kids."
    )
    assert state.fields.full_name.value == "Jane Smith"
    assert state.fields.home_address.value == "12 Elm Street"
    assert state.fields.has_children.value is False
    assert len(result["patch_applied"]) >= 3


def test_boolean_yes():
    engine, state = _make_engine()
    # First answer name so next question is about address
    engine.process_turn(state, "My name is Jane Smith.")
    engine.process_turn(state, "I live at 10 Downing Street.")
    # Next should ask about has_children
    result = engine.process_turn(state, "Yes, I have two children.")
    assert state.fields.has_children.value is True


def test_boolean_no():
    engine, state = _make_engine()
    engine.process_turn(state, "My name is Jane Smith.")
    engine.process_turn(state, "I live at 10 Downing Street.")
    result = engine.process_turn(state, "No, I don't have any kids.")
    assert state.fields.has_children.value is False
    assert state.fields.children_names.status == FieldStatus.NOT_APPLICABLE


def test_children_names_not_applicable_when_no_children():
    engine, state = _make_engine()
    engine.process_turn(state, "My name is Jane Smith.")
    engine.process_turn(state, "I live at 10 Downing Street.")
    engine.process_turn(state, "No kids.")
    assert state.fields.children_names.status == FieldStatus.NOT_APPLICABLE


def test_executor_extraction():
    engine, state = _make_engine()
    result = engine.process_turn(state, "My brother James should be executor.")
    assert state.fields.executor_name.value == "James"
    assert state.fields.executor_relationship.value == "brother"


def test_correction_detection():
    engine, state = _make_engine()
    engine.process_turn(state, "My name is Jane Smith.")
    assert state.fields.full_name.value == "Jane Smith"

    engine.process_turn(state, "My name is Sarah Smith.")
    # Correction should downgrade to unconfirmed
    assert state.fields.full_name.value == "Sarah Smith"
    assert state.fields.full_name.status == FieldStatus.UNCONFIRMED
    assert len(state.corrections) >= 1


def test_ambiguity_handling():
    engine, state = _make_engine()
    engine.process_turn(state, "My name is Jane Smith.")
    engine.process_turn(state, "I live at 10 Downing Street.")
    result = engine.process_turn(state, "Sort of, it's complicated.")
    assert result["ambiguities"]


def test_contradictory_info():
    engine, state = _make_engine()
    engine.process_turn(state, "My name is Jane Smith.")
    engine.process_turn(state, "I live at 10 Downing Street.")
    result = engine.process_turn(state, "I have no kids, my son Tom is in school.")
    assert result["ambiguities"]


def test_completion_state():
    engine, state = _make_engine()
    engine.process_turn(state, "My name is Jane Smith.")
    engine.process_turn(state, "I live at 12 Elm Street.")
    engine.process_turn(state, "No kids.")
    engine.process_turn(state, "Yes, cover worldwide assets.")
    engine.process_turn(state, "My brother James should be executor.")
    engine.process_turn(state, "No specific gifts.")
    engine.process_turn(state, "Nothing else, thanks.")
    assert state.status == "ready_for_review"
    assert state.fields.is_complete()


def test_conversation_log_grows():
    engine, state = _make_engine()
    initial = len(state.conversation_log)
    engine.process_turn(state, "My name is Jane Smith.")
    # Should have added user msg + assistant response
    assert len(state.conversation_log) == initial + 2


def test_state_updated_at_changes():
    engine, state = _make_engine()
    old_time = state.updated_at
    engine.process_turn(state, "My name is Jane Smith.")
    assert state.updated_at >= old_time
