"""
CSV Export Service

Generic CSV export service that streams CSV rows from SQLAlchemy query results.
Supports CSV injection protection, date range filtering, and multi-tenant isolation.
"""

import csv
import io
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, Generator, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

# Characters that could trigger formula injection in spreadsheets
_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_value(value: str) -> str:
    """
    Protect against CSV injection by prefixing dangerous characters with a single quote.

    Spreadsheet applications (Excel, Google Sheets, LibreOffice Calc) interpret
    cells starting with =, +, -, @, tab, or carriage return as formulas.
    Prefixing with a single quote forces text interpretation.

    Args:
        value: The string value to sanitize.

    Returns:
        Sanitized string safe for CSV output.
    """
    if isinstance(value, str) and value and value[0] in _CSV_INJECTION_PREFIXES:
        return "'" + value
    return value


def _format_value(value: Any) -> str:
    """
    Format a Python value for CSV output.

    Handles None, datetime, date, time, Decimal, int, float, bool, and enum types.

    Args:
        value: Any Python value from an ORM model attribute.

    Returns:
        String representation suitable for CSV cell.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    # Enum values
    if hasattr(value, "value"):
        return str(value.value)
    return sanitize_csv_value(str(value))


def stream_csv_export(
    db: Session,
    model_class: Any,
    client_filter: Any,
    columns: List[Tuple[str, str]],
    date_field: Any = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    line_id: Optional[int] = None,
) -> Generator[str, None, None]:
    """
    Generic CSV export generator for any entity.

    Yields CSV rows as strings, starting with the header row. Streams data
    in chunks to keep memory usage low for large datasets.

    Args:
        db: SQLAlchemy database session.
        model_class: ORM model class to query (e.g., ProductionEntry).
        client_filter: SQLAlchemy filter clause for multi-tenant isolation,
                       or None if no tenant filtering is needed (ADMIN/POWERUSER).
        columns: List of (orm_attribute_name, csv_header_name) tuples defining
                 which columns to export and their CSV header labels.
        date_field: Optional SQLAlchemy column to filter by date range.
        start_date: Optional start date for range filtering (inclusive).
        end_date: Optional end date for range filtering (inclusive, end of day).
        line_id: Optional production line ID filter.

    Yields:
        CSV-formatted strings (header row first, then data rows).
    """
    # Build query
    query = db.query(model_class)

    # Apply multi-tenant filter
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply date range filter
    if date_field is not None:
        if start_date is not None:
            query = query.filter(date_field >= datetime.combine(start_date, datetime.min.time()))
        if end_date is not None:
            query = query.filter(date_field <= datetime.combine(end_date, datetime.max.time()))

    # Apply line_id filter if the model has line_id and a value was provided
    if line_id is not None and hasattr(model_class, "line_id"):
        query = query.filter(model_class.line_id == line_id)

    # Order by primary key for deterministic output
    pk_columns = [col for col in model_class.__table__.primary_key.columns]
    if pk_columns:
        query = query.order_by(*pk_columns)

    # Yield header row
    output = io.StringIO()
    writer = csv.writer(output)
    header = [col_header for _, col_header in columns]
    writer.writerow(header)
    yield output.getvalue()

    # Stream data rows in batches
    batch_size = 500
    offset = 0
    total_rows = 0

    while True:
        batch = query.offset(offset).limit(batch_size).all()
        if not batch:
            break

        for row in batch:
            output = io.StringIO()
            writer = csv.writer(output)
            values = [_format_value(getattr(row, attr_name, None)) for attr_name, _ in columns]
            writer.writerow(values)
            yield output.getvalue()
            total_rows += 1

        offset += batch_size

        if len(batch) < batch_size:
            break

    logger.info(
        "CSV export completed for %s: %d rows exported",
        model_class.__tablename__,
        total_rows,
    )
