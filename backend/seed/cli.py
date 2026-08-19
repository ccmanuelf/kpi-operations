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
from backend.seed.coverage import SEEDED
from backend.seed.events import PLATFORM_CLIENT_ID, UserCreated
from backend.seed.generator import generate
from backend.seed.materialize import CLIENT_SCOPE_COLUMN, INSERT_ORDER, materialize
from backend.seed.profiles import PROFILES
from backend.seed.scenarios import SCENARIOS

ALLOWLIST = frozenset(s.client_id for s in SCENARIOS)


class SeedError(RuntimeError):
    """A guard refused the operation; the message is user-facing."""


def _reset(conn: Connection, client_ids: tuple[str, ...]) -> None:
    """Delete only these clients' rows, children first.

    Reverse INSERT_ORDER rather than a hand-written list: it is the same
    metadata topological sort, so the two can never drift apart.

    ATTENDANCE_HOUR_ALLOCATION has no tenant column of its own -- only a raw FK
    to ATTENDANCE_ENTRY -- and its ORM cascade only fires on session.delete(),
    not a Core delete. Without the subquery below it survives a reset as an
    orphan and collides on re-seed. (Salvaged from seed_sample_client.)
    """
    attendance = Base.metadata.tables["ATTENDANCE_ENTRY"]
    allocation = Base.metadata.tables.get("ATTENDANCE_HOUR_ALLOCATION")
    if allocation is not None:
        conn.execute(
            delete(allocation).where(
                allocation.c.attendance_entry_id.in_(
                    select(attendance.c.attendance_entry_id).where(attendance.c.client_id.in_(client_ids))
                )
            )
        )

    for name in reversed(INSERT_ORDER):
        if name not in SEEDED:
            continue
        column = CLIENT_SCOPE_COLUMN.get(name)
        if column is None:
            continue
        table = Base.metadata.tables[name]
        conn.execute(delete(table).where(table.c[column].in_(client_ids)))

    # USER carries no client-scope column of its own -- confirmed directly:
    # SEEDED - set(CLIENT_SCOPE_COLUMN) == {"USER"}, the one seeded table the
    # loop above always skips (column is None) -- so it is NEVER deleted here,
    # deliberately, even though scenarios.USERS is a fixed, known id list an
    # earlier version of this function used to delete unconditionally. That
    # version reproduced: a live survey of every FK into USER.user_id found
    # ~10 tables outside S1b's declared coverage (SAVED_FILTER,
    # ALERT.acknowledged_by/resolved_by, IMPORT_LOG, COVERAGE_ENTRY,
    # CALCULATION_ASSUMPTION, METRIC_CALCULATION_RESULT, SIMULATION_SCENARIO,
    # EVENT_STORE) with no ondelete cascade, so an unconditional USER delete
    # RESTRICTs the moment a demo user has used one of those features -- e.g.
    # saved a dashboard filter. That is the default full-allowlist --reset
    # path, not an edge case, and it is a regression the retiring
    # seed_sample_client.py never had (it never deleted USER at all).
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
