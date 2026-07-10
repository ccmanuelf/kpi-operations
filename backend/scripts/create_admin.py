"""
First-admin management command for a fresh production database.

Creates the initial admin account and refuses anywhere it shouldn't run:
  - unmigrated database (no alembic_version / USER table)  -> exit 1
  - any admin already exists (use the admin UI instead)    -> exit 1
  - password fails the SEC-002 strength policy             -> exit 1

The password comes from the ADMIN_PASSWORD env var or an interactive
getpass prompt — NEVER from argv (command lines are visible via `ps`).

VM invocation (interactive TTY so getpass can prompt):
  docker compose -f docker-compose.prod.yml exec backend \\
      python -m backend.scripts.create_admin --username <name>
"""

import sys
import os

# Standalone script: extend sys.path before importing project modules.
# Per-line E402 below is unavoidable for this pattern.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import argparse  # noqa: E402
import getpass  # noqa: E402
import re  # noqa: E402
from typing import TYPE_CHECKING, Optional  # noqa: E402

from sqlalchemy import create_engine, inspect  # noqa: E402
from sqlalchemy.exc import ArgumentError, IntegrityError, NoSuchModuleError, OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

if TYPE_CHECKING:
    from sqlalchemy import Engine  # noqa: E402


class CreateAdminError(RuntimeError):
    """A guard refused the operation; the message is user-facing."""


# Username: 3-44 chars, alphanumeric start, then [A-Za-z0-9._-] — so
# USER-<upper> always fits the USER.user_id String(50) column.
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,43}$")


def ensure_migrated(engine: "Engine") -> None:
    """Refuse to touch a database Alembic hasn't built (C5: Alembic is the
    single schema mechanism — this script never creates schema)."""
    insp = inspect(engine)
    if not (insp.has_table("alembic_version") and insp.has_table("USER")):
        raise CreateAdminError(
            "database is not migrated (alembic_version/USER missing). "
            "Start the backend once (its entrypoint runs `alembic upgrade head`) "
            "or run `python -m alembic upgrade head`, then retry."
        )


def create_admin(session: Session, username: str, password: str, email: Optional[str] = None) -> str:
    """Create the first admin user; returns the new user_id.

    Raises CreateAdminError on any guard: invalid username, weak password,
    an admin already present, or a username/id collision.
    """
    from backend.auth.password import hash_password
    from backend.auth.password_policy import validate_password_strength
    from backend.orm.user import User

    if not USERNAME_RE.match(username or ""):
        raise CreateAdminError(
            f"invalid username {username!r}: 3-44 chars, alphanumeric start, " "then letters/digits/._- only."
        )

    is_valid, message = validate_password_strength(password)
    if not is_valid:
        raise CreateAdminError(f"password rejected by policy: {message}")

    existing_admin = session.query(User).filter(User.role == "admin").first()
    if existing_admin is not None:
        raise CreateAdminError(
            f"an admin already exists ({existing_admin.user_id}); "
            "create further users from the admin UI, not this script."
        )

    # id + default-email conventions intentionally mirror the demo seeder
    # (backend/scripts/init_demo_database.py) — change both together.
    user_id = f"USER-{username.upper()}"
    collision = session.get(User, user_id) or session.query(User).filter(User.username == username).first()
    if collision is not None:
        raise CreateAdminError(f"user {username!r} / id {user_id!r} already exists.")

    session.add(
        User(
            user_id=user_id,
            username=username,
            email=email or f"{username}@kpi-operations.com",
            password_hash=hash_password(password),
            full_name="System Administrator",
            role="admin",
            client_id_assigned=None,
            is_active=True,
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CreateAdminError(f"uniqueness violation (likely the email is already in use): {exc.orig}") from exc
    return user_id


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="create_admin",
        description="Create the FIRST admin user on a fresh production database.",
    )
    parser.add_argument("--username", required=True, help="admin login name")
    parser.add_argument("--email", default=None, help="defaults to <username>@kpi-operations.com")
    args = parser.parse_args(argv)

    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        if not sys.stdin.isatty():
            print(
                "ERROR: no password source. Set ADMIN_PASSWORD without argv exposure "
                "(`read -rs ADMIN_PASSWORD && export ADMIN_PASSWORD`) or run with an "
                "interactive TTY for the prompt.",
                file=sys.stderr,
            )
            return 1
        password = getpass.getpass("Admin password: ")
        if getpass.getpass("Repeat password: ") != password:
            print("ERROR: passwords do not match.", file=sys.stderr)
            return 1

    database_url = os.getenv("DATABASE_URL", "sqlite:///database/kpi_platform.db")
    try:
        engine = create_engine(database_url)
    except (ArgumentError, NoSuchModuleError):
        # Deliberately do NOT echo the exception or URL: a malformed
        # DATABASE_URL can still contain the real password.
        print(
            "ERROR: invalid DATABASE_URL (unparseable URL or unknown dialect); "
            "check the value in the environment/.env.",
            file=sys.stderr,
        )
        return 1

    try:
        ensure_migrated(engine)
        with Session(engine) as session:
            user_id = create_admin(session, args.username, password, args.email)
    except CreateAdminError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OperationalError as exc:
        print(f"ERROR: database unreachable: {exc.orig}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print(f"Created admin user: {user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
