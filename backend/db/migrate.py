"""Programmatic Alembic entrypoints — the ONLY way app code touches schema.

Used by the lifespan startup unit, the demo reseed path, the demo seeder's
standalone mode, and the test suite's template-DB builder.
"""

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config

_BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../backend


def alembic_config(url: Optional[str] = None) -> Config:
    """Build an Alembic Config bound to backend/alembic.ini.

    url=None lets env.py fall through to settings.DATABASE_URL; passing a URL
    overrides it (tests point this at throwaway databases).
    """
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    if url is not None:
        cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def upgrade_to_head(url: Optional[str] = None) -> None:
    """Run `alembic upgrade head` in-process."""
    command.upgrade(alembic_config(url), "head")


class SchemaRebuildError(RuntimeError):
    """A destructive schema rebuild failed partway — the DB may be schema-less."""


def rebuild_schema(url: Optional[str] = None) -> None:
    """DESTRUCTIVE: drop every table (incl. alembic_version) and rebuild to head.

    Binds an engine from ``url`` (or settings.DATABASE_URL when None), drops all
    ORM tables plus Alembic's ``alembic_version`` bookkeeping table, then upgrades
    the schema back to head. Used by the demo reseed path and the MariaDB test
    fixture.

    Raises SchemaRebuildError on any failure — callers must treat that as fatal:
    a half-rebuilt database must crash the boot, not serve 500s.
    """
    from sqlalchemy import create_engine, text

    from backend.database import Base, engine as default_engine

    try:
        target_engine = create_engine(url) if url is not None else default_engine
        try:
            Base.metadata.drop_all(bind=target_engine)
            with target_engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
                conn.commit()
        finally:
            # Only dispose engines we created here; never the app's shared engine.
            if url is not None:
                target_engine.dispose()
        upgrade_to_head(url)
    except Exception as exc:
        raise SchemaRebuildError(f"Schema rebuild failed: {exc}") from exc
