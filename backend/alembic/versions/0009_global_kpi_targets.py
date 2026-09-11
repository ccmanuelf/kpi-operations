"""Global KPI target defaults, so every deployment judges a number the same way.

The report generators now read their targets from ``KPI_THRESHOLD`` instead of
carrying literals. That only works if the configuration exists, and it did not
exist anywhere in the codebase: nothing in ``backend/seed/``, no migration, no
bootstrap inserts a global (``client_id IS NULL``) row. The seeder writes four
keys per client -- efficiency, fpy, oee, otd -- and nothing else.

So the two live deployments had diverged. Checked rather than assumed:

    Render (migrate + seed from a clone)   0 global rows
    VM (MariaDB)                          10 global rows, with bands

The VM's ten were made by hand and were not reproducible from the repository, so
a fresh clone resolved no target at all for performance, PPM or absenteeism, and
no warning/critical band for anything. The same report rendered differently on
the two environments for reasons nobody could find in the source.

VALUES ARE THE VM'S, copied exactly for every key it carries, because the point
is that the two environments converge -- picking a "better" number here would
leave them disagreeing, which is the defect. Only ``fpy`` is new: the seeder
writes it per client, the report reads it, and no global fallback existed on
either environment. Its bands mirror the shape of the other higher-is-better
rows.

Net effect, per environment:

    Render   inserts all 8
    VM       inserts 1 (fpy); the other 7 are already configured

INSERT-IF-ABSENT, per key. An administrator's configured value is theirs; this
migration supplies a default where there is none and never overwrites one, which
also makes it idempotent. The VM's ids carry a ``KPI-TH-GLOBAL-`` prefix and this
migration's carry ``THR-GLOBAL-``, so neither can collide with the other's
primary key even though both describe the same metric.

Deliberately NOT inserted:

* ``rty`` and ``dpmo`` -- their report sections do not render yet (the next PR's
  subject), and a target for a metric nothing displays is configuration noise.
* ``quality``, ``throughput`` and ``wip_aging`` -- the VM carries these and
  Render does not, so they diverge too, but no report row reads them and their
  consumers have not been examined here. Supplying a target for a metric whose
  judgement path is unknown would be inventing configuration rather than
  reproducing it. Named here so the remaining divergence is on record.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_global_kpi_targets"
down_revision: Union[str, None] = "0008_coverage_active_uniqueness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: kpi_key, target, warning, critical, unit, higher_is_better.
#:
#: The bands are what the status column escalates on: below target is "At Risk",
#: and warning/critical are the configured points where it becomes Warning and
#: Critical. For a lower-is-better metric the bands ascend past the target.
DEFAULTS = (
    ("efficiency", 85.0, 75.0, 60.0, "%", "Y"),
    ("performance", 95.0, 85.0, 70.0, "%", "Y"),
    ("availability", 90.0, 80.0, 70.0, "%", "Y"),
    ("oee", 85.0, 75.0, 60.0, "%", "Y"),
    ("fpy", 97.0, 95.0, 90.0, "%", "Y"),
    ("otd", 95.0, 90.0, 80.0, "%", "Y"),
    ("ppm", 500.0, 1000.0, 2000.0, "ppm", "N"),
    ("absenteeism", 5.0, 8.0, 12.0, "%", "N"),
)

#: Stable, readable ids rather than a uuid, so a row inserted here is
#: recognisable as this migration's and a re-run finds it by key regardless.
_ID = "THR-GLOBAL-{}"


def upgrade() -> None:
    bind = op.get_bind()
    table = sa.table(
        "KPI_THRESHOLD",
        sa.column("threshold_id", sa.String),
        sa.column("client_id", sa.String),
        sa.column("kpi_key", sa.String),
        sa.column("target_value", sa.Float),
        sa.column("warning_threshold", sa.Float),
        sa.column("critical_threshold", sa.Float),
        sa.column("unit", sa.String),
        sa.column("higher_is_better", sa.String),
    )

    # Which global keys are already configured. Read once, before any write:
    # MariaDB commits DDL implicitly, and while this migration issues no DDL,
    # deciding from a single up-front read keeps the insert set independent of
    # what the loop itself has added.
    existing = {row[0] for row in bind.execute(sa.text("SELECT kpi_key FROM KPI_THRESHOLD WHERE client_id IS NULL"))}

    missing = [d for d in DEFAULTS if d[0] not in existing]
    if not missing:
        return

    op.bulk_insert(
        table,
        [
            {
                "threshold_id": _ID.format(kpi_key.upper()),
                "client_id": None,
                "kpi_key": kpi_key,
                "target_value": target,
                "warning_threshold": warning,
                "critical_threshold": critical,
                "unit": unit,
                "higher_is_better": higher,
            }
            for kpi_key, target, warning, critical, unit, higher in missing
        ],
    )


def downgrade() -> None:
    # Only the rows this migration could have created, identified by the id it
    # assigns. A global row an administrator configured carries a different id
    # and is left alone -- a downgrade must not delete someone's configuration.
    bind = op.get_bind()
    ids = [_ID.format(kpi_key.upper()) for kpi_key, *_ in DEFAULTS]
    bind.execute(
        sa.text("DELETE FROM KPI_THRESHOLD WHERE client_id IS NULL AND threshold_id IN :ids").bindparams(
            sa.bindparam("ids", value=ids, expanding=True)
        )
    )
