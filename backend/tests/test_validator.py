from app.models.patch import PatchItem
from app.models.state import SessionState
from app.models.fields import FieldValue, FieldStatus
from app.validation.validator import validate_patch


def test_accepts_valid_single_patch():
    state = SessionState()
    items = [PatchItem(field="full_name", value="Jane Smith", status="confirmed")]
    result = validate_patch(items, state)
    assert len(result.accepted) == 1
    assert not result.rejected


def test_rejects_unknown_field():
    state = SessionState()
    items = [PatchItem(field="favorite_color", value="blue", status="confirmed")]
    result = validate_patch(items, state)
    assert len(result.rejected) == 1
    assert "unknown field" in result.rejected[0][1]


def test_rejects_wrong_type_for_boolean():
    state = SessionState()
    items = [PatchItem(field="has_children", value="yes", status="confirmed")]
    result = validate_patch(items, state)
    assert len(result.rejected) == 1
    assert "boolean" in result.rejected[0][1]


def test_rejects_name_too_short():
    state = SessionState()
    items = [PatchItem(field="full_name", value="J", status="confirmed")]
    result = validate_patch(items, state)
    assert len(result.rejected) == 1
    assert "2 characters" in result.rejected[0][1]


def test_partial_patch_keeps_valid_items():
    state = SessionState()
    items = [
        PatchItem(field="full_name", value="Jane Smith", status="confirmed"),
        PatchItem(field="has_children", value="nope", status="confirmed"),
    ]
    result = validate_patch(items, state)
    assert len(result.accepted) == 1
    assert result.accepted[0].field == "full_name"
    assert len(result.rejected) == 1


def test_rejects_children_names_when_no_children():
    state = SessionState()
    state.fields.has_children = FieldValue(value=False, status=FieldStatus.CONFIRMED)
    items = [PatchItem(field="children_names", value=["Tom"], status="confirmed")]
    result = validate_patch(items, state)
    assert len(result.rejected) == 1
    assert len(result.ambiguities) == 1


def test_allows_children_names_when_has_children():
    state = SessionState()
    state.fields.has_children = FieldValue(value=True, status=FieldStatus.CONFIRMED)
    items = [PatchItem(field="children_names", value=["Tom", "Alice"], status="confirmed")]
    result = validate_patch(items, state)
    assert len(result.accepted) == 1
    assert not result.ambiguities


def test_correction_detected_on_value_change():
    state = SessionState()
    state.fields.executor_name = FieldValue(
        value="James", status=FieldStatus.CONFIRMED, source_turn=3,
    )
    items = [PatchItem(field="executor_name", value="Sarah", status="confirmed")]
    result = validate_patch(items, state)
    assert len(result.accepted) == 1
    assert result.accepted[0].status == "unconfirmed"
    assert len(result.corrections) == 1
    assert result.corrections[0].old_value == "James"
    assert result.corrections[0].new_value == "Sarah"


def test_no_correction_when_same_value():
    state = SessionState()
    state.fields.full_name = FieldValue(value="Jane Smith", status=FieldStatus.CONFIRMED)
    items = [PatchItem(field="full_name", value="Jane Smith", status="confirmed")]
    result = validate_patch(items, state)
    assert not result.corrections
    assert len(result.accepted) == 1


def test_empty_patch_is_valid():
    result = validate_patch([], SessionState())
    assert not result.accepted
    assert not result.rejected
    assert not result.ambiguities


def test_accepts_empty_additional_wishes():
    state = SessionState()
    items = [PatchItem(field="additional_wishes", value="", status="confirmed")]
    result = validate_patch(items, state)
    assert len(result.accepted) == 1


def test_accepts_empty_gifts_list():
    state = SessionState()
    items = [PatchItem(field="specific_gifts", value=[], status="confirmed")]
    result = validate_patch(items, state)
    assert len(result.accepted) == 1


def test_rejects_gifts_with_empty_strings():
    state = SessionState()
    items = [PatchItem(field="specific_gifts", value=["watch", ""], status="confirmed")]
    result = validate_patch(items, state)
    assert len(result.rejected) == 1
    assert "non-empty string" in result.rejected[0][1]
