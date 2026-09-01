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
    ALERT_CONFIG does -- one inside the sweep rather than at CLIENT.

    NOT in CHILD_ROW_BUILDERS since S3 seeded JOB: that map's test asserts the
    table holds ZERO rows for the client afterwards, which a seeded table can
    never satisfy -- --reset re-seeds, so its own JOB rows are back. The
    planted-row case it used to cover moved to test_jobs.py, which asserts on
    THIS row's id rather than on the table's count and so still fails if the
    sweep stops reaching JOB.

    The id deliberately does not collide with the seeder's
    `{work_order_id}-OP{n}` format (seed/emitters_operations.py::job_id_for);
    a collision would surface as a PK error rather than as the sweep finding
    it survived."""
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


def _insert_capacity_schedule(conn, client_id):
    """One of the 13 capacity_* tables the retiring seeder swept and the plan
    dropped.

    Was `capacity_calendar` until the seeder began writing it. The case needs a
    table the seeder does NOT write, or "cleared by the sweep" and "re-seeded
    immediately after" are indistinguishable -- which is exactly how it failed:
    59 legitimately re-seeded rows read as 59 rows that survived the sweep.
    `capacity_schedule` is the same FK cluster and still unseeded."""
    conn.execute(
        insert(Base.metadata.tables["capacity_schedule"]),
        [
            {
                "client_id": client_id,
                "schedule_name": "Reset sweep fixture",
                "period_start": date(2026, 8, 3),
                "period_end": date(2026, 8, 31),
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
    "capacity_schedule": (_insert_capacity_schedule, "capacity_schedule", "client_id"),
    "ALERT_HISTORY": (_insert_alert_history, "ALERT", "client_id"),
}
