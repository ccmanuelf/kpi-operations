"""Entry point for the demo seeder.

  python -m backend.seed.cli --profile full --as-of 2026-08-18

Prod-safety carries over from seed_sample_client.py (removed in S1c) unchanged (spec section 9):
INSERT-only, refuses any client not on the allowlist, never creates or drops
schema -- Alembic is the single schema mechanism -- and --reset deletes only
allowlisted clients' rows.
"""

import argparse
import os
import sys
from datetime import date
from typing import Optional

from sqlalchemy import Connection, Engine, MetaData, and_, create_engine, delete, or_, select, update
from sqlalchemy.sql.elements import ColumnElement

from backend.audit import audit_suppressed
from backend.database import Base
from backend.seed.events import PLATFORM_CLIENT_ID, UserCreated
from backend.seed.generator import generate
from backend.seed.materialize import INSERT_ORDER, materialize
from backend.seed.profiles import PROFILES
from backend.seed.scenarios import SCENARIOS

ALLOWLIST = frozenset(s.client_id for s in SCENARIOS)

#: The explicit override for tables whose tenant column cannot be DERIVED --
#: either because there is no ForeignKey to CLIENT.client_id to follow (the
#: EMPLOYEE case, the only one today), or because there is more than one and
#: which of them scopes a row is a judgement no walk can make. Consulted before
#: the ambiguity check in _derive_client_scoped_tables, so naming a table here
#: genuinely resolves it.
#:
#: USER.client_id_assigned is the same bare shape and is DELIBERATELY ABSENT:
#: USER is never deleted by --reset (see _reset's closing comment) because it
#: is user state, not client fixture data, and user creation is idempotent
#: instead. AUDIT_ENTRY.client_id and EVENT_STORE.client_id are bare columns
#: too and are also deliberately absent: they are append-only ledgers rather
#: than client fixture data, this seeder writes zero rows to either (it runs
#: under audit_suppressed()), seed_sample_client.py (removed in S1c) never
#: touched them, and neither carries a foreign key, so neither can block a
#: delete.
_UNDERIVABLE_CLIENT_SCOPE_COLUMNS = {"EMPLOYEE": "client_id_assigned"}


class SeedError(RuntimeError):
    """A guard refused the operation; the message is user-facing."""


class AmbiguousClientScope(SeedError):
    """A table carries more than one ForeignKey to CLIENT, so which column
    scopes it to a tenant is not derivable."""


def _derive_client_scoped_tables(metadata: Optional[MetaData] = None) -> dict[str, str]:
    """Every tenant-scoped table in the schema, mapped to its client column.

    Derived from Base.metadata, not hand-listed. Any table carrying a
    ForeignKey to CLIENT.client_id is client fixture data by construction, so
    a table added later is swept automatically -- which is what
    seed_sample_client.py's (removed in S1c) hand-written RESET_TABLE_ORDER
    could not do.

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
    for table in (metadata or Base.metadata).sorted_tables:
        # Collect ALL of them, then insist there is exactly one. Assigning
        # inside the loop instead would silently keep whichever ForeignKey the
        # column order happened to put last, and --reset would then filter that
        # table by the wrong column -- deleting rows belonging to a client that
        # was never asked for, or leaving the requested one's rows behind to
        # collide on re-seed. Neither failure names its cause. No table has two
        # today (asserted by test_no_table_has_an_ambiguous_client_scope), so
        # this costs nothing until the day it matters.
        if table.name in _UNDERIVABLE_CLIENT_SCOPE_COLUMNS:
            # Consulted BEFORE the ambiguity check, not after, or the escape
            # hatch the error message names would not exist: the raise happens
            # inside this loop while `scoped.update(...)` runs after it, so a
            # table added to the override map would still raise and the
            # instruction would be a dead end. (Raised by the DeepSeek
            # cross-model review of this very change.)
            continue
        candidates = [c.name for c in table.columns for fk in c.foreign_keys if fk.column.table.name == "CLIENT"]
        if len(candidates) > 1:
            raise AmbiguousClientScope(
                f"{table.name} carries {len(candidates)} ForeignKeys to CLIENT ({', '.join(sorted(candidates))}); "
                "which one scopes a row to a tenant cannot be derived. Add it to "
                "_UNDERIVABLE_CLIENT_SCOPE_COLUMNS naming the correct column."
            )
        if candidates:
            scoped[table.name] = candidates[0]
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


def _self_referential_columns() -> tuple:
    """Every swept table's own foreign keys back into ITSELF, as
    (table, column).

    DERIVED from Base.metadata rather than naming PRODUCTION_LINE, so a second
    self-reference added later is handled without a code change here.

    PRODUCTION_LINE.parent_line_id -> PRODUCTION_LINE.line_id is the only one
    in all 60 tables today, it is nullable, ondelete is None, and it is inside
    the --reset sweep. InnoDB checks the constraint per row as the DELETE
    visits rows, and `DELETE FROM PRODUCTION_LINE WHERE client_id IN (...)` is
    planned over uq_production_line_client_code (client_id, line_code), so the
    visit order is LINE_CODE order: a parent whose code sorts before its
    child's is deleted first and raises `Cannot delete or update a parent
    row`, breaking --reset for that tenant from then on. Measured on
    mariadb:11.4.12 -- 'SEW-01' with a 'SEW-01-A' section under it raises
    1451; the same pair named so the child sorts first does not. A section
    named after its line is the ordinary case, and one supervisor-level
    `POST /api/production-lines/` is enough to reach it.

    It is LATENT, not live: the seeder itself never writes a line hierarchy,
    so the seed suite is green on InnoDB either way today. Breaking the
    self-reference first removes the dependence on visit order entirely.

    STATED LIMITATION, deliberate: only CLIENT_SCOPED_TABLES are scanned,
    because the UPDATE needs a tenant column to filter on. A DEPENDENT_SWEEPS
    grandchild with a self-reference would not be found; there is none today,
    and those three are cleared wholesale by subquery in a single statement
    before anything else runs. A NOT NULL self-reference is not filtered out
    either: the UPDATE would fail loudly on the first tenant that owns such a
    row rather than silently leaving the hazard in place, which is the right
    failure for a shape that needs a different strategy entirely.
    """
    found = set()
    for name in CLIENT_SCOPED_TABLES:
        table = Base.metadata.tables[name]
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name == name:
                    found.add((name, column.name))
    return tuple(sorted(found))


#: (table, column) pairs whose value must be NULLed before the sweep deletes
#: the table, because they point back into the same table.
SELF_REFERENTIAL_SWEEPS = _self_referential_columns()


def _nullable_tenant_children() -> tuple:
    """Swept children whose OWN tenant column is nullable and which hold a
    ForeignKey into another swept table, as
    (child, child fk column, child scope column, parent, parent pk).

    A row here with a NULL tenant matches no IN clause, so the scoped DELETE
    never selects it -- and it then RESTRICTs its parent. No sweep ORDER can fix
    that, because the row is never visited at all, which is why
    test_reset_ordering.py cannot see this class either.

    Derived rather than listed: two edges exist today (FLOATING_POOL.employee_id
    -> EMPLOYEE, ALERT.work_order_id -> WORK_ORDER) and a third added later is
    handled without a code change here.
    """
    found = set()
    for name, scope in CLIENT_SCOPED_TABLES.items():
        table = Base.metadata.tables[name]
        if not table.columns[scope].nullable:
            continue
        for column in table.columns:
            if column.name == scope:
                continue
            for fk in column.foreign_keys:
                parent = fk.column.table.name
                if parent in CLIENT_SCOPED_TABLES and parent != name:
                    found.add((name, column.name, scope, parent, fk.column.name))
    return tuple(sorted(found))


#: Children invisible to the scoped sweep because their own tenant column is NULL.
NULLABLE_TENANT_SWEEPS = _nullable_tenant_children()


def _parents_widened_by_the_nullable_tenant_sweep() -> tuple:
    """Tables that sit on BOTH sides of the reset: named as a PARENT in
    DEPENDENT_SWEEPS and as a CHILD in NULLABLE_TENANT_SWEEPS.

    This is the intersection where the two passes interact, and it is exactly
    the set for which "the parent rows in scope" and "the parent rows this
    reset deletes" are DIFFERENT sets. Pass 1 clears a grandchild by selecting
    its parent, and if it selects only `parent.scope IN client_ids` while pass
    2 goes on to delete additional NULL-tenant parent rows, the grandchildren
    of those extra rows are never visited: orphaned where foreign keys are off
    (main()'s bare engine), an IntegrityError that rolls back the whole
    reset+reseed where they are on (MariaDB/InnoDB, i.e. production, and the
    DEMO_MODE boot path where run_best_effort swallows it into a warning).

    ALERT is the one member today and it is reachable through the product's
    own API, not by hand: POST /api/alerts treats client_id as optional
    (routes/alerts/crud.py:238 is a guard, not a requirement) while accepting
    a work_order_id, and resolving that alert writes the ALERT_HISTORY row.

    DERIVED rather than naming ALERT, matching this module's other four
    derived sets, and PINNED by
    test_the_widened_reset_parents_are_exactly_the_known_one. The widening
    itself is generic -- _rows_deleted_by_reset walks NULLABLE_TENANT_SWEEPS,
    so a second member is handled without a code change here -- but the guard
    still earns its place: each member is a shape whose two passes must be
    re-argued (a NOT NULL tenant column, a self-referential edge, or a
    grandchild with its own children would each need a different answer), and
    a set that silently grows is how this bug got in.
    """
    dependent_parents = {parent for _, _, parent, _ in DEPENDENT_SWEEPS}
    nullable_children = {child for child, _, _, _, _ in NULLABLE_TENANT_SWEEPS}
    return tuple(sorted(dependent_parents & nullable_children))


#: Pass-1 parents whose deleted-row set is wider than their in-scope set.
WIDENED_RESET_PARENTS = _parents_widened_by_the_nullable_tenant_sweep()


def _rows_deleted_by_reset(table_name: str, client_ids: tuple[str, ...]) -> ColumnElement:
    """THE definition of "rows of `table_name` that this reset deletes".

    One source of truth, consulted by pass 2 (which executes the delete) and
    by pass 1 (which must clear the children of every row pass 2 will remove,
    not merely the in-scope ones). Duplicating the predicate across the two
    passes is what let them disagree: pass 1 had no knowledge of the set pass
    2 widens to, so a NULL-tenant ALERT pointing at a demo WORK_ORDER was
    deleted with its ALERT_HISTORY children left behind. See
    _parents_widened_by_the_nullable_tenant_sweep.

    `scope IN client_ids` is the base term -- what pass 4 deletes -- so the
    NULLABLE_TENANT_SWEEPS terms reduce to the NULL-tenant case: a row whose
    own tenant column is NULL and which points at an in-scope parent. A row
    explicitly owned by ANOTHER tenant is matched by neither term and stays
    safe, which is the guarantee pass 2's `or_` carried before.
    """
    table = Base.metadata.tables[table_name]
    scope = CLIENT_SCOPED_TABLES[table_name]
    terms: list = [table.c[scope].in_(client_ids)]
    for child_name, child_column, child_scope, parent_name, parent_pk in NULLABLE_TENANT_SWEEPS:
        if child_name != table_name:
            continue
        parent = Base.metadata.tables[parent_name]
        parent_scope = CLIENT_SCOPED_TABLES[parent_name]
        terms.append(
            and_(
                table.c[child_column].in_(select(parent.c[parent_pk]).where(parent.c[parent_scope].in_(client_ids))),
                table.c[child_scope].is_(None),
            )
        )
    return or_(*terms)


def _cascade_children_of_employee() -> tuple:
    """Child tables whose employee_id FK to EMPLOYEE declares ondelete=CASCADE.

    EMPLOYEE is the only swept table whose children can belong to a DIFFERENT
    tenant than the parent -- an employee may be shared across clients, whereas
    a work order, hold or production line belongs to exactly one. So it is the
    only table where deleting a demo row can silently remove a real tenant's
    data. Two such children exist today.
    """
    found = set()
    for name in CLIENT_SCOPED_TABLES:
        table = Base.metadata.tables[name]
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name == "EMPLOYEE" and fk.ondelete == "CASCADE":
                    found.add(name)
    return tuple(sorted(found))


#: Client-scoped children whose employee_id FK to EMPLOYEE cascades.
CASCADE_CHILDREN_OF_EMPLOYEE = _cascade_children_of_employee()


def _reset(conn: Connection, client_ids: tuple[str, ...]) -> None:
    """Delete only these clients' rows, children first.

    Four passes, over CLIENT_SCOPED_TABLES (not SEEDED: --reset must clear
    everything a tenant owns, not only what this seeder wrote -- see
    _derive_client_scoped_tables):

    1. DEPENDENT_SWEEPS: tables with no tenant column of their own, only a
       raw FK into a scoped table -- cleared by subquery through their
       parent. The subquery selects every parent row THIS RESET DELETES
       (_rows_deleted_by_reset), not merely the in-scope ones: for a parent
       pass 2 also widens, the two differ, and the difference is a
       grandchild orphaned or an IntegrityError. See
       _parents_widened_by_the_nullable_tenant_sweep.
    2. NULLABLE_TENANT_SWEEPS: children whose OWN tenant column is nullable,
       selected by their PARENT's scope as well as their own -- a NULL
       tenant column matches no IN clause, so these are invisible to the
       ordinary scoped sweep in pass 4 and would otherwise strand and
       RESTRICT their parent's delete. Same predicate pass 1 used, by
       construction. See its docstring.
    3. SELF_REFERENTIAL_SWEEPS: NULLs every swept table's foreign keys back
       into itself first, which no table-level ordering can resolve. See
       its docstring.
    4. Every client-scoped table, in reverse INSERT_ORDER -- the same
       metadata topological sort the inserts use, so the two can never
       drift apart. EMPLOYEE's delete additionally excludes any employee id
       referenced by a CASCADE_CHILDREN_OF_EMPLOYEE row (own client_id)
       belonging to a tenant outside this sweep: EMPLOYEE_CLIENT_ASSIGNMENT
       and EMPLOYEE_LINE_ASSIGNMENT both declare ondelete=CASCADE on
       employee_id, so without this exclusion deleting a shared demo
       employee would silently cascade-delete a real tenant's assignment
       row -- no IntegrityError, no row count to notice.

    STATED LIMITATION: pass 4's employee guard and pass 2's FLOATING_POOL
    edge can conflict. FLOATING_POOL.employee_id is NOT NULL with no
    ondelete, so if a tenant OUTSIDE this sweep owns a FLOATING_POOL row
    pointing at a demo employee, protecting that row (pass 2) and deleting
    the employee (pass 4) are mutually exclusive: the DELETE raises
    IntegrityError. That is accepted, correct behaviour -- refusing to
    silently delete a real tenant's row and failing loudly beats corrupting
    it. The obvious repair, sparing the employee too, was rejected:
    EMPLOYEE.employee_code carries a GLOBAL unique index
    (ix_EMPLOYEE_employee_code, not per-client), so a spared employee
    collides with the next re-seed's employee_code. Fixing that properly
    needs employee-creation idempotency in the materializer (resolve the
    existing PK into the IdMap rather than insert, mirroring what S1b did
    for USER) -- a materializer change, disproportionate to a scenario that
    cannot arise while demo tenants are the only tenants. Note the
    asymmetry: ALERT.work_order_id, pass 2's other edge, IS nullable, so it
    has no equivalent problem.

    SECOND STATED LIMITATION, confirmed empirically rather than hypothesised:
    pass 4's employee guard collides with employee_code uniqueness on its OWN,
    with no FLOATING_POOL involved at all. Sparing a shared employee (pass 4)
    and then re-seeding the SAME client with the SAME profile/seed -- the
    ordinary --reset workflow -- makes materialize() try to INSERT a fresh
    EMPLOYEE row carrying the identical, deterministic employee_code the
    spared row already holds, because EMPLOYEE has no re-seed idempotency the
    way USER does (seed() never checks for an existing employee_code before
    materializing). That raises the same GLOBAL-unique-index IntegrityError
    named above, and engine.begin() rolls the whole reset+reseed transaction
    back, leaving the database exactly as it was -- the shared employee's
    foreign assignment survives via the rollback rather than via a clean
    scoped sweep. Accepted for the same reason as the first limitation: a
    loud, fully-rolled-back failure beats silently deleting a real tenant's
    row, and the proper fix is the same deferred one -- employee-creation
    idempotency in the materializer. Pinned by
    test_reset_does_not_delete_an_employee_shared_with_a_foreign_tenant and
    its EMPLOYEE_LINE_ASSIGNMENT variant, both of which assert
    pytest.raises(IntegrityError) rather than a clean success.

    USER is never deleted here -- see the comment closing this function.
    """
    for child_name, child_column, parent_name, parent_pk in DEPENDENT_SWEEPS:
        child = Base.metadata.tables[child_name]
        parent = Base.metadata.tables[parent_name]
        # Selected against EVERY parent row this reset deletes, not just the
        # in-scope ones: for a parent that pass 2 also widens (ALERT today),
        # `parent.scope IN client_ids` alone leaves the grandchildren of the
        # NULL-tenant parent rows behind. See _rows_deleted_by_reset.
        conn.execute(
            delete(child).where(
                child.c[child_column].in_(
                    select(parent.c[parent_pk]).where(_rows_deleted_by_reset(parent_name, client_ids))
                )
            )
        )

    for child_name in sorted({child for child, _, _, _, _ in NULLABLE_TENANT_SWEEPS}):
        child = Base.metadata.tables[child_name]
        # Selected by PARENT in scope, not by own tenant -- that is the whole
        # point, and it is the same predicate pass 1 just used to find these
        # rows' children. A row explicitly owned by another tenant is matched
        # by no term and stays safe even when it points at a demo parent.
        conn.execute(delete(child).where(_rows_deleted_by_reset(child_name, client_ids)))

    for table_name, column_name in SELF_REFERENTIAL_SWEEPS:
        table = Base.metadata.tables[table_name]
        scope = CLIENT_SCOPED_TABLES[table_name]
        conn.execute(update(table).where(table.c[scope].in_(client_ids)).values({column_name: None}))

    # An employee shared with a tenant outside the sweep must survive: both of
    # its cascade children carry their own client_id, so deleting the employee
    # would remove a REAL tenant's assignment with no error at all. Their demo
    # assignment rows are still cleared by the scoped sweep below, which is the
    # correct outcome; only the shared EMPLOYEE row is spared.
    shared_employee_ids: set = set()
    for child_name in CASCADE_CHILDREN_OF_EMPLOYEE:
        child = Base.metadata.tables[child_name]
        shared_employee_ids.update(
            conn.execute(select(child.c.employee_id).where(child.c.client_id.notin_(client_ids))).scalars().all()
        )

    for name in reversed(INSERT_ORDER):
        column = CLIENT_SCOPED_TABLES.get(name)
        if column is None:
            continue
        table = Base.metadata.tables[name]
        statement = delete(table).where(table.c[column].in_(client_ids))
        if name == "EMPLOYEE" and shared_employee_ids:
            statement = statement.where(table.c.employee_id.notin_(shared_employee_ids))
        conn.execute(statement)

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
    # seed_sample_client.py (removed in S1c) never had (it never deleted USER
    # at all).
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
