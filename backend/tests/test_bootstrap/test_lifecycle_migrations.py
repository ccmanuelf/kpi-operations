"""Startup-migration unit: gating + fatality (C5 collapse)."""

from unittest.mock import patch

import pytest

from backend.bootstrap import lifecycle
from backend.config import settings


def test_run_startup_migrations_invokes_alembic_when_enabled():
    with patch("backend.db.migrate.upgrade_to_head") as up:
        original = settings.RUN_MIGRATIONS_ON_STARTUP
        settings.RUN_MIGRATIONS_ON_STARTUP = True
        try:
            lifecycle.run_startup_migrations()
        finally:
            settings.RUN_MIGRATIONS_ON_STARTUP = original
    up.assert_called_once_with()


def test_run_startup_migrations_skips_when_disabled():
    with patch("backend.db.migrate.upgrade_to_head") as up:
        original = settings.RUN_MIGRATIONS_ON_STARTUP
        settings.RUN_MIGRATIONS_ON_STARTUP = False
        try:
            lifecycle.run_startup_migrations()
        finally:
            settings.RUN_MIGRATIONS_ON_STARTUP = original
    up.assert_not_called()


def test_run_startup_migrations_is_fatal_on_failure():
    with patch("backend.db.migrate.upgrade_to_head", side_effect=RuntimeError("boom")):
        original = settings.RUN_MIGRATIONS_ON_STARTUP
        settings.RUN_MIGRATIONS_ON_STARTUP = True
        try:
            with pytest.raises(RuntimeError):
                lifecycle.run_startup_migrations()
        finally:
            settings.RUN_MIGRATIONS_ON_STARTUP = original
