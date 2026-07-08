"""MariaDB portability guards.

The dialect-agnostic schema test runs in the default (SQLite) suite. The
integration tests skip unless the app engine is MariaDB (DATABASE_URL points
at MariaDB), which is the case only in the dedicated CI job — see
.github/workflows/ci.yml::mariadb-portability.
"""

from sqlalchemy import String
from unittest.mock import patch

from backend.orm.user import User
from backend.db.providers.mariadb import MariaDBProvider


def test_client_id_assigned_is_bounded_string_not_text():
    """MariaDB cannot index TEXT; the column must be a bounded String."""
    col = User.__table__.c.client_id_assigned
    assert isinstance(col.type, String)
    assert col.type.length == 500
    assert col.index is True


def test_mariadb_provider_enforces_utf8mb4():
    """The MariaDB provider must pass charset=utf8mb4 in connect_args."""
    provider = MariaDBProvider()
    with patch("backend.db.providers.mariadb.create_engine") as mock_create_engine:
        provider.create_engine("mysql+pymysql://u:p@localhost:3306/db")
    _, kwargs = mock_create_engine.call_args
    assert kwargs["connect_args"]["charset"] == "utf8mb4"


# ---------------------------------------------------------------------------
# FK type-consistency guard (always-on, dialect-agnostic). InnoDB (MariaDB)
# refuses to create a table whose FK column type differs from the referenced
# column (errno 150 "Foreign key constraint is incorrectly formed"); SQLite
# silently accepts the mismatch, so it must be caught statically here.
# ---------------------------------------------------------------------------

from backend.database import Base  # noqa: E402

# Populate Base.metadata with EVERY table. Model-import block copied VERBATIM
# from backend/alembic/env.py (the canonical list that registers all core +
# capacity models).
import backend.orm  # noqa: E402,F401 — registers core ORM models
import backend.orm.capacity  # noqa: E402,F401 — registers capacity planning models


def test_foreign_key_column_types_match_referenced_columns():
    """Every FK column's type must exactly match its referenced column's type."""
    mismatches = []
    for table in Base.metadata.sorted_tables:
        for constraint in table.foreign_key_constraints:
            for fk in constraint.elements:
                local, remote = fk.parent, fk.column
                same_class = type(local.type) is type(remote.type)
                same_length = getattr(local.type, "length", None) == getattr(remote.type, "length", None)
                if not (same_class and same_length):
                    mismatches.append(
                        f"{table.name}.{local.name} ({local.type!r}) -> "
                        f"{remote.table.name}.{remote.name} ({remote.type!r})"
                    )
    assert mismatches == []
