"""Guard: response-model fields backed by a Numeric/Decimal source must serialize
as JSON numbers, not Decimal-as-string.

Root cause (e2e-sweep ISSUE-011, same class as #145 `4cecdd3`): Pydantic v2
serializes a field typed ``Decimal`` to a JSON *string* on ``model_dump_json`` /
``model_dump(mode="json")`` — verified end-to-end through FastAPI's actual
response path, not just a unit-level pydantic call. A field typed ``float``
correctly coerces a ``Decimal`` value (e.g. one read off a SQLAlchemy
``Numeric`` column via ``from_attributes``) into a JSON number. The mechanism
applied here mirrors #145: cast Decimal-backed values to ``float`` — at the
schema field-type level for real Pydantic response models (#145 did the
equivalent cast in raw-dict arithmetic for endpoints with no response schema).

Two layers:
  1. ``TestNoDecimalFieldsOnResponseModels`` — a structural sweep over every
     class referenced via ``response_model=`` across ``backend/routes/**``.
     This is the regression backstop: it fails automatically if a *future*
     field is added back as ``Decimal`` on any response model, without
     needing this file to be updated.
  2. ``TestDecimalInputSerializesAsNumber`` — concrete construction of each
     model this task fixed, fed real ``Decimal`` values (as MariaDB/SQLAlchemy
     would produce off a ``Numeric`` column), then JSON-dumped and asserted
     to decode as ``int``/``float`` — never ``str``. Runs on SQLite CI; the
     defect is Pydantic-serialization-level, not driver-level, so it does not
     require MariaDB to reproduce (live MariaDB verification is a separate,
     already-covered concern — see test_kpi/test_decimal_json_serialization.py).
"""

import importlib
import json
import pkgutil
import re
from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel

import backend.routes as routes_pkg
from backend.schemas.alert import (
    AlertConfigResponse,
    AlertResponse,
    CapacityAlert,
    OTDRiskAlert,
    QualityTrendAlert,
)
from backend.schemas.attendance import AbsenteeismCalculationResponse, AttendanceRecordResponse
from backend.schemas.coverage import ShiftCoverageResponse
from backend.schemas.downtime import AvailabilityCalculationResponse
from backend.schemas.employee_line_assignment import EmployeeLineAssignmentResponse
from backend.schemas.hold import (
    TotalHoldDurationResponse,
    WIPAgingAdjustedResponse,
    WIPAgingResponse,
    WIPHoldResponse,
)
from backend.schemas.job import JobResponse
from backend.schemas.production import (
    KPICalculationResponse,
    ProductionEntryResponse,
    ProductionEntryWithKPIs,
)
from backend.schemas.quality import (
    DPMOCalculationResponse,
    FPYRTYCalculationResponse,
    PPMCalculationResponse,
    QualityInspectionResponse,
)
from backend.schemas.work_order import WorkOrderResponse, WorkOrderWithMetrics

# ---------------------------------------------------------------------------
# Layer 1: structural sweep over every response_model= referenced in routes/
# ---------------------------------------------------------------------------


def _iter_route_modules():
    """Yield every importable module under backend/routes (recursively)."""
    for finder, name, ispkg in pkgutil.walk_packages(routes_pkg.__path__, prefix="backend.routes."):
        if name.endswith("__pycache__"):
            continue
        try:
            yield importlib.import_module(name)
        except Exception:  # pragma: no cover - defensive; import failures caught elsewhere
            continue


def _collect_response_model_class_names():
    """Grep-equivalent: every identifier passed to response_model= across routes/."""
    names = set()
    pattern = re.compile(r"response_model=(?:List\[)?([A-Za-z_][A-Za-z0-9_]*)")
    routes_dir = routes_pkg.__path__[0]
    import os

    for dirpath, _, filenames in os.walk(routes_dir):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            with open(os.path.join(dirpath, fn)) as f:
                for match in pattern.finditer(f.read()):
                    names.add(match.group(1))
    names -= {"Dict", "dict", "None", "Optional"}
    return names


def _field_has_decimal(annotation, _seen=None) -> bool:
    """Recursively check a Pydantic field annotation for a bare Decimal type."""
    if _seen is None:
        _seen = set()
    if annotation is Decimal:
        return True
    ann_id = id(annotation)
    if ann_id in _seen:
        return False
    _seen.add(ann_id)
    args = getattr(annotation, "__args__", None)
    if args:
        return any(_field_has_decimal(a, _seen) for a in args)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return any(_field_has_decimal(f.annotation, _seen) for f in annotation.model_fields.values())
    return False


class TestNoDecimalFieldsOnResponseModels:
    """No class wired as response_model= anywhere may expose a Decimal field."""

    def test_no_response_model_carries_a_decimal_field(self):
        modules = list(_iter_route_modules())
        names = _collect_response_model_class_names()

        offenders = {}
        for name in names:
            cls = None
            for mod in modules:
                cls = getattr(mod, name, None)
                if cls is not None:
                    break
            if cls is None or not (isinstance(cls, type) and issubclass(cls, BaseModel)):
                continue
            bad_fields = [fname for fname, finfo in cls.model_fields.items() if _field_has_decimal(finfo.annotation)]
            if bad_fields:
                offenders[name] = bad_fields

        assert not offenders, (
            "The following response_model classes expose Decimal-typed fields, which "
            "serialize as JSON strings (not numbers) via Pydantic v2's model_dump_json. "
            f"Change the field type to float: {offenders}"
        )


# ---------------------------------------------------------------------------
# Layer 2: concrete Decimal input -> JSON number, for every model fixed by
# this task (backend/schemas/{hold,employee_line_assignment,job,attendance,
# coverage,downtime,work_order,quality,production,alert}.py)
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 10, 8, 0, 0)
_TODAY = date(2026, 6, 10)

CASES = [
    pytest.param(
        WIPHoldResponse,
        dict(
            hold_entry_id="H1",
            client_id="C1",
            work_order_id="WO1",
            hold_status="ON_HOLD",
            total_hold_duration_hours=Decimal("12.50"),
        ),
        ["total_hold_duration_hours"],
        id="WIPHoldResponse",
    ),
    pytest.param(
        WIPAgingResponse,
        dict(
            total_held_quantity=5,
            average_aging_days=Decimal("74.7"),
            aging_0_7_days=1,
            aging_8_14_days=1,
            aging_15_30_days=1,
            aging_over_30_days=2,
            total_hold_events=5,
            calculation_timestamp=_NOW,
        ),
        ["average_aging_days"],
        id="WIPAgingResponse",
    ),
    pytest.param(
        WIPAgingAdjustedResponse,
        dict(
            work_order_number="WO1",
            raw_age_hours=Decimal("10.5000"),
            total_hold_duration_hours=Decimal("2.0000"),
            adjusted_age_hours=Decimal("8.5000"),
            hold_count=1,
            is_currently_on_hold=False,
        ),
        ["raw_age_hours", "total_hold_duration_hours", "adjusted_age_hours"],
        id="WIPAgingAdjustedResponse",
    ),
    pytest.param(
        TotalHoldDurationResponse,
        dict(work_order_number="WO1", total_hold_duration_hours=Decimal("5.2500"), hold_count=1, active_holds=0),
        ["total_hold_duration_hours"],
        id="TotalHoldDurationResponse",
    ),
    pytest.param(
        EmployeeLineAssignmentResponse,
        dict(
            assignment_id=1,
            employee_id=1,
            line_id=1,
            client_id="C1",
            allocation_percentage=Decimal("100.00"),
            is_primary=True,
            effective_date=_TODAY,
            created_at=_NOW,
        ),
        ["allocation_percentage"],
        id="EmployeeLineAssignmentResponse",
    ),
    pytest.param(
        JobResponse,
        dict(
            work_order_id="WO1",
            client_id_fk="C1",
            operation_name="Sew",
            sequence_number=1,
            job_id="J1",
            created_at=_NOW,
            planned_hours=Decimal("8.00"),
            actual_hours=Decimal("7.50"),
        ),
        ["planned_hours", "actual_hours"],
        id="JobResponse",
    ),
    pytest.param(
        AttendanceRecordResponse,
        dict(
            attendance_entry_id="A1",
            client_id="C1",
            employee_id=1,
            shift_date=_NOW,
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("7.50"),
            absence_hours=Decimal("0.50"),
            is_absent=0,
        ),
        ["scheduled_hours", "actual_hours", "absence_hours"],
        id="AttendanceRecordResponse",
    ),
    pytest.param(
        AbsenteeismCalculationResponse,
        dict(
            shift_id=1,
            start_date=_TODAY,
            end_date=_TODAY,
            total_scheduled_hours=Decimal("40.00"),
            total_hours_worked=Decimal("38.00"),
            total_hours_absent=Decimal("2.00"),
            absenteeism_rate=Decimal("5.00"),
            total_employees=5,
            total_absences=1,
            calculation_timestamp=_NOW,
        ),
        ["total_scheduled_hours", "total_hours_worked", "total_hours_absent", "absenteeism_rate"],
        id="AbsenteeismCalculationResponse",
    ),
    pytest.param(
        ShiftCoverageResponse,
        dict(
            coverage_id=1,
            shift_id=1,
            coverage_date=_TODAY,
            required_employees=5,
            actual_employees=4,
            coverage_percentage=Decimal("80.00"),
            entered_by="u1",
            created_at=_NOW,
            updated_at=_NOW,
        ),
        ["coverage_percentage"],
        id="ShiftCoverageResponse",
    ),
    pytest.param(
        AvailabilityCalculationResponse,
        dict(
            product_id=1,
            shift_id=1,
            production_date=_TODAY,
            total_scheduled_hours=Decimal("8.00"),
            total_downtime_hours=Decimal("1.00"),
            available_hours=Decimal("7.00"),
            availability_percentage=Decimal("87.50"),
            downtime_events=1,
            calculation_timestamp=_NOW,
        ),
        ["total_scheduled_hours", "total_downtime_hours", "available_hours", "availability_percentage"],
        id="AvailabilityCalculationResponse",
    ),
    pytest.param(
        WorkOrderResponse,
        dict(
            work_order_id="WO1",
            client_id="C1",
            style_model="M1",
            planned_quantity=10,
            actual_quantity=5,
            status="RECEIVED",
            ideal_cycle_time=Decimal("0.2500"),
            calculated_cycle_time=Decimal("0.3000"),
            total_run_time_hours=Decimal("12.50"),
            created_at=_NOW,
        ),
        ["ideal_cycle_time", "calculated_cycle_time", "total_run_time_hours"],
        id="WorkOrderResponse",
    ),
    pytest.param(
        WorkOrderWithMetrics,
        dict(
            work_order_id="WO1",
            client_id="C1",
            style_model="M1",
            planned_quantity=10,
            actual_quantity=5,
            status="RECEIVED",
            created_at=_NOW,
            efficiency_percentage=Decimal("84.6400"),
        ),
        ["efficiency_percentage"],
        id="WorkOrderWithMetrics",
    ),
    pytest.param(
        QualityInspectionResponse,
        dict(
            quality_entry_id="QE1",
            client_id="C1",
            work_order_id="WO1",
            shift_date=_NOW,
            units_inspected=100,
            units_passed=90,
            units_defective=10,
            total_defects_count=10,
            ppm=Decimal("1000.00"),
            dpmo=Decimal("500.00"),
            fpy_percentage=Decimal("90.00"),
        ),
        ["ppm", "dpmo", "fpy_percentage"],
        id="QualityInspectionResponse",
    ),
    pytest.param(
        PPMCalculationResponse,
        dict(
            product_id=1,
            shift_id=1,
            start_date=_TODAY,
            end_date=_TODAY,
            total_units_inspected=100,
            total_defects=5,
            ppm=Decimal("500.00"),
            defect_rate_percentage=Decimal("5.00"),
            calculation_timestamp=_NOW,
        ),
        ["ppm", "defect_rate_percentage"],
        id="PPMCalculationResponse",
    ),
    pytest.param(
        DPMOCalculationResponse,
        dict(
            product_id=1,
            shift_id=1,
            start_date=_TODAY,
            end_date=_TODAY,
            total_units=100,
            opportunities_per_unit=1,
            total_defects=5,
            dpmo=Decimal("500.00"),
            sigma_level=Decimal("3.50"),
            calculation_timestamp=_NOW,
        ),
        ["dpmo", "sigma_level"],
        id="DPMOCalculationResponse",
    ),
    pytest.param(
        FPYRTYCalculationResponse,
        dict(
            product_id=1,
            start_date=_TODAY,
            end_date=_TODAY,
            total_units=100,
            first_pass_good=90,
            fpy_percentage=Decimal("90.00"),
            rty_percentage=Decimal("85.00"),
            final_yield_percentage=Decimal("80.00"),
            total_process_steps=3,
            calculation_timestamp=_NOW,
        ),
        ["fpy_percentage", "rty_percentage", "final_yield_percentage"],
        id="FPYRTYCalculationResponse",
    ),
    pytest.param(
        ProductionEntryResponse,
        dict(
            production_entry_id="PE1",
            client_id="C1",
            product_id=1,
            shift_id=1,
            production_date=_NOW,
            shift_date=_NOW,
            units_produced=100,
            run_time_hours=Decimal("8.00"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            setup_time_hours=Decimal("0.50"),
            downtime_hours=Decimal("0.25"),
            maintenance_hours=Decimal("0.10"),
            ideal_cycle_time=Decimal("0.0800"),
            actual_cycle_time=Decimal("0.0900"),
            efficiency_percentage=Decimal("84.6400"),
            performance_percentage=Decimal("90.0000"),
            quality_rate=Decimal("98.0000"),
        ),
        [
            "run_time_hours",
            "setup_time_hours",
            "downtime_hours",
            "maintenance_hours",
            "ideal_cycle_time",
            "actual_cycle_time",
            "efficiency_percentage",
            "performance_percentage",
            "quality_rate",
        ],
        id="ProductionEntryResponse",
    ),
    pytest.param(
        ProductionEntryWithKPIs,
        dict(
            production_entry_id="PE1",
            client_id="C1",
            product_id=1,
            shift_id=1,
            production_date=_NOW,
            shift_date=_NOW,
            units_produced=100,
            run_time_hours=Decimal("8.00"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            product_name="Widget",
            shift_name="Day",
            total_available_hours=Decimal("7.50"),
            quality_rate=Decimal("98.0000"),
            oee=Decimal("74.7000"),
        ),
        ["total_available_hours", "quality_rate", "oee"],
        id="ProductionEntryWithKPIs",
    ),
    pytest.param(
        KPICalculationResponse,
        dict(
            entry_id="PE1",
            efficiency_percentage=Decimal("84.6400"),
            performance_percentage=Decimal("90.0000"),
            quality_rate=Decimal("98.0000"),
            ideal_cycle_time_used=Decimal("0.0800"),
            was_inferred=False,
            calculation_timestamp=_NOW,
        ),
        ["efficiency_percentage", "performance_percentage", "quality_rate", "ideal_cycle_time_used"],
        id="KPICalculationResponse",
    ),
    pytest.param(
        AlertResponse,
        dict(
            category="otd",
            severity="info",
            title="t",
            message="m",
            alert_id="A1",
            current_value=Decimal("10.50"),
            threshold_value=Decimal("5.00"),
            predicted_value=Decimal("12.00"),
            confidence=Decimal("80.00"),
            created_at=_NOW,
        ),
        ["current_value", "threshold_value", "predicted_value", "confidence"],
        id="AlertResponse",
    ),
    pytest.param(
        AlertConfigResponse,
        dict(
            alert_type="otd",
            config_id="CFG1",
            warning_threshold=Decimal("70.00"),
            critical_threshold=Decimal("50.00"),
            created_at=_NOW,
        ),
        ["warning_threshold", "critical_threshold"],
        id="AlertConfigResponse",
    ),
    pytest.param(
        OTDRiskAlert,
        dict(
            work_order_id="WO1",
            client_name="C",
            due_date=_NOW,
            current_completion=Decimal("50.00"),
            required_completion=Decimal("100.00"),
            risk_score=Decimal("75.00"),
            days_remaining=2,
        ),
        ["current_completion", "required_completion", "risk_score"],
        id="OTDRiskAlert",
    ),
    pytest.param(
        QualityTrendAlert,
        dict(
            kpi_type="fpy",
            current_value=Decimal("90.00"),
            trend_direction="stable",
            change_percent=Decimal("1.50"),
            period_days=7,
        ),
        ["current_value", "change_percent"],
        id="QualityTrendAlert",
    ),
    pytest.param(
        CapacityAlert,
        dict(
            load_percent=Decimal("95.00"),
            status="overloaded",
            recommended_action="x",
            overtime_hours_needed=Decimal("4.00"),
        ),
        ["load_percent", "overtime_hours_needed"],
        id="CapacityAlert",
    ),
]


class TestDecimalInputSerializesAsNumber:
    """Feed each fixed response model real Decimal values; JSON must carry numbers."""

    @pytest.mark.parametrize("model_cls, kwargs, fields", CASES)
    def test_decimal_fields_are_json_numbers(self, model_cls, kwargs, fields):
        instance = model_cls(**kwargs)
        dumped = json.loads(instance.model_dump_json())

        for field in fields:
            value = dumped[field]
            assert isinstance(value, (int, float)) and not isinstance(value, bool), (
                f"{model_cls.__name__}.{field} serialized as {value!r} ({type(value).__name__}), "
                "expected a JSON number. A Decimal-typed field regressed back in — see #145 / "
                "ISSUE-011 for the fix mechanism (cast to float)."
            )
