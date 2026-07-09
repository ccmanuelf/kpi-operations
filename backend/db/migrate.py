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
