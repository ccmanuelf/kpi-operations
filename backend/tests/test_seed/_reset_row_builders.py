"""Client-scoped rows the seeder itself never writes, so that --reset can be
observed either reaching them or correctly leaving them alone.

Shared by test_cli_reset.py and test_cli_reset_sweep.py. Leading underscore:
not collected as a test module.
"""

from datetime import date, datetime

from sqlalchemy import insert, select

from backend.database import Base

# --- C-2: --reset must clear every client-scoped table, not just SEEDED ------


def _insert_alert_config(conn, client_id):
    """Exactly what the alert-configuration API writes the first time anyone
    edits a threshold on the demo."""
    conn.execute(
        insert(Base.metadata.tables["ALERT_CONFIG"]),
        [
            {
                "config_id": f"AC-{client_id}",
                "client_id": client_id,
                "alert_type": "OEE_LOW",
                "warning_threshold": 70.0,
                "critical_threshold": 60.0,
                "created_at": datetime(2026, 8, 1),
                "updated_at": datetime(2026, 8, 1),
            }
        ],
    )


def _insert_job(conn, client_id):
    """A JOB is a child of WORK_ORDER, so it blocks a different DELETE than
    ALERT_CONFIG does -- one inside the sweep rather than at CLIENT."""
    work_order = Base.metadata.tables["WORK_ORDER"]
    work_order_id = conn.execute(
        select(work_order.c.work_order_id).where(work_order.c.client_id == client_id).limit(1)
    ).scalar_one()
    conn.execute(
        insert(Base.metadata.tables["JOB"]),
        [
            {
                "job_id": f"JOB-{client_id}",
                "work_order_id": work_order_id,
                "client_id_fk": client_id,
                "operation_name": "OP10",
                "sequence_number": 10,
                "created_at": datetime(2026, 8, 1),
                "updated_at": datetime(2026, 8, 1),
            }
        ],
    )


def _insert_capacity_calendar(conn, client_id):
    """One of the 13 capacity_* tables the retiring seeder swept and the plan
    dropped."""
    conn.execute(
        insert(Base.metadata.tables["capacity_calendar"]),
        [
            {
                "client_id": client_id,
                "calendar_date": date(2026, 8, 3),
                "is_working_day": True,
                "shifts_available": 2,
                "created_at": datetime(2026, 8, 1),
                "updated_at": datetime(2026, 8, 1),
            }
        ],
    )


def _insert_alert_history(conn, client_id):
    """The one grandchild with NO ondelete: ALERT_HISTORY.alert_id -> ALERT
    RESTRICTs, so deleting the tenant's ALERT rows fails unless the subquery
    sweep in DEPENDENT_SWEEPS clears it first."""
    conn.execute(
        insert(Base.metadata.tables["ALERT"]),
        [
            {
                "alert_id": f"ALRT-{client_id}",
                "category": "KPI",
                "severity": "HIGH",
                "status": "ACTIVE",
                "title": "OEE below target",
                "message": "m",
                "client_id": client_id,
                "created_at": datetime(2026, 8, 1),
            }
        ],
    )
    conn.execute(
        insert(Base.metadata.tables["ALERT_HISTORY"]),
        [
            {
                "history_id": f"AH-{client_id}",
                "alert_id": f"ALRT-{client_id}",
                "prediction_date": datetime(2026, 8, 1),
                "created_at": datetime(2026, 8, 1),
            }
        ],
    )


def _insert_null_tenant_alert_history(conn, client_id):
    """The same ALERT/ALERT_HISTORY pair as above, but with the ALERT's own
    tenant column NULL and a demo WORK_ORDER as its parent.

    That one field is the difference between a row pass 1 of `_reset` selects
    and a row only pass 2 selects. `_insert_alert_history` always sets
    client_id=client_id, so its ALERT is in scope and pass 1's
    `parent.client_id IN client_ids` subquery reaches its history child --
    which is precisely why the existing suite could not see the pass-1/pass-2
    disagreement.

    Reachable through the product's own API rather than only by hand: POST
    /api/alerts treats client_id as optional (routes/alerts/crud.py:238 is a
    guard, not a requirement) while accepting a work_order_id, and resolving
    that alert is what writes the ALERT_HISTORY row.

    NOT in CHILD_ROW_BUILDERS below: that map's test asserts on rows matching
    `column == client_id`, and a NULL tenant column matches nothing, so the
    assertion would pass without the sweep ever running.
    """
    work_order = Base.metadata.tables["WORK_ORDER"]
    work_order_id = conn.execute(
        select(work_order.c.work_order_id).where(work_order.c.client_id == client_id).limit(1)
    ).scalar_one()
    conn.execute(
        insert(Base.metadata.tables["ALERT"]),
        [
            {
                "alert_id": f"ALRT-NULL-{client_id}",
                "category": "manual",
                "severity": "HIGH",
                "status": "ACTIVE",
                "title": "Raised against a work order, no client",
                "message": "m",
                "client_id": None,
                "work_order_id": work_order_id,
                "created_at": datetime(2026, 8, 1),
            }
        ],
    )
    conn.execute(
        insert(Base.metadata.tables["ALERT_HISTORY"]),
        [
            {
                "history_id": f"AH-NULL-{client_id}",
                "alert_id": f"ALRT-NULL-{client_id}",
                "prediction_date": datetime(2026, 8, 1),
                "created_at": datetime(2026, 8, 1),
            }
        ],
    )


CHILD_ROW_BUILDERS = {
    "ALERT_CONFIG": (_insert_alert_config, "ALERT_CONFIG", "client_id"),
    "JOB": (_insert_job, "JOB", "client_id_fk"),
    "capacity_calendar": (_insert_capacity_calendar, "capacity_calendar", "client_id"),
    "ALERT_HISTORY": (_insert_alert_history, "ALERT", "client_id"),
}
