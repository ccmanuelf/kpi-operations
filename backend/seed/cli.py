"""Entry point for the demo seeder.

  python -m backend.seed.cli --profile full --as-of 2026-08-18

Prod-safety carries over from seed_sample_client unchanged (spec section 9):
INSERT-only, refuses any client not on the allowlist, never creates or drops
schema -- Alembic is the single schema mechanism -- and --reset deletes only
allowlisted clients' rows.
"""

import argparse
import os
import sys
from datetime import date
from typing import Optional

from sqlalchemy import Connection, Engine, create_engine, delete, select

from backend.audit import audit_suppressed
from backend.database import Base
from backend.seed.events import PLATFORM_CLIENT_ID, UserCreated
from backend.seed.generator import generate
from backend.seed.materialize import INSERT_ORDER, materialize
from backend.seed.profiles import PROFILES
from backend.seed.scenarios import SCENARIOS

ALLOWLIST = frozenset(s.client_id for s in SCENARIOS)

#: Tenant-scoped tables with NO ForeignKey to CLIENT.client_id, so no
#: derivation can find them. Only EMPLOYEE belongs here.
#:
#: USER.client_id_assigned is the same bare shape and is DELIBERATELY ABSENT:
#: USER is never deleted by --reset (see _reset's closing comment) because it
#: is user state, not client fixture data, and user creation is idempotent
#: instead. AUDIT_ENTRY.client_id and EVENT_STORE.client_id are bare columns
#: too and are also deliberately absent: they are append-only ledgers rather
#: than client fixture data, this seeder writes zero rows to either (it runs
#: under audit_suppressed()), the retiring seed_sample_client.py never touched
#: them, and neither carries a foreign key, so neither can block a delete.
_UNDERIVABLE_CLIENT_SCOPE_COLUMNS = {"EMPLOYEE": "client_id_assigned"}


def _derive_client_scoped_tables() -> dict[str, str]:
    """Every tenant-scoped table in the schema, mapped to its client column.

    Derived from Base.metadata, not hand-listed. Any table carrying a
    ForeignKey to CLIENT.client_id is client fixture data by construction, so
    a table added later is swept automatically -- which is what
    seed_sample_client's hand-written RESET_TABLE_ORDER could not do.

    Deliberately NOT `SEEDED`. What the seeder WRITES and what --reset must
    CLEAR are different sets: 45 tables hold a FK into CLIENT while the
    seeder writes 23, and restricting the sweep to the seeded ones left every
    other one (ALERT_CONFIG, JOB, EQUIPMENT, the 13 capacity_* tables, ...)
    holding rows that RESTRICT the DELETE FROM "CLIENT" at the end of the
    sweep. That is not an edge case: an ALERT_CONFIG row is what the
    alert-configuration API writes the first time anyone edits a threshold on
    the demo.
    """
    scoped = {"CLIENT": "client_id"}
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name == "CLIENT":
                    scoped[table.name] = column.name
    scoped.update(_UNDERIVABLE_CLIENT_SCOPE_COLUMNS)
    return scoped


#: name -> the column that scopes it to a tenant.
CLIENT_SCOPED_TABLES = _derive_client_scoped_tables()

#: Grandchildren: tables OUTSIDE CLIENT_SCOPED_TABLES that hold a ForeignKey
#: into one of them, as (child, child fk column, parent, parent pk column).
#: Swept by subquery before the scoped sweep, because they have no tenant
#: column of their own to filter on.
#:
#: Every one is swept explicitly even though two of the three declare
#: ondelete=CASCADE at the DB level: SQLite honours ON DELETE CASCADE only
#: under PRAGMA foreign_keys=ON, and the bare create_engine(url) in main()
#: does not set it (the app's SQLiteProvider does; this seeder's own engine
#: does not). Relying on the declared cascade would leave orphans on exactly
#: the path --reset exists to clean.
#:
#: test_no_table_outside_the_reset_sweep_holds_a_foreign_key_into_it proves
#: this list is complete against live metadata, so a new grandchild fails the
#: build rather than --reset on a customer's VM.
DEPENDENT_SWEEPS = (
    # ondelete=None -- a hard blocker, nothing would clean this up.
    ("ALERT_HISTORY", "alert_id", "ALERT", "alert_id"),
    # ondelete=CASCADE, swept explicitly for the PRAGMA reason above.
    ("ASSUMPTION_CHANGE", "assumption_id", "CALCULATION_ASSUMPTION", "assumption_id"),
    ("ATTENDANCE_HOUR_ALLOCATION", "attendance_entry_id", "ATTENDANCE_ENTRY", "attendance_entry_id"),
)


class SeedError(RuntimeError):
    """A guard refused the operation; the message is user-facing."""


def _reset(conn: Connection, client_ids: tuple[str, ...]) -> None:
    """Delete only these clients' rows, children first.

    Two passes. DEPENDENT_SWEEPS first: those tables carry no tenant column,
    only a raw FK into a scoped table, so they are cleared by subquery through
    their parent. Then every client-scoped table in reverse INSERT_ORDER --
    the same metadata topological sort the inserts use, so the two can never
    drift apart.

    The sweep covers CLIENT_SCOPED_TABLES, not SEEDED: --reset must clear
    everything a tenant owns, not only what this seeder wrote. See
    _derive_client_scoped_tables.
    """
    for child_name, child_column, parent_name, parent_pk in DEPENDENT_SWEEPS:
        child = Base.metadata.tables[child_name]
        parent = Base.metadata.tables[parent_name]
        parent_scope = CLIENT_SCOPED_TABLES[parent_name]
        conn.execute(
            delete(child).where(
                child.c[child_column].in_(select(parent.c[parent_pk]).where(parent.c[parent_scope].in_(client_ids)))
            )
        )

    for name in reversed(INSERT_ORDER):
        column = CLIENT_SCOPED_TABLES.get(name)
        if column is None:
            continue
        table = Base.metadata.tables[name]
        conn.execute(delete(table).where(table.c[column].in_(client_ids)))

    # USER carries no ForeignKey to CLIENT -- only a bare client_id_assigned
    # column, the same shape EMPLOYEE has -- so nothing derives it and it is
    # deliberately left out of _UNDERIVABLE_CLIENT_SCOPE_COLUMNS above. It is
    # therefore NEVER deleted here, deliberately, even though scenarios.USERS
    # is a fixed, known id list an earlier version of this function used to
    # delete unconditionally. That version reproduced: a live survey of every
    # FK into USER.user_id found ~10 tables outside S1b's declared coverage
    # (SAVED_FILTER, ALERT.acknowledged_by/resolved_by, IMPORT_LOG,
    # COVERAGE_ENTRY, CALCULATION_ASSUMPTION, METRIC_CALCULATION_RESULT,
    # SIMULATION_SCENARIO, EVENT_STORE) with no ondelete cascade, so an
    # unconditional USER delete RESTRICTs the moment a demo user has used one
    # of those features -- e.g. saved a dashboard filter. That is the default
    # full-allowlist --reset path, not an edge case, and it is a regression
    # the retiring seed_sample_client.py never had (it never deleted USER at
    # all).
    # User creation is idempotent instead -- see seed() below -- which also
    # means a demo user's saved filters and acknowledged alerts genuinely
    # survive a reset, arguably correct since that is user state, not client
    # fixture data.


@audit_suppressed()
def seed(
    engine: Engine,
    *,
    client_ids: tuple[str, ...],
    profile_name: str,
    seed_value: int,
    as_of: date,
    reset: bool,
) -> dict[str, int]:
    unknown = sorted(set(client_ids) - ALLOWLIST)
    if unknown:
        raise SeedError(
            f"refusing to seed client(s) not on the demo allowlist: {', '.join(unknown)}. "
            "This seeder is INSERT-only against demo tenants and must never touch a real one."
        )
    profile = PROFILES.get(profile_name)
    if profile is None:
        raise SeedError(f"unknown profile {profile_name!r}; known: {', '.join(sorted(PROFILES))}")

    scenarios = tuple(s for s in SCENARIOS if s.client_id in client_ids)
    events = generate(scenarios, profile, seed=seed_value, as_of=as_of)
    # generator.py's _generate_platform now scopes ClientAccessGranted to the
    # scenarios it was actually given, so this is redundant defence, not the
    # primary fix -- kept because a seeder whose whole policy is "never touch
    # anything outside the target clients" should not rely on a single
    # upstream module to enforce that alone. A no-op whenever client_ids
    # matches what was passed to generate() (every current caller).
    client_id_set = set(client_ids)
    events = [e for e in events if e.client_id in client_id_set or e.client_id == PLATFORM_CLIENT_ID]

    with engine.begin() as conn:
        if reset:
            _reset(conn, tuple(client_ids))
        # USER is never deleted by _reset() (see its docstring) so re-seeding
        # must not try to re-INSERT a demo user that is already there.
        # Idempotent rather than delete-then-recreate: query which of the
        # seeded ids already exist and drop their UserCreated events before
        # materializing. USER_CLIENT_ASSIGNMENT's FK to USER stays satisfied
        # either way, since the row it points at is never removed.
        user_table = Base.metadata.tables["USER"]
        existing_user_ids = {row[0] for row in conn.execute(select(user_table.c.user_id))}
        events = [e for e in events if not (isinstance(e, UserCreated) and e.user_id in existing_user_ids)]
        return materialize(conn, events, profile)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.seed.cli",
        description="Seed the demo dataset (INSERT-only, allowlist-guarded).",
    )
    parser.add_argument(
        "--client",
        dest="client",
        action="append",
        default=None,
        help=f"repeatable; one of {sorted(ALLOWLIST)}; default = every allowlisted client",
    )
    parser.add_argument("--profile", default="full", help="dataset size preset (default: full)")
    parser.add_argument("--seed", type=int, default=1234, help="RNG seed (default: 1234)")
    parser.add_argument(
        "--as-of",
        dest="as_of",
        type=date.fromisoformat,
        default=date.today(),
        help="YYYY-MM-DD anchor for the seeded window (default: today)",
    )
    parser.add_argument("--reset", action="store_true", help="delete allowlisted clients' rows before seeding")
    return parser


def main(argv: Optional[list] = None) -> int:
    """Entry point (CLI / VM invocation). `seed()` is wrapped in
    `audit_suppressed()`, not this function -- a --reset re-seed writes tens
    of thousands of rows describing machine-generated fixture data, not a
    human decision; see backend/audit/context.py."""
    args = build_parser().parse_args(argv)
    client_ids = tuple(args.client) if args.client else tuple(ALLOWLIST)

    database_url = os.getenv("DATABASE_URL", "sqlite:///database/kpi_platform.db")
    engine = create_engine(database_url)
    try:
        counts = seed(
            engine,
            client_ids=client_ids,
            profile_name=args.profile,
            seed_value=args.seed,
            as_of=args.as_of,
            reset=args.reset,
        )
    except SeedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        engine.dispose()

    for name, count in sorted(counts.items()):
        print(f"{name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
