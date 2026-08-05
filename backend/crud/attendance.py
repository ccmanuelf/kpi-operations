"""
CRUD operations for attendance tracking
PHASE 3
SECURITY: Multi-tenant client filtering enabled
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional, List
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException

from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.attendance_hour_allocation import AttendanceHourAllocation
from backend.orm.shift import Shift
from backend.orm.employee import Employee
from backend.schemas.attendance import (
    AllocationItemResponse,
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    AttendanceRecordResponse,
)
from backend.calculations.labor_hours import (
    available_for_efficiency_hours,
    billed_hours,
    effective_labor_class,
    validate_allocations,
    validate_ot_split,
)
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.orm.user import User
from backend.utils.soft_delete import soft_delete
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


def _compose_attendance_response(
    entry: AttendanceEntry, employee_default_class: Optional[str]
) -> AttendanceRecordResponse:
    """Compose the response with Task 3's derived labor-hours fields, given an
    already-resolved employee default labor class (caller's responsibility to fetch it —
    single-row and batch callers below use different strategies to avoid N+1).

    billed_hours / available_for_efficiency_hours / effective_labor_class are pure
    derivations over the entry's persisted split + allocations, never stored themselves.
    hour_allocations is lazy="selectin", so accessing it here doesn't add a query per
    entry when the entries were loaded together by a single Query.
    """
    alloc_tuples = [(alloc.category, alloc.hours) for alloc in entry.hour_allocations]

    response = AttendanceRecordResponse.model_validate(entry)
    # AllocationItemResponse(...) constructor validation coerces Decimal .hours -> float.
    response.allocations = [
        AllocationItemResponse(category=alloc.category, hours=alloc.hours) for alloc in entry.hour_allocations
    ]
    # Direct attribute assignment on an already-constructed model bypasses field
    # validation/coercion (validate_assignment defaults to False), so cast explicitly —
    # otherwise a raw Decimal would land on a float-typed field and could re-serialize
    # as a JSON string (see AllocationItem's docstring in schemas/attendance.py).
    response.billed_hours = float(billed_hours(alloc_tuples))
    response.available_for_efficiency_hours = (
        float(available_for_efficiency_hours(entry.actual_hours, alloc_tuples))
        if entry.actual_hours is not None
        else None
    )
    response.effective_labor_class = effective_labor_class(entry.labor_class_override, employee_default_class)
    return response


def _build_attendance_response(db: Session, entry: AttendanceEntry) -> AttendanceRecordResponse:
    """Single-entry enrichment (create/update/get-by-id): one query to join the employee."""
    employee = db.query(Employee).filter(Employee.employee_id == entry.employee_id).first()
    employee_default_class = employee.labor_class if employee else None
    return _compose_attendance_response(entry, employee_default_class)


def _build_attendance_responses_batch(db: Session, entries: List[AttendanceEntry]) -> List[AttendanceRecordResponse]:
    """List enrichment: a single IN query over the page's distinct employee_ids,
    instead of one Employee lookup per row (N+1 risk on the grid's feed).
    """
    employee_ids = {entry.employee_id for entry in entries}
    class_by_employee_id: dict[int, Optional[str]] = {}
    if employee_ids:
        rows = db.query(Employee.employee_id, Employee.labor_class).filter(Employee.employee_id.in_(employee_ids)).all()
        class_by_employee_id = {row.employee_id: row.labor_class for row in rows}

    return [_compose_attendance_response(entry, class_by_employee_id.get(entry.employee_id)) for entry in entries]


def create_attendance_record(
    db: Session, attendance: AttendanceRecordCreate, current_user: User
) -> AttendanceRecordResponse:
    """
    Create new attendance record
    SECURITY: Verifies user has access to the specified client
    """
    # SECURITY: Verify user has access to this client
    if hasattr(attendance, "client_id") and attendance.client_id:
        verify_client_access(current_user, attendance.client_id)

    data = attendance.model_dump(exclude={"allocations"})

    # OT split invariant: normalize the 0-defaulted triple when any tier is supplied.
    try:
        normalized_split = validate_ot_split(
            data.get("normal_hours"), data.get("double_hours"), data.get("triple_hours"), data.get("actual_hours")
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if normalized_split is not None:
        data["normal_hours"], data["double_hours"], data["triple_hours"] = normalized_split

    data["labor_class_override"] = (
        attendance.labor_class_override.value if attendance.labor_class_override is not None else None
    )

    allocations = attendance.allocations
    if allocations is not None:
        items = [(item.category.value, item.hours) for item in allocations]
        try:
            validate_allocations(items, data.get("actual_hours") or Decimal("0"))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    # Pre-existing gap: this path never set the String PK (no ORM/DB default),
    # so every insert would violate NOT NULL. Same uuid4().hex pattern as
    # bulk_create_attendance_records / mark_all_present below.
    db_attendance = AttendanceEntry(attendance_entry_id=uuid4().hex, **data, entered_by=current_user.user_id)
    if allocations is not None:
        db_attendance.hour_allocations = [
            AttendanceHourAllocation(category=item.category.value, hours=item.hours) for item in allocations
        ]

    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)

    return _build_attendance_response(db, db_attendance)


def get_attendance_record(db: Session, attendance_id: str, current_user: User) -> AttendanceRecordResponse:
    """
    Get attendance record by ID
    SECURITY: Verifies user has access to the record's client
    """
    db_attendance = db.query(AttendanceEntry).filter(AttendanceEntry.attendance_entry_id == attendance_id).first()

    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_attendance, "client_id") and db_attendance.client_id:
        verify_client_access(current_user, db_attendance.client_id)

    return _build_attendance_response(db, db_attendance)


def get_attendance_records(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    shift_date: Optional[date] = None,
    employee_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    is_absent: Optional[int] = None,
    client_id: Optional[str] = None,
) -> List[AttendanceRecordResponse]:
    """
    Get attendance records with filters
    SECURITY: Automatically filters by user's authorized clients
    """
    query = db.query(AttendanceEntry)

    # SECURITY: Apply client filtering based on user's role
    client_filter = build_client_filter_clause(current_user, AttendanceEntry.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply additional filters
    if client_id:
        query = query.filter(AttendanceEntry.client_id == client_id)

    if start_date:
        query = query.filter(AttendanceEntry.shift_date >= datetime.combine(start_date, datetime.min.time()))

    if end_date:
        query = query.filter(AttendanceEntry.shift_date <= datetime.combine(end_date, datetime.max.time()))

    # Exact-day match (as opposed to start_date/end_date's range) — portable
    # idiom is func.date(...) == shift_date, NEVER a cast-to-Date (structural
    # guard enforces this; see docs/architecture/date-filtering.md-equivalent
    # precedent in calculations/efficiency.py, availability.py, ppm.py, dpmo.py).
    # Was previously accepted as a query param and silently ignored (not a
    # declared FastAPI param), so the grid's "load today's entries" call was
    # effectively date-unfiltered — last-wins on the employee_id merge could
    # hydrate today's grid with a stale, older day's allocations.
    if shift_date:
        query = query.filter(func.date(AttendanceEntry.shift_date) == shift_date)

    if employee_id:
        query = query.filter(AttendanceEntry.employee_id == employee_id)

    if shift_id:
        query = query.filter(AttendanceEntry.shift_id == shift_id)

    if is_absent is not None:
        query = query.filter(AttendanceEntry.is_absent == is_absent)

    entries = query.order_by(AttendanceEntry.shift_date.desc()).offset(skip).limit(limit).all()
    return _build_attendance_responses_batch(db, entries)


def update_attendance_record(
    db: Session, attendance_id: str, attendance_update: AttendanceRecordUpdate, current_user: User
) -> Optional[AttendanceRecordResponse]:
    """
    Update attendance record
    SECURITY: Verifies user has access to the record's client
    """
    db_attendance = db.query(AttendanceEntry).filter(AttendanceEntry.attendance_entry_id == attendance_id).first()

    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_attendance, "client_id") and db_attendance.client_id:
        verify_client_access(current_user, db_attendance.client_id)

    fields_set = attendance_update.model_fields_set
    update_data = attendance_update.model_dump(exclude_unset=True, exclude={"allocations", "labor_class_override"})

    # actual_hours is PUT-updatable (grid-style edits send it alongside a new
    # split) — validate the split/allocations against the NEW value when this
    # same request changes it, not the stale stored one (fix round 3, item 4).
    effective_actual_hours = (
        attendance_update.actual_hours if "actual_hours" in fields_set else db_attendance.actual_hours
    )

    # OT split invariant: normalize the 0-defaulted triple when any tier is supplied.
    if {"normal_hours", "double_hours", "triple_hours"} & fields_set:
        try:
            normalized_split = validate_ot_split(
                attendance_update.normal_hours,
                attendance_update.double_hours,
                attendance_update.triple_hours,
                effective_actual_hours,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        if normalized_split is not None:
            update_data["normal_hours"], update_data["double_hours"], update_data["triple_hours"] = normalized_split
        else:
            # At least one tier key was explicitly sent (fields_set matched
            # above), but the resolved trio came back all-None: unset tier
            # keys default to None too, so validate_ot_split can't tell
            # "caller means to clear everything" apart from "caller only
            # touched one tier and meant to leave the others alone" — the
            # sum invariant is all-or-nothing, so there IS no valid partial
            # reading. Without this, `update_data` (built from
            # exclude_unset) would only carry the tier(s) actually in the
            # request body, leaving the untouched tiers at their stale DB
            # values (fix round 3, item 1 — e.g. PUT {"normal_hours": null}
            # on a split entry left double/triple at their old nonzero
            # values instead of clearing the whole split).
            update_data["normal_hours"] = None
            update_data["double_hours"] = None
            update_data["triple_hours"] = None

    if "labor_class_override" in fields_set:
        update_data["labor_class_override"] = (
            attendance_update.labor_class_override.value if attendance_update.labor_class_override is not None else None
        )

    # Replace-on-write: only touch the ledger when the key was actually sent (omitted -> untouched,
    # empty list -> cleared via the delete-orphan cascade).
    if "allocations" in fields_set:
        allocations = attendance_update.allocations or []
        items = [(item.category.value, item.hours) for item in allocations]
        try:
            validate_allocations(items, effective_actual_hours or Decimal("0"))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        # Clear-then-flush before assigning the new rows. SQLAlchemy's flush ordering
        # doesn't guarantee the delete-orphan DELETEs for the removed rows land before the
        # new rows' INSERTs, so a resubmit that reuses any category (even an identical
        # resubmit) would otherwise violate UniqueConstraint(attendance_entry_id, category).
        db_attendance.hour_allocations = []
        db.flush()
        db_attendance.hour_allocations = [
            AttendanceHourAllocation(category=item.category.value, hours=item.hours) for item in allocations
        ]

    for field, value in update_data.items():
        if hasattr(db_attendance, field):
            setattr(db_attendance, field, value)

    db.commit()
    db.refresh(db_attendance)

    return _build_attendance_response(db, db_attendance)


def delete_attendance_record(db: Session, attendance_id: str, current_user: User) -> bool:
    """
    Soft delete attendance record (sets is_active = False)
    SECURITY: Verifies user has access to the record's client
    """
    db_attendance = db.query(AttendanceEntry).filter(AttendanceEntry.attendance_entry_id == attendance_id).first()

    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_attendance, "client_id") and db_attendance.client_id:
        verify_client_access(current_user, db_attendance.client_id)

    # Soft delete - preserves data integrity
    return soft_delete(db, db_attendance)


# ============================================================================
# BULK OPERATIONS
# ============================================================================


def bulk_create_attendance_records(db: Session, records: List[AttendanceRecordCreate], current_user: User) -> dict:
    """
    Create multiple attendance records in one transaction.

    SECURITY: Validates client access for each record.

    Args:
        db: Database session
        records: List of AttendanceRecordCreate Pydantic models
        current_user: Authenticated user

    Returns:
        Summary dict with total, successful, failed counts, errors, and created IDs
    """
    total = len(records)
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for idx, record in enumerate(records):
        try:
            # Validate client access
            if record.client_id:
                verify_client_access(current_user, record.client_id)

            # "allocations" has no matching AttendanceEntry column/kwarg (it's a separate
            # child-table relationship); bulk-create doesn't support labor-hours capture yet.
            # Previously silently dropped (excluded below with no error) — fail this row
            # explicitly instead, same per-row idiom as an invalid OT split, rather than
            # quietly persisting the row without the allocations the caller asked for.
            if record.allocations is not None:
                raise ValueError("allocations are not supported on the bulk endpoint — use single create/update")

            data = record.model_dump(exclude={"allocations"})

            # OT split invariant: same as single-record create. This is a per-row bulk
            # operation (not all-or-nothing), so an invalid split fails only this row
            # rather than persisting silently — the ValueError below is caught by the
            # existing per-row except clause and reported in the row's error entry.
            normalized_split = validate_ot_split(
                data.get("normal_hours"), data.get("double_hours"), data.get("triple_hours"), data.get("actual_hours")
            )
            if normalized_split is not None:
                data["normal_hours"], data["double_hours"], data["triple_hours"] = normalized_split

            entry_id = uuid4().hex
            db_entry = AttendanceEntry(
                attendance_entry_id=entry_id,
                **data,
                entered_by=current_user.user_id,
            )
            db.add(db_entry)
            created_ids.append(entry_id)
            successful += 1
        except HTTPException as e:
            failed += 1
            errors.append({"index": idx, "error": e.detail})
        except Exception as e:
            failed += 1
            errors.append({"index": idx, "error": str(e)})

    if successful > 0:
        db.commit()
        logger.info(
            "Bulk attendance create: %d/%d succeeded, user=%s",
            successful,
            total,
            current_user.username,
        )
    else:
        db.rollback()

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "errors": errors,
        "created_ids": created_ids,
    }


def mark_all_present(db: Session, client_id: str, shift_id: int, shift_date: date, current_user: User) -> dict:
    """
    Create attendance records for all active employees assigned to a client,
    marking them as present for a given shift and date.

    SECURITY: Verifies user has access to the specified client.

    Args:
        db: Database session
        client_id: Client to mark attendance for
        shift_id: Shift to record attendance against
        shift_date: Date of the shift
        current_user: Authenticated user

    Returns:
        Summary dict with total_employees, records_created, already_exists, created_ids
    """
    # Verify client access
    verify_client_access(current_user, client_id)

    # Get the shift to determine scheduled hours
    shift = (
        db.query(Shift)
        .filter(
            Shift.shift_id == shift_id,
            Shift.client_id == client_id,
        )
        .first()
    )

    if not shift:
        raise HTTPException(status_code=404, detail=f"Shift {shift_id} not found for client {client_id}")

    # Calculate shift hours from start_time / end_time (handle overnight)
    start_dt = datetime.combine(shift_date, shift.start_time)
    end_dt = datetime.combine(shift_date, shift.end_time)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)  # overnight shift
    shift_hours = Decimal(str(round((end_dt - start_dt).total_seconds() / 3600, 2)))

    # Get all active employees assigned to this client
    # Employee.client_id_assigned is a comma-separated string of client IDs
    employees = (
        db.query(Employee)
        .filter(
            Employee.is_active == 1,
            or_(
                Employee.client_id_assigned == client_id,
                Employee.client_id_assigned.like(f"{client_id},%"),
                Employee.client_id_assigned.like(f"%,{client_id},%"),
                Employee.client_id_assigned.like(f"%,{client_id}"),
            ),
        )
        .all()
    )

    total_employees = len(employees)

    # Convert shift_date to datetime for comparison with the DateTime column
    shift_datetime = datetime.combine(shift_date, datetime.min.time())

    # Find employees who already have attendance for this shift_date + shift_id
    existing_employee_ids = set()
    if employees:
        existing = (
            db.query(AttendanceEntry.employee_id)
            .filter(
                AttendanceEntry.client_id == client_id,
                AttendanceEntry.shift_id == shift_id,
                AttendanceEntry.shift_date == shift_datetime,
                AttendanceEntry.employee_id.in_([e.employee_id for e in employees]),
            )
            .all()
        )
        existing_employee_ids = {row.employee_id for row in existing}

    already_exists = len(existing_employee_ids)
    created_ids = []

    for emp in employees:
        if emp.employee_id in existing_employee_ids:
            continue

        entry_id = uuid4().hex
        db_entry = AttendanceEntry(
            attendance_entry_id=entry_id,
            client_id=client_id,
            employee_id=emp.employee_id,
            shift_date=shift_datetime,
            shift_id=shift_id,
            scheduled_hours=shift_hours,
            actual_hours=shift_hours,
            absence_hours=Decimal("0"),
            is_absent=0,
            entered_by=current_user.user_id,
        )
        db.add(db_entry)
        created_ids.append(entry_id)

    records_created = len(created_ids)

    if records_created > 0:
        db.commit()
        logger.info(
            "Mark all present: %d records created for client=%s shift=%d date=%s, user=%s",
            records_created,
            client_id,
            shift_id,
            shift_date.isoformat(),
            current_user.username,
        )

    return {
        "total_employees": total_employees,
        "records_created": records_created,
        "already_exists": already_exists,
        "created_ids": created_ids,
    }
