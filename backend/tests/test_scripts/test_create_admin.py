"""Unit tests for backend/scripts/create_admin.py (first-admin command, PR-4).

Core tests use the conftest `db_session` fixture (in-memory clone of the
Alembic-built template — full real schema, zero users). CLI tests build a
file-based migrated DB via upgrade_to_head and drive `main()` through the
DATABASE_URL / ADMIN_PASSWORD environment, exactly like the VM invocation.
"""

import io

import pytest
from sqlalchemy import create_engine

from backend.auth.password import verify_password
from backend.db.migrate import upgrade_to_head
from backend.orm.user import User
from backend.scripts.create_admin import (
    CreateAdminError,
    create_admin,
    ensure_migrated,
    main,
)

STRONG_PW = "Corr3ct-Horse-Battery!"  # pragma: allowlist secret


class TestCreateAdminCore:
    def test_creates_admin_with_all_fields(self, db_session):
        user_id = create_admin(db_session, "ops1", STRONG_PW)
        assert user_id == "USER-OPS1"
        user = db_session.get(User, "USER-OPS1")
        assert user.username == "ops1"
        assert user.email == "ops1@kpi-operations.com"
        assert user.role == "admin"
        assert user.is_active is True
        assert user.client_id_assigned is None
        assert user.full_name == "System Administrator"
        assert user.password_hash.startswith("$argon2")
        assert verify_password(STRONG_PW, user.password_hash) is True

    def test_custom_email(self, db_session):
        create_admin(db_session, "ops1", STRONG_PW, email="boss@example.com")
        assert db_session.get(User, "USER-OPS1").email == "boss@example.com"

    def test_refuses_second_admin(self, db_session):
        create_admin(db_session, "ops1", STRONG_PW)
        with pytest.raises(CreateAdminError, match="already exists"):
            create_admin(db_session, "other", STRONG_PW)

    def test_weak_password_rejected_and_nothing_persisted(self, db_session):
        with pytest.raises(CreateAdminError, match="policy"):
            create_admin(db_session, "ops1", "admin123")  # pragma: allowlist secret
        assert db_session.query(User).count() == 0

    def test_invalid_username_rejected(self, db_session):
        with pytest.raises(CreateAdminError, match="invalid username"):
            create_admin(db_session, "bad user!", STRONG_PW)

    def test_username_collision_with_non_admin_rejected(self, db_session):
        db_session.add(
            User(
                user_id="USER-OPS1",
                username="ops1",
                email="ops1@kpi-operations.com",
                password_hash=None,
                role="operator",
                is_active=True,
            )
        )
        db_session.commit()
        with pytest.raises(CreateAdminError, match="already exists"):
            create_admin(db_session, "ops1", STRONG_PW)


class TestGuardsAndCli:
    def test_unmigrated_db_guard(self):
        engine = create_engine("sqlite://")
        with pytest.raises(CreateAdminError, match="not migrated"):
            ensure_migrated(engine)
        engine.dispose()

    def test_main_env_password_creates_then_second_run_refuses(self, tmp_path, monkeypatch):
        url = f"sqlite:///{tmp_path / 'prod.db'}"
        upgrade_to_head(url)
        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.setenv("ADMIN_PASSWORD", STRONG_PW)
        assert main(["--username", "opsadmin"]) == 0
        assert main(["--username", "second"]) == 1

    def test_main_unmigrated_db_fails(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'empty.db'}")
        monkeypatch.setenv("ADMIN_PASSWORD", STRONG_PW)
        assert main(["--username", "opsadmin"]) == 1

    def test_main_without_password_and_no_tty_fails(self, tmp_path, monkeypatch):
        url = f"sqlite:///{tmp_path / 'prod.db'}"
        upgrade_to_head(url)
        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        monkeypatch.setattr("sys.stdin", io.StringIO(""))  # isatty() -> False
        assert main(["--username", "opsadmin"]) == 1
