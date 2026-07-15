from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import event, create_engine
from sqlalchemy.orm import Session as SASession

from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.quality_entry import QualityEntry
from backend.orm.defect_detail import DefectDetail
from backend.orm.attendance_entry import AttendanceEntry, AbsenceType
from backend.orm.work_order import WorkOrder, WorkOrderStatus
from backend.orm.hold_entry import HoldEntry, HoldStatus
from backend.orm.production_entry import ProductionEntry
from backend.services.kpi_cause_service import (
    CauseResult,
    top_downtime_reason,
    top_defect_type,
    top_absence_type,
    late_work_orders,
    oldest_active_hold,
    oee_dominant_loss,
)

DAY = date(2026, 6, 10)


def _dt(h):
    return datetime(2026, 6, 10, h, 0, 0)


def test_top_downtime_reason_picks_max_minutes_and_share(db_session):
    db_session.add_all(
        [
            DowntimeEntry(
                downtime_entry_id="DT1",
                client_id="C1",
                shift_date=_dt(8),
                downtime_reason="Changeover",
                downtime_duration_minutes=90,
            ),
            DowntimeEntry(
                downtime_entry_id="DT2",
                client_id="C1",
                shift_date=_dt(9),
                downtime_reason="Breakdown",
                downtime_duration_minutes=30,
            ),
            DowntimeEntry(
                downtime_entry_id="DT3",
                client_id="C1",
                shift_date=_dt(10),
                downtime_reason="Changeover",
                downtime_duration_minutes=30,
            ),
        ]
    )
    db_session.commit()
    res = top_downtime_reason(db_session, "C1", DAY)
    assert res == CauseResult(kind="downtime", factor="Changeover", value=120.0, unit="min", share=0.8)


def test_top_downtime_reason_empty_day_returns_none(db_session):
    assert top_downtime_reason(db_session, "C1", DAY) is None


def test_top_defect_type_joins_quality_entry_for_date(db_session):
    db_session.add(
        QualityEntry(
            quality_entry_id="QE1",
            client_id="C1",
            work_order_id="WO1",
            shift_date=_dt(8),
            units_inspected=100,
            units_passed=90,
            units_defective=10,
            total_defects_count=10,
        )
    )
    db_session.flush()
    db_session.add_all(
        [
            DefectDetail(
                defect_detail_id="DD1", quality_entry_id="QE1", client_id_fk="C1", defect_type="Burr", defect_count=7
            ),
            DefectDetail(
                defect_detail_id="DD2", quality_entry_id="QE1", client_id_fk="C1", defect_type="Scratch", defect_count=3
            ),
        ]
    )
    db_session.commit()
    res = top_defect_type(db_session, "C1", DAY)
    assert res.kind == "defect" and res.factor == "Burr" and res.value == 7.0 and res.share == 0.7


def test_top_absence_type_groups_by_coalesced_type(db_session):
    db_session.add_all(
        [
            AttendanceEntry(
                attendance_entry_id="AE1",
                client_id="C1",
                employee_id=1,
                shift_date=_dt(8),
                scheduled_hours=8,
                is_absent=1,
                absence_type=AbsenceType.MEDICAL_LEAVE,
            ),
            AttendanceEntry(
                attendance_entry_id="AE2",
                client_id="C1",
                employee_id=2,
                shift_date=_dt(8),
                scheduled_hours=8,
                is_absent=1,
                absence_type=AbsenceType.MEDICAL_LEAVE,
            ),
            AttendanceEntry(
                attendance_entry_id="AE3",
                client_id="C1",
                employee_id=3,
                shift_date=_dt(8),
                scheduled_hours=8,
                is_absent=1,
                absence_type=AbsenceType.VACATION,
            ),
        ]
    )
    db_session.commit()
    res = top_absence_type(db_session, "C1", DAY)
    assert res.kind == "absence" and res.factor == "MEDICAL_LEAVE" and res.value == 2.0


def test_top_absence_type_does_not_crash_on_null_absence_type(db_session):
    """A legitimate absent row can have absence_type=NULL (is_absent=1, no reason).

    The driver must NOT crash decoding a coalesced literal through the Enum
    result-processor, and must still return the correct dominant factor.
    """
    db_session.add_all(
        [
            AttendanceEntry(
                attendance_entry_id="AE1",
                client_id="C1",
                employee_id=1,
                shift_date=_dt(8),
                scheduled_hours=8,
                is_absent=1,
                absence_type=None,
            ),
            AttendanceEntry(
                attendance_entry_id="AE2",
                client_id="C1",
                employee_id=2,
                shift_date=_dt(8),
                scheduled_hours=8,
                is_absent=1,
                absence_type=AbsenceType.MEDICAL_LEAVE,
            ),
            AttendanceEntry(
                attendance_entry_id="AE3",
                client_id="C1",
                employee_id=3,
                shift_date=_dt(9),
                scheduled_hours=8,
                is_absent=1,
                absence_type=AbsenceType.MEDICAL_LEAVE,
            ),
        ]
    )
    db_session.commit()
    res = top_absence_type(db_session, "C1", DAY)
    assert res.kind == "absence" and res.factor == "MEDICAL_LEAVE" and res.value == 2.0


def test_top_absence_type_null_only_day_labels_unspecified(db_session):
    """A day whose only absences have NULL absence_type yields factor 'Unspecified'."""
    db_session.add_all(
        [
            AttendanceEntry(
                attendance_entry_id="AE1",
                client_id="C1",
                employee_id=1,
                shift_date=_dt(8),
                scheduled_hours=8,
                is_absent=1,
                absence_type=None,
            ),
            AttendanceEntry(
                attendance_entry_id="AE2",
                client_id="C1",
                employee_id=2,
                shift_date=_dt(9),
                scheduled_hours=8,
                is_absent=1,
                absence_type=None,
            ),
        ]
    )
    db_session.commit()
    res = top_absence_type(db_session, "C1", DAY)
    assert res.kind == "absence" and res.factor == "Unspecified" and res.value == 2.0


def test_top_defect_type_under_fk_enforcement(tmp_path):
    """Portability guard: the DefectDetail↔QualityEntry join runs under FK enforcement (MariaDB-like)."""
    from backend.db.migrate import upgrade_to_head
    from backend.db.factories import TestDataFactory

    url = f"sqlite:///{tmp_path / 'fk.db'}"
    upgrade_to_head(url)
    eng = create_engine(url)

    @event.listens_for(eng, "connect")
    def _fk_on(conn, _rec):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    try:
        with SASession(eng) as s:
            TestDataFactory.create_client(s, client_id="C1")
            wo = TestDataFactory.create_work_order(s, client_id="C1")
            s.commit()
            qe = QualityEntry(
                quality_entry_id="QE1",
                client_id="C1",
                work_order_id=wo.work_order_id,
                shift_date=_dt(8),
                units_inspected=10,
                units_passed=8,
                units_defective=2,
                total_defects_count=2,
            )
            s.add(qe)
            s.flush()
            s.add(
                DefectDetail(
                    defect_detail_id="DD1",
                    quality_entry_id="QE1",
                    client_id_fk="C1",
                    defect_type="Burr",
                    defect_count=2,
                )
            )
            s.commit()
            res = top_defect_type(s, "C1", DAY)
            assert res.factor == "Burr"
    finally:
        eng.dispose()


def _wo(wid, required, delivered):
    return WorkOrder(
        work_order_id=wid,
        client_id="C1",
        style_model="M1",
        planned_quantity=10,
        status=WorkOrderStatus.ACTIVE,
        required_date=required,
        actual_delivery_date=delivered,
    )


def test_late_work_orders_counts_late_and_undelivered_due_that_day(db_session):
    db_session.add_all(
        [
            _wo("W1", _dt(0), _dt(0) + timedelta(days=2)),  # delivered late -> counts
            _wo("W2", _dt(0), None),  # not delivered, due today -> counts
            _wo("W3", _dt(0), _dt(0) - timedelta(hours=1)),  # delivered early -> excluded
        ]
    )
    db_session.commit()
    res = late_work_orders(db_session, "C1", DAY)
    assert res.kind == "lateOrders" and res.value == 2.0 and res.factor == "2"


def test_late_work_orders_none_when_all_on_time(db_session):
    db_session.add(_wo("W9", _dt(0), _dt(0) - timedelta(hours=1)))
    db_session.commit()
    assert late_work_orders(db_session, "C1", DAY) is None


def test_oldest_active_hold_reports_reason_and_age_days(db_session):
    db_session.add_all(
        [
            HoldEntry(
                hold_entry_id="H1",
                client_id="C1",
                work_order_id="W1",
                hold_status=HoldStatus.ON_HOLD,
                hold_date=datetime(2026, 6, 1, 8),
                resume_date=None,
            ),
            HoldEntry(
                hold_entry_id="H2",
                client_id="C1",
                work_order_id="W2",
                hold_status=HoldStatus.ON_HOLD,
                hold_date=datetime(2026, 6, 8, 8),
                resume_date=None,
            ),
            # resumed before DAY -> not active on DAY
            HoldEntry(
                hold_entry_id="H3",
                client_id="C1",
                work_order_id="W3",
                hold_status=HoldStatus.ON_HOLD,
                hold_date=datetime(2026, 5, 1, 8),
                resume_date=datetime(2026, 6, 5, 8),
            ),
        ]
    )
    db_session.commit()
    res = oldest_active_hold(db_session, "C1", DAY)
    assert res.kind == "hold" and res.unit == "days" and res.value == 9.0  # 2026-06-10 - 2026-06-01
    assert res.factor  # hold_reason (may be None -> "Unspecified")


def test_oldest_active_hold_none_when_no_active_holds(db_session):
    assert oldest_active_hold(db_session, "C1", DAY) is None


def _pe(pid, perf):
    return ProductionEntry(
        production_entry_id=pid,
        client_id="C1",
        product_id=1,
        shift_id=1,
        production_date=_dt(8),
        shift_date=_dt(8),
        units_produced=100,
        run_time_hours=Decimal("8.0"),
        employees_assigned=5,
        performance_percentage=Decimal(str(perf)),
        entered_by="u1",
    )


def test_oee_dominant_loss_availability(db_session):
    # 1 entry -> scheduled 8h; 240 min downtime -> 4h -> availability 50 (loss 50, dominant)
    db_session.add(_pe("PE1", 95))
    db_session.add(
        QualityEntry(
            quality_entry_id="QE1",
            client_id="C1",
            work_order_id="WO1",
            shift_date=_dt(8),
            units_inspected=100,
            units_passed=100,
            units_defective=0,
            total_defects_count=0,
        )
    )
    db_session.add(
        DowntimeEntry(
            downtime_entry_id="DT1",
            client_id="C1",
            shift_date=_dt(9),
            downtime_reason="Breakdown",
            downtime_duration_minutes=240,
        )
    )
    db_session.commit()
    res = oee_dominant_loss(db_session, "C1", DAY)
    assert res.kind == "downtime" and res.factor == "Breakdown"


def test_oee_dominant_loss_quality(db_session):
    db_session.add(_pe("PE1", 98))  # perf loss 2, no downtime -> avail loss 0
    db_session.add(
        QualityEntry(
            quality_entry_id="QE1",
            client_id="C1",
            work_order_id="WO1",
            shift_date=_dt(8),
            units_inspected=100,
            units_passed=70,
            units_defective=30,
            total_defects_count=30,
        )
    )  # quality 70, loss 30
    db_session.flush()
    db_session.add(
        DefectDetail(
            defect_detail_id="DD1", quality_entry_id="QE1", client_id_fk="C1", defect_type="Burr", defect_count=30
        )
    )
    db_session.commit()
    res = oee_dominant_loss(db_session, "C1", DAY)
    assert res.kind == "defect" and res.factor == "Burr"


def test_oee_dominant_loss_performance_component(db_session):
    db_session.add(_pe("PE1", 60))  # perf loss 40 dominant; no downtime, quality 100
    db_session.add(
        QualityEntry(
            quality_entry_id="QE1",
            client_id="C1",
            work_order_id="WO1",
            shift_date=_dt(8),
            units_inspected=100,
            units_passed=100,
            units_defective=0,
            total_defects_count=0,
        )
    )
    db_session.commit()
    res = oee_dominant_loss(db_session, "C1", DAY)
    assert res == CauseResult(kind="component", factor="performance", value=None, unit="", share=None)


def test_oee_dominant_loss_none_without_production(db_session):
    assert oee_dominant_loss(db_session, "C1", DAY) is None
