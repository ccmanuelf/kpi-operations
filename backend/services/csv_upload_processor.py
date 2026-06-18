"""Shared CSV/XLSX upload processing — one correct per-row loop for all upload endpoints."""

import csv
import io
import logging
from decimal import InvalidOperation
from typing import Any, Callable, Optional

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.schemas.production import CSVUploadResponse

logger = logging.getLogger(__name__)

_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_MAX_CSV_SIZE = 10 * 1024 * 1024  # 10MB
_ALLOWED_EXTENSIONS = (".csv", ".xlsx")


def sanitize_csv_value(value: str) -> str:
    """Strip CSV injection prefixes (=, +, -, @, \\t, \\r) from string values."""
    if isinstance(value, str) and value and value[0] in _CSV_INJECTION_PREFIXES:
        return "'" + value
    return value


def _read_upload_file(file_content: bytes, filename: str, sheet_name: Optional[str] = None) -> list[dict]:
    """Read uploaded file (CSV or XLSX) → list of row dicts (csv.DictReader-shaped)."""
    lower_name = (filename or "").lower()
    if lower_name.endswith(".xlsx"):
        from backend.services.xlsx_parser import parse_xlsx_to_rows

        try:
            return parse_xlsx_to_rows(file_content, sheet_name=sheet_name, fuzzy_headers=True)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid XLSX file: {exc}")
    if lower_name.endswith(".csv"):
        return list(csv.DictReader(io.StringIO(file_content.decode("utf-8"))))
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a .csv or .xlsx file")


def read_upload(content: bytes, filename: str, sheet_name: Optional[str] = None) -> list[dict]:
    """Validate extension + size, then parse. Raises the same 400/413 as the legacy endpoints."""
    if not (filename or "").lower().endswith(_ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a .csv or .xlsx file")
    if len(content) > _MAX_CSV_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds 10MB limit")
    return _read_upload_file(content, filename, sheet_name=sheet_name)


def process_csv_upload(
    rows: list[dict],
    db: Session,
    current_user: User,
    *,
    row_mapper: Callable[[dict, User], Any],
    create_fn: Callable[[Session, Any, User], Any],
    id_getter: Callable[[Any], Any],
) -> CSVUploadResponse:
    """Run each row through row_mapper → create_fn, collecting the same counts/errors as the legacy endpoints."""
    total_rows = 0
    successful = 0
    failed = 0
    errors: list[dict] = []
    created_ids: list = []

    for row_num, row in enumerate(rows, start=2):
        total_rows += 1
        try:
            entry = row_mapper(row, current_user)
            created = create_fn(db, entry, current_user)
            created_ids.append(id_getter(created))
            successful += 1
        except ValidationError as e:
            logger.warning("CSV row %d validation failed: %s", row_num, e)
            failed += 1
            errors.append({"row": row_num, "error": "Validation error in CSV row data", "data": row})
        except SQLAlchemyError:
            logger.exception("Database error processing CSV row %d", row_num)
            failed += 1
            errors.append({"row": row_num, "error": "Database error processing row", "data": row})
        except (ValueError, TypeError, KeyError, InvalidOperation) as e:
            logger.warning("Data parsing error in CSV row %d: %s", row_num, e)
            failed += 1
            errors.append({"row": row_num, "error": "Data parsing error in CSV row", "data": row})

    return CSVUploadResponse(
        total_rows=total_rows, successful=successful, failed=failed, errors=errors[:100], created_entries=created_ids
    )
