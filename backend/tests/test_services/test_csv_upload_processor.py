from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from backend.services.csv_upload_processor import process_csv_upload, sanitize_csv_value


class _Created:
    def __init__(self, _id):
        self.id = _id


def _id_getter(c):
    return c.id


def test_all_rows_succeed():
    rows = [{"v": "1"}, {"v": "2"}]
    res = process_csv_upload(
        rows,
        db=None,
        current_user=None,
        row_mapper=lambda row, user: row,
        create_fn=lambda db, e, u: _Created(e["v"]),
        id_getter=_id_getter,
    )
    assert res.total_rows == 2
    assert res.successful == 2
    assert res.failed == 0
    assert res.created_entries == ["1", "2"]


def test_validation_error_row_recorded_with_exact_message():
    class _M(BaseModel):
        n: int

    def mapper(row, user):
        _M(n="not-an-int")  # raises pydantic ValidationError
        return row

    res = process_csv_upload(
        [{"a": "1"}],
        db=None,
        current_user=None,
        row_mapper=mapper,
        create_fn=lambda db, e, u: _Created(1),
        id_getter=_id_getter,
    )
    assert res.failed == 1
    assert res.errors[0] == {"row": 2, "error": "Validation error in CSV row data", "data": {"a": "1"}}


def test_database_error_row_recorded():
    def create(db, e, u):
        raise SQLAlchemyError("boom")

    res = process_csv_upload(
        [{"a": "1"}],
        db=None,
        current_user=None,
        row_mapper=lambda row, user: row,
        create_fn=create,
        id_getter=_id_getter,
    )
    assert res.failed == 1
    assert res.errors[0]["error"] == "Database error processing row"


def test_parsing_error_row_recorded():
    def mapper(row, user):
        raise ValueError("bad date")

    res = process_csv_upload(
        [{"a": "1"}],
        db=None,
        current_user=None,
        row_mapper=mapper,
        create_fn=lambda db, e, u: _Created(1),
        id_getter=_id_getter,
    )
    assert res.failed == 1
    assert res.errors[0]["error"] == "Data parsing error in CSV row"


def test_errors_capped_at_100():
    rows = [{"a": str(i)} for i in range(150)]
    res = process_csv_upload(
        rows,
        db=None,
        current_user=None,
        row_mapper=lambda row, user: (_ for _ in ()).throw(ValueError("x")),
        create_fn=lambda db, e, u: _Created(1),
        id_getter=_id_getter,
    )
    assert res.failed == 150
    assert len(res.errors) == 100


def test_row_numbering_starts_at_2():
    res = process_csv_upload(
        [{"a": "1"}],
        db=None,
        current_user=None,
        row_mapper=lambda row, user: (_ for _ in ()).throw(ValueError("x")),
        create_fn=lambda db, e, u: _Created(1),
        id_getter=_id_getter,
    )
    assert res.errors[0]["row"] == 2


def test_sanitize_csv_value_prefixes():
    assert sanitize_csv_value("=cmd") == "'=cmd"
    assert sanitize_csv_value("safe") == "safe"
