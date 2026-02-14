"""
Absenteeism KPI Calculation
PHASE 3: Employee attendance tracking

Absenteeism Rate = (Total Hours Absent / Total Scheduled Hours) * 100
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from backend.schemas.attendance_entry import AttendanceEntry


def calculate_absenteeism(
    db: Session, shift_id: int, start_date: date, end_date: date
) -> tuple[Decimal, Decimal, Decimal, int, int]:
    """
    Calculate absenteeism rate for a shift over date range

    Returns: (absenteeism_rate, total_scheduled, total_absent, employee_count, absence_count)
    """
    # Convert date to datetime for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Get all attendance records for period
    records = (
        db.query(AttendanceEntry)
        .filter(
            and_(
                AttendanceEntry.shift_id == shift_id,
                AttendanceEntry.shift_date >= start_datetime,
                AttendanceEntry.shift_date <= end_datetime,
            )
        )
        .all()
    )

    if not records:
        return (Decimal("0"), Decimal("0"), Decimal("0"), 0, 0)

    # Sum scheduled and worked hours
    total_scheduled = Decimal("0")
    total_worked = Decimal("0")
    unique_employees = set()
    absence_count = 0

    for record in records:
        total_scheduled += Decimal(str(record.scheduled_hours or 0))
        total_worked += Decimal(str(record.actual_hours or 0))
        unique_employees.add(record.employee_id)

        # Check if absent or late using boolean flags
        if record.is_absent == 1 or record.is_late == 1:
            absence_count += 1

    total_absent = total_scheduled - total_worked

    # Calculate absenteeism rate
    if total_scheduled > 0:
        absenteeism_rate = (total_absent / total_scheduled) * 100
    else:
        absenteeism_rate = Decimal("0")

    return (absenteeism_rate, total_scheduled, total_absent, len(unique_employees), absence_count)


def calculate_attendance_rate(db: Session, employee_id: int, start_date: date, end_date: date) -> Decimal:
    """
    Calculate attendance rate for specific employee

    Attendance Rate = (Days Present / Total Scheduled Days) * 100
    """
    # Convert date to datetime for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    total_days = (
        db.query(func.count(AttendanceEntry.attendance_entry_id))
        .filter(
            and_(
                AttendanceEntry.employee_id == employee_id,
                AttendanceEntry.shift_date >= start_datetime,
                AttendanceEntry.shift_date <= end_datetime,
            )
        )
        .scalar()
    )

    if not total_days:
        return Decimal("0")

    # Count days where employee was present (not absent)
    present_days = (
        db.query(func.count(AttendanceEntry.attendance_entry_id))
        .filter(
            and_(
                AttendanceEntry.employee_id == employee_id,
                AttendanceEntry.shift_date >= start_datetime,
                AttendanceEntry.shift_date <= end_datetime,
                AttendanceEntry.is_absent == 0,
            )
        )
        .scalar()
    )

    attendance_rate = (Decimal(str(present_days)) / Decimal(str(total_days))) * 100
    return attendance_rate


def identify_chronic_absentees(
    db: Session, threshold_rate: Decimal = Decimal("10.0"), start_date: date = None, end_date: date = None
) -> list[dict]:
    """
    Identify employees with absenteeism above threshold

    Default threshold: 10% (industry average is ~5%)
    """
    from datetime import timedelta

    if not start_date:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

    # Convert date to datetime for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Get all unique employees
    employees = (
        db.query(AttendanceEntry.employee_id)
        .filter(and_(AttendanceEntry.shift_date >= start_datetime, AttendanceEntry.shift_date <= end_datetime))
        .distinct()
        .all()
    )

    chronic_absentees = []

    for (emp_id,) in employees:
        rate = calculate_attendance_rate(db, emp_id, start_date, end_date)

        # If attendance rate is low (high absenteeism)
        if rate < (100 - threshold_rate):
            absenteeism = 100 - rate

            chronic_absentees.append(
                {
                    "employee_id": emp_id,
                    "attendance_rate": rate,
                    "absenteeism_rate": absenteeism,
                    "needs_attention": True,
                }
            )

    # Sort by worst absenteeism first
    chronic_absentees.sort(key=lambda x: x["absenteeism_rate"], reverse=True)

    return chronic_absentees


def calculate_bradford_factor(db: Session, employee_id: int, start_date: date, end_date: date) -> int:
    """
    Calculate Bradford Factor Score

    Bradford Factor = S² × D
    Where:
    - S = Number of spells (instances) of absence
    - D = Total days of absence

    Interpretation:
    - 0-50: Low risk
    - 51-125: Monitor
    - 126-250: Formal action
    - 251+: Final warning/termination
    """
    from sqlalchemy import or_

    # Convert date to datetime for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    absences = (
        db.query(AttendanceEntry)
        .filter(
            and_(
                AttendanceEntry.employee_id == employee_id,
                AttendanceEntry.shift_date >= start_datetime,
                AttendanceEntry.shift_date <= end_datetime,
                or_(AttendanceEntry.is_absent == 1, AttendanceEntry.is_late == 1),
            )
        )
        .order_by(AttendanceEntry.shift_date)
        .all()
    )

    if not absences:
        return 0

    # Count spells (continuous absence periods)
    spells = 1
    prev_date = absences[0].shift_date.date() if hasattr(absences[0].shift_date, "date") else absences[0].shift_date

    for i in range(1, len(absences)):
        current_date = (
            absences[i].shift_date.date() if hasattr(absences[i].shift_date, "date") else absences[i].shift_date
        )
        if (current_date - prev_date).days > 1:
            spells += 1
        prev_date = current_date

    # Total days absent
    total_days = len(absences)

    # Calculate Bradford Factor
    bradford_score = (spells**2) * total_days

    return bradford_score
