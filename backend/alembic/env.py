"""
Alembic environment configuration for KPI Operations Platform.

Imports all ORM models so that Base.metadata contains every table,
then configures online/offline migration execution.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# 1. Import Base and settings
# ---------------------------------------------------------------------------
from backend.database import Base
from backend.config import settings

# ---------------------------------------------------------------------------
# 2. Import ALL ORM models so they register with Base.metadata
#    backend.orm.__init__ re-exports every core model.
#    backend.orm.capacity.__init__ re-exports every capacity model.
# ---------------------------------------------------------------------------
import backend.orm  # noqa: F401 — registers core ORM models
import backend.orm.capacity  # noqa: F401 — registers capacity planning models

# ---------------------------------------------------------------------------
# 3. Alembic Config object (provides access to alembic.ini values)
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging (unless we are in a test
# harness that has already configured logging).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# 4. Metadata target — this is what autogenerate diffs against
# ---------------------------------------------------------------------------
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# 5. Override sqlalchemy.url from application settings
# ---------------------------------------------------------------------------
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL to stdout.

    Calls to context.execute() emit the given string to the script output.
    No Engine is required; only the database URL is needed.
    """
    url = config.get_main_option("sqlalchemy.url")
    is_sqlite = bool(url and "sqlite" in url)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connect to the database.

    Creates an Engine and associates a connection with the context.
    For SQLite databases, ``render_as_batch=True`` is enabled because
    SQLite does not support ALTER TABLE operations natively.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    url = config.get_main_option("sqlalchemy.url")
    is_sqlite = bool(url and "sqlite" in url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
