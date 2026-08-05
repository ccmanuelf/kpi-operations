from decimal import Decimal
from datetime import datetime

import pytest

from backend.orm.labor_taxonomy import (
    BILLABLE_CATEGORIES,
    PRODUCTIVE_CATEGORIES,
    SELECTABLE_HOUR_CATEGORIES,
    HourCategoryEnum,
    LaborClassEnum,
)
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.attendance_hour_allocation import AttendanceHourAllocation
from backend.orm.employee import Employee


def test_labor_class_enum():
    assert {c.value for c in LaborClassEnum} == {"direct", "indirect"}


def test_hour_category_enum_exact_eight():
    assert [c.value for c in HourCategoryEnum] == [
        "billed_production",
        "unbilled_production",
        "training",
        "meeting",
        "idle_wait",
        "other_nonproductive",
        "paid_leave",
        "medical",
    ]
    assert SELECTABLE_HOUR_CATEGORIES == [c.value for c in HourCategoryEnum]


def test_metadata_sets():
    assert BILLABLE_CATEGORIES == frozenset({"billed_production"})
    assert PRODUCTIVE_CATEGORIES == frozenset({"billed_production", "unbilled_production"})
    assert BILLABLE_CATEGORIES <= PRODUCTIVE_CATEGORIES
    assert PRODUCTIVE_CATEGORIES <= {c.value for c in HourCategoryEnum}


def _entry(**kwargs):
    return AttendanceEntry(
        attendance_entry_id=kwargs.pop("attendance_entry_id", "ATT-LAB-T1"),
        client_id="C1",
        employee_id=1,
        shift_date=datetime(2026, 8, 1, 6, 0),
        scheduled_hours=Decimal("8.00"),
        **kwargs,
    )
    # Align with AttendanceEntry's actual NOT-NULL constructor fields — read the
    # model first and extend if instantiation needs more; keep labor kwargs as tested.


def test_attendance_validators_reject_invalid_override_allow_none():
    with pytest.raises(ValueError, match="labor_class_override"):
        _entry(labor_class_override="contractor")
    assert _entry(attendance_entry_id="ATT-LAB-T2", labor_class_override=None).labor_class_override is None
    assert _entry(attendance_entry_id="ATT-LAB-T3", labor_class_override="indirect").labor_class_override == "indirect"


def test_employee_validator_rejects_invalid_class():
    with pytest.raises(ValueError, match="labor_class"):
        Employee(employee_id=999999, client_id_assigned="C1", labor_class="temp")
    # Align Employee constructor with its NOT-NULL fields (read model); the
    # labor_class kwarg is the assertion target.


def test_allocation_category_validator():
    with pytest.raises(ValueError, match="category"):
        AttendanceHourAllocation(attendance_entry_id="ATT-LAB-T1", category="lunch", hours=Decimal("1.00"))
    ok = AttendanceHourAllocation(attendance_entry_id="ATT-LAB-T1", category="training", hours=Decimal("1.50"))
    assert ok.category == "training"
