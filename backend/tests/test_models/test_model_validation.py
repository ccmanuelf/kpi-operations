"""
Tests for critical ORM and Pydantic model validation.

Covers:
  1. HoldEntry ORM + WIPHoldCreate/WIPHoldResponse Pydantic
  2. QualityEntry ORM + QualityInspectionCreate Pydantic
  3. DowntimeEntry ORM + DowntimeEventCreate Pydantic
  4. AttendanceEntry ORM + AttendanceRecordCreate Pydantic
  5. WorkOrder ORM + WorkOrderCreate Pydantic
  6. WorkflowTransitionLog ORM + workflow Pydantic models
  7. Alert/AlertConfig/AlertHistory ORM models
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pydantic import ValidationError

# ── ORM schemas (SQLAlchemy) ──
from backend.schemas import (
    HoldEntry,
    HoldStatus,
    QualityEntry,
    DowntimeEntry,
    AttendanceEntry,
    AbsenceType,
    WorkOrder,
    WorkOrderStatus,
    WorkflowTransitionLog,
)
from backend.schemas.hold_entry import HoldReason

# Alert ORM is in backend/models/alert.py (it IS an ORM model, not Pydantic)
from backend.models.alert import Alert, AlertConfig, AlertHistory

# ── Pydantic validation models ──
from backend.models.hold import (
    HoldStatusEnum,
    HoldReasonEnum,
    WIPHoldCreate,
    WIPHoldUpdate,
    WIPHoldResponse,
    WIPAgingResponse,
)
from backend.models.quality import (
    QualityInspectionCreate,
    QualityInspectionUpdate,
    QualityInspectionResponse,
    InferenceMetadata as QualityInferenceMetadata,
)
from backend.models.downtime import (
    DowntimeReasonEnum,
    DowntimeEventCreate,
    DowntimeEventUpdate,
    DowntimeEventResponse,
    AvailabilityCalculationResponse,
)
from backend.models.attendance import (
    AbsenceTypeEnum,
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    AttendanceRecordResponse,
)
from backend.models.work_order import (
    WorkOrderStatusEnum,
    WorkOrderCreate,
    WorkOrderUpdate,
    WorkOrderResponse,
)
from backend.models.workflow import (
    WorkflowStatusEnum,
    ClosureTriggerEnum,
    TriggerSourceEnum,
    WorkflowTransitionCreate,
    WorkflowConfigCreate,
    BulkTransitionRequest,
    WORKFLOW_TEMPLATES,
)

# ── Factories ──
from backend.tests.fixtures.factories import TestDataFactory


# ==========================================================================
# 1. HoldEntry — ORM persistence + Pydantic validation
# ==========================================================================


class TestHoldEntryORM:
    """Tests for HoldEntry SQLAlchemy ORM model."""

    def test_create_hold_entry_with_required_fields(self, transactional_db):
        """HoldEntry persists with only required fields."""
        client = TestDataFactory.create_client(transactional_db, client_id="HOLD-C1")
        user = TestDataFactory.create_user(
            transactional_db, client_id="HOLD-C1", role="supervisor"
        )
        wo = TestDataFactory.create_work_order(
            transactional_db, client_id="HOLD-C1"
        )
        transactional_db.flush()

        hold = HoldEntry(
            hold_entry_id="HOLD-TEST-001",
            client_id="HOLD-C1",
            work_order_id=wo.work_order_id,
            hold_status=HoldStatus.ON_HOLD,
            hold_date=datetime.now(tz=timezone.utc),
            hold_initiated_by=user.user_id,
            hold_reason=HoldReason.QUALITY_ISSUE,
        )
        transactional_db.add(hold)
        transactional_db.commit()

        fetched = (
            transactional_db.query(HoldEntry)
            .filter(HoldEntry.hold_entry_id == "HOLD-TEST-001")
            .first()
        )
        assert fetched is not None
        assert fetched.hold_status == HoldStatus.ON_HOLD
        assert fetched.client_id == "HOLD-C1"
        assert fetched.hold_reason == HoldReason.QUALITY_ISSUE

    def test_hold_entry_default_duration_is_zero(self, transactional_db):
        """total_hold_duration_hours defaults to 0."""
        client = TestDataFactory.create_client(transactional_db, client_id="HOLD-C2")
        wo = TestDataFactory.create_work_order(
            transactional_db, client_id="HOLD-C2"
        )
        transactional_db.flush()

        hold = HoldEntry(
            hold_entry_id="HOLD-TEST-002",
            client_id="HOLD-C2",
            work_order_id=wo.work_order_id,
            hold_status=HoldStatus.PENDING_HOLD_APPROVAL,
        )
        transactional_db.add(hold)
        transactional_db.commit()

        fetched = (
            transactional_db.query(HoldEntry)
            .filter(HoldEntry.hold_entry_id == "HOLD-TEST-002")
            .first()
        )
        assert fetched.total_hold_duration_hours == 0

    def test_hold_status_enum_values(self):
        """HoldStatus enum contains expected workflow states."""
        assert HoldStatus.PENDING_HOLD_APPROVAL.value == "PENDING_HOLD_APPROVAL"
        assert HoldStatus.ON_HOLD.value == "ON_HOLD"
        assert HoldStatus.PENDING_RESUME_APPROVAL.value == "PENDING_RESUME_APPROVAL"
        assert HoldStatus.RESUMED.value == "RESUMED"
        assert HoldStatus.CANCELLED.value == "CANCELLED"

    def test_hold_reason_enum_values(self):
        """HoldReason enum covers all reason categories."""
        expected = {
            "MATERIAL_INSPECTION",
            "MATERIAL_SHORTAGE",
            "QUALITY_ISSUE",
            "ENGINEERING_REVIEW",
            "ENGINEERING_CHANGE",
            "CUSTOMER_REQUEST",
            "MISSING_SPECIFICATION",
            "EQUIPMENT_UNAVAILABLE",
            "CAPACITY_CONSTRAINT",
            "PENDING_APPROVAL",
            "OTHER",
        }
        actual = {member.value for member in HoldReason}
        assert actual == expected

    def test_hold_entry_factory(self, transactional_db):
        """TestDataFactory.create_hold_entry produces valid records."""
        client = TestDataFactory.create_client(transactional_db, client_id="HOLD-C3")
        user = TestDataFactory.create_user(
            transactional_db, client_id="HOLD-C3", role="supervisor"
        )
        wo = TestDataFactory.create_work_order(
            transactional_db, client_id="HOLD-C3"
        )
        transactional_db.flush()

        hold = TestDataFactory.create_hold_entry(
            transactional_db,
            work_order_id=wo.work_order_id,
            client_id="HOLD-C3",
            created_by=user.user_id,
            hold_reason="MATERIAL_INSPECTION",
        )
        transactional_db.commit()

        assert hold.hold_entry_id is not None
        assert hold.hold_reason == HoldReason.MATERIAL_INSPECTION


class TestWIPHoldPydantic:
    """Tests for WIPHoldCreate / WIPHoldResponse Pydantic models."""

    def test_create_with_required_fields(self):
        h = WIPHoldCreate(client_id="C1", work_order_id="WO-001")
        assert h.hold_status == HoldStatusEnum.ON_HOLD
        assert h.hold_date is None

    def test_create_rejects_empty_client_id(self):
        with pytest.raises(ValidationError):
            WIPHoldCreate(client_id="", work_order_id="WO-001")

    def test_create_rejects_empty_work_order_id(self):
        with pytest.raises(ValidationError):
            WIPHoldCreate(client_id="C1", work_order_id="")

    def test_from_legacy_csv_maps_reason(self):
        data = {
            "client_id": "C1",
            "work_order_number": "WO-100",
            "hold_category": "QUALITY",
        }
        h = WIPHoldCreate.from_legacy_csv(data)
        assert h.hold_reason == HoldReasonEnum.QUALITY_ISSUE
        assert h.work_order_id == "WO-100"

    def test_from_legacy_csv_unknown_reason_defaults_to_other(self):
        data = {
            "client_id": "C1",
            "work_order_number": "WO-100",
            "hold_category": "SOME_UNKNOWN_REASON",
        }
        h = WIPHoldCreate.from_legacy_csv(data)
        assert h.hold_reason == HoldReasonEnum.OTHER

    def test_response_from_attributes(self):
        assert WIPHoldResponse.model_config.get("from_attributes") is True


# ==========================================================================
# 2. QualityEntry — ORM persistence + Pydantic validation
# ==========================================================================


class TestQualityEntryORM:
    """Tests for QualityEntry SQLAlchemy ORM model."""

    def test_create_quality_entry(self, transactional_db):
        """QualityEntry persists with all required fields."""
        client = TestDataFactory.create_client(transactional_db, client_id="QUAL-C1")
        user = TestDataFactory.create_user(
            transactional_db, client_id="QUAL-C1", role="supervisor"
        )
        wo = TestDataFactory.create_work_order(
            transactional_db, client_id="QUAL-C1"
        )
        transactional_db.flush()

        qe = QualityEntry(
            quality_entry_id="QE-TEST-001",
            client_id="QUAL-C1",
            work_order_id=wo.work_order_id,
            shift_date=datetime(2026, 2, 15),
            units_inspected=500,
            units_passed=490,
            units_defective=10,
            total_defects_count=12,
            inspector_id=user.user_id,
        )
        transactional_db.add(qe)
        transactional_db.commit()

        fetched = (
            transactional_db.query(QualityEntry)
            .filter(QualityEntry.quality_entry_id == "QE-TEST-001")
            .first()
        )
        assert fetched is not None
        assert fetched.units_inspected == 500
        assert fetched.units_defective == 10
        assert fetched.total_defects_count == 12
        assert fetched.is_first_pass == 1  # default

    def test_quality_entry_defaults(self, transactional_db):
        """Defaults for optional integer columns."""
        client = TestDataFactory.create_client(transactional_db, client_id="QUAL-C2")
        wo = TestDataFactory.create_work_order(
            transactional_db, client_id="QUAL-C2"
        )
        transactional_db.flush()

        qe = QualityEntry(
            quality_entry_id="QE-TEST-002",
            client_id="QUAL-C2",
            work_order_id=wo.work_order_id,
            shift_date=datetime(2026, 2, 15),
            units_inspected=100,
            units_passed=95,
            units_defective=5,
            total_defects_count=5,
        )
        transactional_db.add(qe)
        transactional_db.commit()

        fetched = (
            transactional_db.query(QualityEntry)
            .filter(QualityEntry.quality_entry_id == "QE-TEST-002")
            .first()
        )
        assert fetched.units_scrapped == 0
        assert fetched.units_reworked == 0
        assert fetched.units_requiring_repair == 0

    def test_quality_entry_factory(self, transactional_db):
        """TestDataFactory.create_quality_entry produces valid records."""
        client = TestDataFactory.create_client(transactional_db, client_id="QUAL-C3")
        user = TestDataFactory.create_user(
            transactional_db, client_id="QUAL-C3", role="supervisor"
        )
        wo = TestDataFactory.create_work_order(
            transactional_db, client_id="QUAL-C3"
        )
        transactional_db.flush()

        qe = TestDataFactory.create_quality_entry(
            transactional_db,
            work_order_id=wo.work_order_id,
            client_id="QUAL-C3",
            inspector_id=user.user_id,
            units_inspected=200,
            units_defective=3,
        )
        transactional_db.commit()

        assert qe.quality_entry_id is not None
        assert qe.units_passed == 197  # 200 - 3


class TestQualityInspectionPydantic:
    """Tests for QualityInspectionCreate Pydantic model."""

    def test_create_with_required_fields(self):
        qi = QualityInspectionCreate(
            client_id="C1",
            work_order_id="WO-001",
            shift_date=date(2026, 2, 15),
            units_inspected=100,
            units_passed=95,
        )
        assert qi.units_defective == 0
        assert qi.total_defects_count == 0
        assert qi.is_first_pass == 1

    def test_units_inspected_must_be_positive(self):
        with pytest.raises(ValidationError):
            QualityInspectionCreate(
                client_id="C1",
                work_order_id="WO-001",
                shift_date=date(2026, 2, 15),
                units_inspected=0,
                units_passed=0,
            )

    def test_units_passed_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            QualityInspectionCreate(
                client_id="C1",
                work_order_id="WO-001",
                shift_date=date(2026, 2, 15),
                units_inspected=100,
                units_passed=-1,
            )

    def test_from_legacy_csv(self):
        data = {
            "client_id": "C1",
            "work_order_number": "WO-100",
            "shift_date": date(2026, 2, 15),
            "units_inspected": 200,
            "defects_found": 8,
        }
        qi = QualityInspectionCreate.from_legacy_csv(data)
        assert qi.work_order_id == "WO-100"
        assert qi.units_defective == 8
        assert qi.units_passed == 192  # 200 - 8


# ==========================================================================
# 3. DowntimeEntry — ORM persistence + Pydantic validation
# ==========================================================================


class TestDowntimeEntryORM:
    """Tests for DowntimeEntry SQLAlchemy ORM model."""

    def test_create_downtime_entry(self, transactional_db):
        """DowntimeEntry persists with required fields."""
        client = TestDataFactory.create_client(transactional_db, client_id="DT-C1")
        user = TestDataFactory.create_user(
            transactional_db, client_id="DT-C1", role="operator"
        )
        wo = TestDataFactory.create_work_order(
            transactional_db, client_id="DT-C1"
        )
        transactional_db.flush()

        dt = DowntimeEntry(
            downtime_entry_id="DT-TEST-001",
            client_id="DT-C1",
            work_order_id=wo.work_order_id,
            shift_date=datetime(2026, 2, 15, 8, 0),
            downtime_reason="EQUIPMENT_FAILURE",
            downtime_duration_minutes=45,
            machine_id="MACH-001",
        )
        transactional_db.add(dt)
        transactional_db.commit()

        fetched = (
            transactional_db.query(DowntimeEntry)
            .filter(DowntimeEntry.downtime_entry_id == "DT-TEST-001")
            .first()
        )
        assert fetched is not None
        assert fetched.downtime_reason == "EQUIPMENT_FAILURE"
        assert fetched.downtime_duration_minutes == 45
        assert fetched.machine_id == "MACH-001"

    def test_downtime_entry_factory(self, transactional_db):
        """TestDataFactory.create_downtime_entry produces valid records."""
        client = TestDataFactory.create_client(transactional_db, client_id="DT-C2")
        user = TestDataFactory.create_user(
            transactional_db, client_id="DT-C2", role="supervisor"
        )
        wo = TestDataFactory.create_work_order(
            transactional_db, client_id="DT-C2"
        )
        transactional_db.flush()

        dt = TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DT-C2",
            work_order_id=wo.work_order_id,
            reported_by=user.user_id,
            downtime_reason="MAINTENANCE",
            duration_minutes=30,
        )
        transactional_db.commit()

        assert dt.downtime_entry_id is not None
        assert dt.downtime_duration_minutes == 30
        assert dt.downtime_reason == "MAINTENANCE"


class TestDowntimeEventPydantic:
    """Tests for DowntimeEventCreate Pydantic model."""

    def test_create_with_required_fields(self):
        de = DowntimeEventCreate(
            client_id="C1",
            work_order_id="WO-001",
            shift_date=date(2026, 2, 15),
            downtime_reason=DowntimeReasonEnum.EQUIPMENT_FAILURE,
            downtime_duration_minutes=60,
        )
        assert de.downtime_reason == DowntimeReasonEnum.EQUIPMENT_FAILURE
        assert de.machine_id is None

    def test_duration_must_be_positive(self):
        with pytest.raises(ValidationError):
            DowntimeEventCreate(
                client_id="C1",
                work_order_id="WO-001",
                shift_date=date(2026, 2, 15),
                downtime_reason=DowntimeReasonEnum.OTHER,
                downtime_duration_minutes=0,
            )

    def test_duration_max_1440(self):
        with pytest.raises(ValidationError):
            DowntimeEventCreate(
                client_id="C1",
                work_order_id="WO-001",
                shift_date=date(2026, 2, 15),
                downtime_reason=DowntimeReasonEnum.OTHER,
                downtime_duration_minutes=1441,
            )

    def test_downtime_reason_enum_values(self):
        expected = {
            "EQUIPMENT_FAILURE",
            "MATERIAL_SHORTAGE",
            "SETUP_CHANGEOVER",
            "QUALITY_HOLD",
            "MAINTENANCE",
            "POWER_OUTAGE",
            "OTHER",
        }
        actual = {member.value for member in DowntimeReasonEnum}
        assert actual == expected

    def test_from_legacy_csv_converts_hours_to_minutes(self):
        data = {
            "client_id": "C1",
            "work_order_number": "WO-100",
            "shift_date": date(2026, 2, 15),
            "downtime_category": "SETUP",
            "duration_hours": 1.5,
        }
        de = DowntimeEventCreate.from_legacy_csv(data)
        assert de.downtime_duration_minutes == 90
        assert de.downtime_reason == DowntimeReasonEnum.SETUP_CHANGEOVER


# ==========================================================================
# 4. AttendanceEntry — ORM persistence + Pydantic validation
# ==========================================================================


class TestAttendanceEntryORM:
    """Tests for AttendanceEntry SQLAlchemy ORM model."""

    def test_create_attendance_entry(self, transactional_db):
        """AttendanceEntry persists with required fields."""
        client = TestDataFactory.create_client(transactional_db, client_id="ATT-C1")
        employee = TestDataFactory.create_employee(
            transactional_db, client_id="ATT-C1"
        )
        shift = TestDataFactory.create_shift(transactional_db, client_id="ATT-C1")
        transactional_db.flush()

        att = AttendanceEntry(
            attendance_entry_id="ATT-TEST-001",
            client_id="ATT-C1",
            employee_id=employee.employee_id,
            shift_date=datetime(2026, 2, 15),
            shift_id=shift.shift_id,
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            is_absent=0,
        )
        transactional_db.add(att)
        transactional_db.commit()

        fetched = (
            transactional_db.query(AttendanceEntry)
            .filter(AttendanceEntry.attendance_entry_id == "ATT-TEST-001")
            .first()
        )
        assert fetched is not None
        assert fetched.is_absent == 0
        assert float(fetched.scheduled_hours) == 8.0

    def test_attendance_absent_with_type(self, transactional_db):
        """Absent entry records absence_type correctly."""
        client = TestDataFactory.create_client(transactional_db, client_id="ATT-C2")
        employee = TestDataFactory.create_employee(
            transactional_db, client_id="ATT-C2"
        )
        shift = TestDataFactory.create_shift(transactional_db, client_id="ATT-C2")
        transactional_db.flush()

        att = AttendanceEntry(
            attendance_entry_id="ATT-TEST-002",
            client_id="ATT-C2",
            employee_id=employee.employee_id,
            shift_date=datetime(2026, 2, 15),
            shift_id=shift.shift_id,
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("0"),
            absence_hours=Decimal("8.0"),
            is_absent=1,
            absence_type=AbsenceType.UNSCHEDULED_ABSENCE,
        )
        transactional_db.add(att)
        transactional_db.commit()

        fetched = (
            transactional_db.query(AttendanceEntry)
            .filter(AttendanceEntry.attendance_entry_id == "ATT-TEST-002")
            .first()
        )
        assert fetched.is_absent == 1
        assert fetched.absence_type == AbsenceType.UNSCHEDULED_ABSENCE
        assert float(fetched.absence_hours) == 8.0

    def test_absence_type_enum_values(self):
        expected = {
            "UNSCHEDULED_ABSENCE",
            "VACATION",
            "MEDICAL_LEAVE",
            "PERSONAL_LEAVE",
        }
        actual = {member.value for member in AbsenceType}
        assert actual == expected

    def test_attendance_defaults(self, transactional_db):
        """Integer boolean defaults are 0 (present, not late)."""
        client = TestDataFactory.create_client(transactional_db, client_id="ATT-C3")
        employee = TestDataFactory.create_employee(
            transactional_db, client_id="ATT-C3"
        )
        shift = TestDataFactory.create_shift(transactional_db, client_id="ATT-C3")
        transactional_db.flush()

        att = AttendanceEntry(
            attendance_entry_id="ATT-TEST-003",
            client_id="ATT-C3",
            employee_id=employee.employee_id,
            shift_date=datetime(2026, 2, 15),
            shift_id=shift.shift_id,
            scheduled_hours=Decimal("8.0"),
        )
        transactional_db.add(att)
        transactional_db.commit()

        fetched = (
            transactional_db.query(AttendanceEntry)
            .filter(AttendanceEntry.attendance_entry_id == "ATT-TEST-003")
            .first()
        )
        assert fetched.is_absent == 0
        assert fetched.is_late == 0
        assert fetched.is_early_departure == 0
        assert fetched.coverage_confirmed == 0


class TestAttendanceRecordPydantic:
    """Tests for AttendanceRecordCreate Pydantic model."""

    def test_create_with_required_fields(self):
        ar = AttendanceRecordCreate(
            client_id="C1",
            employee_id=1,
            shift_date=date(2026, 2, 15),
            scheduled_hours=Decimal("8.0"),
        )
        assert ar.actual_hours == Decimal("0")
        assert ar.is_absent == 0
        assert ar.absence_type is None

    def test_employee_id_must_be_positive(self):
        with pytest.raises(ValidationError):
            AttendanceRecordCreate(
                client_id="C1",
                employee_id=0,
                shift_date=date(2026, 2, 15),
                scheduled_hours=Decimal("8.0"),
            )

    def test_scheduled_hours_must_be_positive(self):
        with pytest.raises(ValidationError):
            AttendanceRecordCreate(
                client_id="C1",
                employee_id=1,
                shift_date=date(2026, 2, 15),
                scheduled_hours=Decimal("0"),
            )

    def test_from_legacy_csv_absent_status(self):
        data = {
            "client_id": "C1",
            "employee_id": 1,
            "shift_date": date(2026, 2, 15),
            "status": "ABSENT",
            "scheduled_hours": 8,
        }
        ar = AttendanceRecordCreate.from_legacy_csv(data)
        assert ar.is_absent == 1
        assert ar.absence_type == AbsenceTypeEnum.UNSCHEDULED_ABSENCE

    def test_from_legacy_csv_vacation_status(self):
        data = {
            "client_id": "C1",
            "employee_id": 1,
            "shift_date": date(2026, 2, 15),
            "status": "VACATION",
            "scheduled_hours": 8,
        }
        ar = AttendanceRecordCreate.from_legacy_csv(data)
        assert ar.is_absent == 1
        assert ar.absence_type == AbsenceTypeEnum.VACATION


# ==========================================================================
# 5. WorkOrder — ORM persistence + Pydantic validation
# ==========================================================================


class TestWorkOrderORM:
    """Tests for WorkOrder SQLAlchemy ORM model."""

    def test_create_work_order(self, transactional_db):
        """WorkOrder persists with required fields."""
        client = TestDataFactory.create_client(transactional_db, client_id="WO-C1")
        transactional_db.flush()

        wo = WorkOrder(
            work_order_id="WO-TEST-001",
            client_id="WO-C1",
            style_model="STYLE-X100",
            planned_quantity=500,
            status=WorkOrderStatus.RECEIVED,
        )
        transactional_db.add(wo)
        transactional_db.commit()

        fetched = (
            transactional_db.query(WorkOrder)
            .filter(WorkOrder.work_order_id == "WO-TEST-001")
            .first()
        )
        assert fetched is not None
        assert fetched.style_model == "STYLE-X100"
        assert fetched.planned_quantity == 500
        assert fetched.status == WorkOrderStatus.RECEIVED
        assert fetched.actual_quantity == 0  # default

    def test_work_order_status_enum_values(self):
        """WorkOrderStatus enum has all expected statuses."""
        expected = {
            "RECEIVED",
            "RELEASED",
            "DEMOTED",
            "ACTIVE",
            "IN_PROGRESS",
            "ON_HOLD",
            "COMPLETED",
            "SHIPPED",
            "CLOSED",
            "REJECTED",
            "CANCELLED",
        }
        actual = {member.value for member in WorkOrderStatus}
        assert actual == expected

    def test_work_order_factory(self, transactional_db):
        """TestDataFactory.create_work_order produces valid records."""
        client = TestDataFactory.create_client(transactional_db, client_id="WO-C2")
        transactional_db.flush()

        wo = TestDataFactory.create_work_order(
            transactional_db,
            client_id="WO-C2",
            planned_quantity=2000,
            status=WorkOrderStatus.IN_PROGRESS,
        )
        transactional_db.commit()

        assert wo.work_order_id is not None
        assert wo.planned_quantity == 2000
        assert wo.status == WorkOrderStatus.IN_PROGRESS


class TestWorkOrderPydantic:
    """Tests for WorkOrderCreate Pydantic model."""

    def test_create_with_required_fields(self):
        wo = WorkOrderCreate(
            work_order_id="WO-001",
            client_id="C1",
            style_model="STYLE-A",
            planned_quantity=100,
        )
        assert wo.status == "RECEIVED"
        assert wo.actual_quantity == 0
        assert wo.qc_approved == 0

    def test_planned_quantity_must_be_positive(self):
        with pytest.raises(ValidationError):
            WorkOrderCreate(
                work_order_id="WO-001",
                client_id="C1",
                style_model="STYLE-A",
                planned_quantity=0,
            )

    def test_invalid_status_pattern_rejected(self):
        with pytest.raises(ValidationError):
            WorkOrderCreate(
                work_order_id="WO-001",
                client_id="C1",
                style_model="STYLE-A",
                planned_quantity=100,
                status="INVALID_STATUS",
            )

    def test_valid_priority_values(self):
        for p in ("HIGH", "MEDIUM", "LOW"):
            wo = WorkOrderCreate(
                work_order_id="WO-001",
                client_id="C1",
                style_model="STYLE-A",
                planned_quantity=100,
                priority=p,
            )
            assert wo.priority == p

    def test_invalid_priority_rejected(self):
        with pytest.raises(ValidationError):
            WorkOrderCreate(
                work_order_id="WO-001",
                client_id="C1",
                style_model="STYLE-A",
                planned_quantity=100,
                priority="URGENT",
            )


# ==========================================================================
# 6. WorkflowTransitionLog — ORM persistence + Pydantic validation
# ==========================================================================


class TestWorkflowTransitionLogORM:
    """Tests for WorkflowTransitionLog SQLAlchemy ORM model."""

    def test_create_transition_log(self, transactional_db):
        """WorkflowTransitionLog persists with required fields."""
        client = TestDataFactory.create_client(transactional_db, client_id="WF-C1")
        user = TestDataFactory.create_user(
            transactional_db, client_id="WF-C1", role="supervisor"
        )
        wo = TestDataFactory.create_work_order(
            transactional_db, client_id="WF-C1"
        )
        transactional_db.flush()

        log = WorkflowTransitionLog(
            work_order_id=wo.work_order_id,
            client_id="WF-C1",
            from_status=None,  # initial creation
            to_status="RECEIVED",
            trigger_source="manual",
            notes="Initial creation",
        )
        transactional_db.add(log)
        transactional_db.commit()

        fetched = (
            transactional_db.query(WorkflowTransitionLog)
            .filter(WorkflowTransitionLog.work_order_id == wo.work_order_id)
            .first()
        )
        assert fetched is not None
        assert fetched.from_status is None
        assert fetched.to_status == "RECEIVED"
        assert fetched.transition_id is not None  # autoincrement

    def test_multiple_transitions_for_same_work_order(self, transactional_db):
        """Multiple transitions can be recorded for a single work order."""
        client = TestDataFactory.create_client(transactional_db, client_id="WF-C2")
        user = TestDataFactory.create_user(
            transactional_db, client_id="WF-C2", role="supervisor"
        )
        wo = TestDataFactory.create_work_order(
            transactional_db, client_id="WF-C2"
        )
        transactional_db.flush()

        log1 = WorkflowTransitionLog(
            work_order_id=wo.work_order_id,
            client_id="WF-C2",
            from_status="RECEIVED",
            to_status="RELEASED",
            trigger_source="manual",
        )
        log2 = WorkflowTransitionLog(
            work_order_id=wo.work_order_id,
            client_id="WF-C2",
            from_status="RELEASED",
            to_status="IN_PROGRESS",
            trigger_source="manual",
        )
        transactional_db.add_all([log1, log2])
        transactional_db.commit()

        transitions = (
            transactional_db.query(WorkflowTransitionLog)
            .filter(WorkflowTransitionLog.work_order_id == wo.work_order_id)
            .order_by(WorkflowTransitionLog.transition_id)
            .all()
        )
        assert len(transitions) == 2
        assert transitions[0].to_status == "RELEASED"
        assert transitions[1].to_status == "IN_PROGRESS"


class TestWorkflowPydantic:
    """Tests for Workflow Pydantic models."""

    def test_workflow_status_enum(self):
        expected = {
            "RECEIVED",
            "RELEASED",
            "DEMOTED",
            "ACTIVE",
            "IN_PROGRESS",
            "ON_HOLD",
            "COMPLETED",
            "SHIPPED",
            "CLOSED",
            "REJECTED",
            "CANCELLED",
        }
        actual = {member.value for member in WorkflowStatusEnum}
        assert actual == expected

    def test_closure_trigger_enum(self):
        expected = {"at_shipment", "at_client_receipt", "at_completion", "manual"}
        actual = {member.value for member in ClosureTriggerEnum}
        assert actual == expected

    def test_trigger_source_enum(self):
        expected = {"manual", "automatic", "bulk", "api", "import"}
        actual = {member.value for member in TriggerSourceEnum}
        assert actual == expected

    def test_transition_create_required_fields(self):
        tc = WorkflowTransitionCreate(to_status=WorkflowStatusEnum.RELEASED)
        assert tc.trigger_source == TriggerSourceEnum.MANUAL
        assert tc.notes is None

    def test_workflow_config_defaults(self):
        wc = WorkflowConfigCreate()
        assert "RECEIVED" in wc.workflow_statuses
        assert "CLOSED" in wc.workflow_statuses
        assert wc.workflow_closure_trigger == ClosureTriggerEnum.AT_SHIPMENT
        assert "SHIPPED" in wc.workflow_optional_statuses

    def test_bulk_transition_request_validation(self):
        bt = BulkTransitionRequest(
            work_order_ids=["WO-1", "WO-2"],
            to_status=WorkflowStatusEnum.COMPLETED,
        )
        assert len(bt.work_order_ids) == 2

    def test_bulk_transition_request_empty_list_rejected(self):
        with pytest.raises(ValidationError):
            BulkTransitionRequest(
                work_order_ids=[],
                to_status=WorkflowStatusEnum.COMPLETED,
            )

    def test_workflow_templates_exist(self):
        assert "standard" in WORKFLOW_TEMPLATES
        assert "simple" in WORKFLOW_TEMPLATES
        assert "express" in WORKFLOW_TEMPLATES
        assert WORKFLOW_TEMPLATES["standard"].name == "Standard Manufacturing"


# ==========================================================================
# 7. Alert ORM models — persistence + defaults
# ==========================================================================


class TestAlertORM:
    """Tests for Alert, AlertConfig, AlertHistory SQLAlchemy ORM models."""

    def test_create_alert(self, transactional_db):
        """Alert persists with required fields."""
        client = TestDataFactory.create_client(transactional_db, client_id="ALERT-C1")
        transactional_db.flush()

        alert = Alert(
            alert_id="ALT-TEST-001",
            category="quality",
            severity="warning",
            status="active",
            title="FPY Below Threshold",
            message="First Pass Yield dropped to 91.2% (threshold: 95%)",
            client_id="ALERT-C1",
            kpi_key="fpy",
            current_value=91.2,
            threshold_value=95.0,
        )
        transactional_db.add(alert)
        transactional_db.commit()

        fetched = (
            transactional_db.query(Alert)
            .filter(Alert.alert_id == "ALT-TEST-001")
            .first()
        )
        assert fetched is not None
        assert fetched.category == "quality"
        assert fetched.severity == "warning"
        assert fetched.status == "active"
        assert fetched.current_value == pytest.approx(91.2)
        assert fetched.recommendation is None  # optional
        assert fetched.acknowledged_at is None

    def test_create_alert_config(self, transactional_db):
        """AlertConfig persists with settings."""
        client = TestDataFactory.create_client(transactional_db, client_id="ALERT-C2")
        transactional_db.flush()

        config = AlertConfig(
            config_id="ACFG-TEST-001",
            client_id="ALERT-C2",
            alert_type="quality",
            enabled=True,
            warning_threshold=95.0,
            critical_threshold=90.0,
            check_frequency_minutes=30,
        )
        transactional_db.add(config)
        transactional_db.commit()

        fetched = (
            transactional_db.query(AlertConfig)
            .filter(AlertConfig.config_id == "ACFG-TEST-001")
            .first()
        )
        assert fetched is not None
        assert fetched.enabled is True
        assert fetched.warning_threshold == pytest.approx(95.0)
        assert fetched.critical_threshold == pytest.approx(90.0)
        assert fetched.check_frequency_minutes == 30

    def test_create_alert_history(self, transactional_db):
        """AlertHistory tracks prediction accuracy."""
        client = TestDataFactory.create_client(transactional_db, client_id="ALERT-C3")
        transactional_db.flush()

        alert = Alert(
            alert_id="ALT-TEST-002",
            category="otd",
            severity="critical",
            status="active",
            title="OTD Risk",
            message="On-time delivery at risk",
            client_id="ALERT-C3",
            predicted_value=78.5,
            confidence=0.85,
        )
        transactional_db.add(alert)
        transactional_db.flush()

        history = AlertHistory(
            history_id="AH-TEST-001",
            alert_id="ALT-TEST-002",
            predicted_value=78.5,
            actual_value=80.1,
            prediction_date=datetime(2026, 2, 15),
            actual_date=datetime(2026, 2, 16),
            was_accurate=True,
            error_percent=2.04,
        )
        transactional_db.add(history)
        transactional_db.commit()

        fetched = (
            transactional_db.query(AlertHistory)
            .filter(AlertHistory.history_id == "AH-TEST-001")
            .first()
        )
        assert fetched is not None
        assert fetched.alert_id == "ALT-TEST-002"
        assert fetched.was_accurate is True
        assert fetched.error_percent == pytest.approx(2.04)

    def test_alert_config_global_no_client(self, transactional_db):
        """AlertConfig with NULL client_id is a global default."""
        config = AlertConfig(
            config_id="ACFG-GLOBAL-001",
            client_id=None,
            alert_type="efficiency",
            enabled=True,
            check_frequency_minutes=60,
        )
        transactional_db.add(config)
        transactional_db.commit()

        fetched = (
            transactional_db.query(AlertConfig)
            .filter(AlertConfig.config_id == "ACFG-GLOBAL-001")
            .first()
        )
        assert fetched.client_id is None
        assert fetched.alert_type == "efficiency"
