from datetime import date, datetime

from sqlalchemy import event, create_engine
from sqlalchemy.orm import Session as SASession

from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.quality_entry import QualityEntry
from backend.orm.defect_detail import DefectDetail
from backend.orm.attendance_entry import AttendanceEntry, AbsenceType
from backend.services.kpi_cause_service import (
    CauseResult,
    top_downtime_reason,
    top_defect_type,
    top_absence_type,
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
