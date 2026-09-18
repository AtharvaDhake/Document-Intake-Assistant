from app.models.fields import FieldValue, FieldStatus
from app.models.state import SessionState, SessionFields


def test_new_session_all_missing():
    state = SessionState()
    assert len(state.fields.missing_fields()) == 9
    assert state.fields.progress() == (0, 9)
    assert not state.fields.is_complete()


def test_setting_field_removes_from_missing():
    fields = SessionFields()
    fields.full_name = FieldValue(value="Jane Smith", status=FieldStatus.CONFIRMED)
    missing = fields.missing_fields()
    assert "full_name" not in missing
    assert len(missing) == 8


def test_progress_counts_confirmed_and_unconfirmed():
    fields = SessionFields()
    fields.full_name = FieldValue(value="Jane", status=FieldStatus.CONFIRMED)
    fields.home_address = FieldValue(value="123 Elm St", status=FieldStatus.UNCONFIRMED)
    captured, total = fields.progress()
    assert captured == 2
    assert total == 9


def test_not_applicable_reduces_total():
    fields = SessionFields()
    fields.has_children = FieldValue(value=False, status=FieldStatus.CONFIRMED)
    fields.children_names = FieldValue(status=FieldStatus.NOT_APPLICABLE)
    captured, total = fields.progress()
    assert total == 8
    assert captured == 1


def test_is_complete_without_children():
    fields = SessionFields(
        full_name=FieldValue(value="Jane Smith", status=FieldStatus.CONFIRMED),
        home_address=FieldValue(value="123 Elm St", status=FieldStatus.CONFIRMED),
        covers_worldwide_assets=FieldValue(value=True, status=FieldStatus.CONFIRMED),
        has_children=FieldValue(value=False, status=FieldStatus.CONFIRMED),
        children_names=FieldValue(status=FieldStatus.NOT_APPLICABLE),
        executor_name=FieldValue(value="James Smith", status=FieldStatus.CONFIRMED),
        executor_relationship=FieldValue(value="brother", status=FieldStatus.CONFIRMED),
        specific_gifts=FieldValue(status=FieldStatus.NOT_APPLICABLE),
        additional_wishes=FieldValue(status=FieldStatus.NOT_APPLICABLE),
    )
    assert fields.is_complete()


def test_is_complete_requires_children_names_when_has_children():
    fields = SessionFields(
        full_name=FieldValue(value="Jane Smith", status=FieldStatus.CONFIRMED),
        home_address=FieldValue(value="123 Elm St", status=FieldStatus.CONFIRMED),
        covers_worldwide_assets=FieldValue(value=True, status=FieldStatus.CONFIRMED),
        has_children=FieldValue(value=True, status=FieldStatus.CONFIRMED),
        executor_name=FieldValue(value="James Smith", status=FieldStatus.CONFIRMED),
        executor_relationship=FieldValue(value="brother", status=FieldStatus.CONFIRMED),
        specific_gifts=FieldValue(status=FieldStatus.NOT_APPLICABLE),
        additional_wishes=FieldValue(status=FieldStatus.NOT_APPLICABLE),
    )
    assert not fields.is_complete()

    fields.children_names = FieldValue(value=["Tom", "Alice"], status=FieldStatus.CONFIRMED)
    assert fields.is_complete()


def test_next_missing_follows_priority():
    fields = SessionFields()
    assert fields.next_missing_field() == "full_name"

    fields.full_name = FieldValue(value="Jane", status=FieldStatus.CONFIRMED)
    assert fields.next_missing_field() == "home_address"
