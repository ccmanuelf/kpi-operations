# KPI Deploy PR-4 — VM Bootstrap + First Admin + Deploy Runbook — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the last deployment artifacts — `deploy/vm-bootstrap.sh` (interactive host prep), `backend/scripts/create_admin.py` (first-admin command), and `docs/deployment/vm-deploy-runbook.md` — so the live VM deployment can execute post-merge from the runbook alone.

**Architecture:** Three independent deliverables on branch `deploy/pr4-vm-bootstrap`. The bootstrap script is pure bash with per-command sudo confirmation and two test seams (`--print-config`, `--scaffold-env-only`) so its non-privileged logic is hermetically testable. The admin script follows the repo's standalone-script conventions (sys.path shim, `DATABASE_URL` env) with a testable core (`create_admin(session, …)`) separated from the CLI (`main(argv)`). The runbook wraps everything into 7 phases with exit criteria and a living-captures block.

**Tech Stack:** bash (set -euo pipefail), Python 3.11 / SQLAlchemy 2 / argon2id, pytest (template-clone fixtures), existing CI jobs (`backend-tests`, `tooling-tests`).

**Spec:** `docs/superpowers/specs/2026-07-10-kpi-deploy-pr4-vm-bootstrap-design.md` (user-approved 2026-07-10).

## Global Constraints

- Branch: `deploy/pr4-vm-bootstrap` (exists; spec commits `edd6add`, `ed11fda` already on it).
- **Never modify:** `Dockerfile`, `render.yaml`, `docker-compose.yml`, `docker-compose.prod.yml`, `frontend/docker-entrypoint.sh`, anything under `backend/bootstrap/` — the Render demo and the PR-3 stack stay untouched by construction.
- **Secrets discipline:** passwords never on argv (`ADMIN_PASSWORD` env or getpass; generated `.env` values never echoed); `.env` written mode 600 under `umask 077`.
- **Permissive assertions are forbidden:** each test asserts ONE expected value/code — never `in [...]`.
- Defaults (exact values): data root `/opt/kpi-operations`, app dir `<root>/app`, host IP `192.168.2.234`, repo URL `https://github.com/ccmanuelf/kpi-operations.git`, TZ `America/Monterrey`, CORS origin `https://192.168.2.234`.
- ufw allows (exact list, D2): `22 443 80 7070 5443 3389` — all `/tcp`; `default deny incoming`, `default allow outgoing`; `ufw enable` LAST and only after the 22/tcp rule is verified staged (anti-lockout).
- User-id convention: `USER-{username.upper()}` (seeder convention, NOT the register endpoint's `USR-` prefix); role literal `"admin"` lowercase; `client_id_assigned=None`; `full_name="System Administrator"`.
- Standalone-script conventions: sys.path shim before project imports with per-line `# noqa: E402`; `DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database/kpi_platform.db")`.
- Backend tests run from `backend/`: `pytest tests/...` (coverage gate ≥ 75% via `backend/.coveragerc`). Tooling tests: `bash tests/scripts/<test>.sh` (exit 0 = pass), auto-discovered by the `tooling-tests` CI job.
- detect-secrets pre-commit hook is blocking: any example credential / password-keyword line in tests or docs needs `# pragma: allowlist secret` (or `<!-- pragma: allowlist secret -->` in markdown).
- Commit style: conventional commits (`feat:`, `test:`, `docs:`).
- Files under 500 lines.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/scripts/create_admin.py` | Create | First-admin command: guards + creation core + CLI |
| `backend/tests/test_scripts/__init__.py` | Create | Empty package marker (convention: `backend/tests/test_alembic/__init__.py`) |
| `backend/tests/test_scripts/test_create_admin.py` | Create | Unit tests (template-clone DB, exact assertions) |
| `deploy/vm-bootstrap.sh` | Create | Interactive, idempotent host preparation (6 phases) |
| `tests/scripts/test_vm_bootstrap.sh` | Create | Hermetic tooling test (stubbed sudo/python3) |
| `docs/deployment/vm-deploy-runbook.md` | Create | 7-phase deploy runbook, exit criteria + living captures |
| `docs/DEPLOYMENT.md` | Modify (insert after the `## Docker Deployment` heading, line 498) | Pointer to the runbook |

---

### Task 1: `backend/scripts/create_admin.py` + unit tests

**Files:**
- Create: `backend/scripts/create_admin.py`
- Create: `backend/tests/test_scripts/__init__.py` (empty file)
- Test: `backend/tests/test_scripts/test_create_admin.py`

**Interfaces:**
- Consumes: `backend.auth.password.hash_password(str) -> str`, `backend.auth.password.verify_password(str, str) -> bool`, `backend.auth.password_policy.validate_password_strength(str) -> tuple[bool, str]`, `backend.orm.user.User`, `backend.db.migrate.upgrade_to_head(url)`, conftest fixtures `db_session` / helper `clone_template_engine` (already exist).
- Produces: `create_admin(session, username, password, email=None) -> str` (returns user_id, raises `CreateAdminError`), `ensure_migrated(engine) -> None` (raises `CreateAdminError`), `main(argv=None) -> int` (0 success / 1 any guard). Task 3's runbook documents the `python -m backend.scripts.create_admin --username <name>` invocation — do not rename the module or flags.

- [ ] **Step 1: Create the package marker**

```bash
touch backend/tests/test_scripts/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_scripts/test_create_admin.py`:

```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_scripts/test_create_admin.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'backend.scripts.create_admin'`

- [ ] **Step 4: Write the implementation**

Create `backend/scripts/create_admin.py`:

```python
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
from typing import Optional  # noqa: E402

from sqlalchemy import create_engine, inspect  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


class CreateAdminError(RuntimeError):
    """A guard refused the operation; the message is user-facing."""


# Username: 3-44 chars, alphanumeric start, then [A-Za-z0-9._-] — so
# USER-<upper> always fits the USER.user_id String(50) column.
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,43}$")


def ensure_migrated(engine) -> None:
    """Refuse to touch a database Alembic hasn't built (C5: Alembic is the
    single schema mechanism — this script never creates schema)."""
    insp = inspect(engine)
    if not (insp.has_table("alembic_version") and insp.has_table("USER")):
        raise CreateAdminError(
            "database is not migrated (alembic_version/USER missing). "
            "Start the backend once (its entrypoint runs `alembic upgrade head`) "
            "or run `python -m alembic upgrade head`, then retry."
        )


def create_admin(
    session: Session, username: str, password: str, email: Optional[str] = None
) -> str:
    """Create the first admin user; returns the new user_id.

    Raises CreateAdminError on any guard: invalid username, weak password,
    an admin already present, or a username/id collision.
    """
    from backend.auth.password import hash_password
    from backend.auth.password_policy import validate_password_strength
    from backend.orm.user import User

    if not USERNAME_RE.match(username or ""):
        raise CreateAdminError(
            f"invalid username {username!r}: 3-44 chars, alphanumeric start, "
            "then letters/digits/._- only."
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

    user_id = f"USER-{username.upper()}"
    collision = (
        session.get(User, user_id)
        or session.query(User).filter(User.username == username).first()
    )
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
    session.commit()
    return user_id


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="create_admin",
        description="Create the FIRST admin user on a fresh production database.",
    )
    parser.add_argument("--username", required=True, help="admin login name")
    parser.add_argument(
        "--email", default=None, help="defaults to <username>@kpi-operations.com"
    )
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
    engine = create_engine(database_url)
    try:
        ensure_migrated(engine)
        with Session(engine) as session:
            user_id = create_admin(session, args.username, password, args.email)
    except CreateAdminError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print(f"Created admin user: {user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_scripts/test_create_admin.py -v`
Expected: 10 passed

- [ ] **Step 6: Run the full backend suite (coverage gate)**

Run: `cd backend && pytest tests/`
Expected: all pass, coverage ≥ 75% (was 81.88%; a fully-tested new script must not drop it below the gate)

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/create_admin.py backend/tests/test_scripts/__init__.py backend/tests/test_scripts/test_create_admin.py
git commit -m "feat(scripts): create_admin first-admin command with fail-fast guards"
```

---

### Task 2: `deploy/vm-bootstrap.sh` + hermetic tooling test

**Files:**
- Create: `deploy/vm-bootstrap.sh`
- Test: `tests/scripts/test_vm_bootstrap.sh`

**Interfaces:**
- Consumes: `deploy/preflight.sh <root>` (exit 0 = case-sensitive FS; creates+cleans probe files under `<root>/mariadb-data`), `deploy/init-data-root.sh <root> [--chown UID]`, `.env.prod.example` at repo root (keys `SECRET_KEY=`, `DB_PASSWORD=`, `DB_ROOT_PASSWORD=`, `CORS_ORIGINS=...` present as bare/valued assignments at line start).
- Produces: `deploy/vm-bootstrap.sh [--root DIR] [--app-dir DIR] [--ip ADDR]` plus test seams `--print-config` (prints `ROOT=…`, `APP_DIR=…`, `IP=…`, exits 0) and `--scaffold-env-only DIR` (writes `DIR/.env` from `DIR/.env.prod.example`, exits nonzero if the example is missing, no-ops if `.env` exists). Task 3's runbook invokes `bash deploy/vm-bootstrap.sh` with no args — keep the defaults exactly as in Global Constraints.

- [ ] **Step 1: Write the failing tooling test**

Create `tests/scripts/test_vm_bootstrap.sh`:

```bash
#!/usr/bin/env bash
# Unit tests for deploy/vm-bootstrap.sh non-privileged logic. Hermetic:
# sudo/python3 are stubbed onto PATH (sudo records argv, python3 emits a
# deterministic "secret") — no privileged action, no network, no Docker.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BOOTSTRAP="$SCRIPT_DIR/deploy/vm-bootstrap.sh"
fail=0
assert() { # assert <desc> <cond-exit>
  if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi
}

TMP="$(mktemp -d)"

# --- stub bin: sudo logs its argv; python3 emits a deterministic secret ------
STUB="$TMP/bin"; mkdir -p "$STUB"
cat > "$STUB/sudo" <<'EOF'
#!/usr/bin/env bash
echo "sudo $*" >> "${SUDO_LOG:?}"
exit 0
EOF
cat > "$STUB/python3" <<'EOF'
#!/usr/bin/env bash
echo "STUBSECRET1234567890abcdefghijkl"  # pragma: allowlist secret
EOF
chmod +x "$STUB/sudo" "$STUB/python3"
export PATH="$STUB:$PATH"
export SUDO_LOG="$TMP/sudo.log"; : > "$SUDO_LOG"

# --- bash -n: script parses ---------------------------------------------------
bash -n "$BOOTSTRAP"
assert "bash -n parses vm-bootstrap.sh" $?

# --- --print-config: defaults -------------------------------------------------
out=$(bash "$BOOTSTRAP" --print-config)
echo "$out" | grep -qx 'ROOT=/opt/kpi-operations'; assert "default ROOT" $?
echo "$out" | grep -qx 'APP_DIR=/opt/kpi-operations/app'; assert "default APP_DIR" $?
echo "$out" | grep -qx 'IP=192.168.2.234'; assert "default IP" $?

# --- --print-config: --app-dir follows --root unless given --------------------
out=$(bash "$BOOTSTRAP" --root /srv/kpi --print-config)
echo "$out" | grep -qx 'APP_DIR=/srv/kpi/app'; assert "APP_DIR follows --root" $?
out=$(bash "$BOOTSTRAP" --root /srv/kpi --app-dir /x --ip 10.0.0.5 --print-config)
echo "$out" | grep -qx 'APP_DIR=/x'; assert "explicit --app-dir wins" $?
echo "$out" | grep -qx 'IP=10.0.0.5'; assert "--ip override" $?

# --- unknown argument exits nonzero -------------------------------------------
bash "$BOOTSTRAP" --bogus >/dev/null 2>&1
[ "$?" -ne 0 ]; assert "unknown argument exits nonzero" $?

# --- scaffold-env: all keys populated, mode 600 --------------------------------
ENVDIR="$TMP/app"; mkdir -p "$ENVDIR"
cp "$SCRIPT_DIR/.env.prod.example" "$ENVDIR/"
bash "$BOOTSTRAP" --scaffold-env-only "$ENVDIR" >/dev/null
assert "scaffold-env exits 0" $?
grep -q '^SECRET_KEY=STUBSECRET' "$ENVDIR/.env"; assert "SECRET_KEY populated" $?
grep -q '^DB_PASSWORD=STUBSECRET' "$ENVDIR/.env"; assert "DB_PASSWORD populated" $?
grep -q '^DB_ROOT_PASSWORD=STUBSECRET' "$ENVDIR/.env"; assert "DB_ROOT_PASSWORD populated" $?
grep -qx 'CORS_ORIGINS=https://192.168.2.234' "$ENVDIR/.env"; assert "CORS_ORIGINS set" $?
grep -qx 'TZ=America/Monterrey' "$ENVDIR/.env"; assert "TZ set" $?
perms=$(stat -f %Lp "$ENVDIR/.env" 2>/dev/null || stat -c %a "$ENVDIR/.env")
[ "$perms" = "600" ]; assert ".env is mode 600" $?

# --- scaffold-env: secrets are never echoed to stdout/stderr -------------------
rm -f "$ENVDIR/.env"
outerr=$(bash "$BOOTSTRAP" --scaffold-env-only "$ENVDIR" 2>&1)
echo "$outerr" | grep -q 'STUBSECRET'
[ "$?" -ne 0 ]; assert "generated secrets never echoed" $?

# --- scaffold-env: idempotent re-run keeps the existing .env -------------------
echo "SENTINEL=1" >> "$ENVDIR/.env"
bash "$BOOTSTRAP" --scaffold-env-only "$ENVDIR" >/dev/null
grep -qx 'SENTINEL=1' "$ENVDIR/.env"; assert "re-run keeps existing .env" $?

# --- scaffold-env: missing example file exits nonzero --------------------------
EMPTY="$TMP/empty"; mkdir -p "$EMPTY"
bash "$BOOTSTRAP" --scaffold-env-only "$EMPTY" >/dev/null 2>&1
[ "$?" -ne 0 ]; assert "scaffold without example exits nonzero" $?

# --- confirm gate: declining every y/N prompt invokes zero sudo commands -------
# Full run with all confirms declined. On a case-insensitive dev FS the script
# exits at the phase-1 preflight (also sudo-free); on ext4 CI it walks all
# phases declining each gate. Either way the sudo stub log must stay empty.
yes n | bash "$BOOTSTRAP" --root "$TMP/root" >/dev/null 2>&1 || true
[ ! -s "$SUDO_LOG" ]; assert "declined confirms invoke no sudo" $?

rm -rf "$TMP"
exit $fail
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash tests/scripts/test_vm_bootstrap.sh`
Expected: FAIL lines (bash -n against a missing file errors; script not found), exit 1

- [ ] **Step 3: Write the bootstrap script**

Create `deploy/vm-bootstrap.sh` (chmod +x):

```bash
#!/usr/bin/env bash
# KPI Operations — VM host bootstrap (PR-4).
# Prepares a fresh Ubuntu host for the docker-compose.prod.yml stack:
#   phase 1  sanity checks (read-only; fatal on low disk / case-insensitive FS)
#   phase 2  docker install (guarded no-op when docker + compose exist)
#   phase 3  docker group membership (re-login required to take effect)
#   phase 4  ufw firewall — deny-incoming + allows 22 443 80 7070 5443 3389,
#            enable LAST and only after the 22/tcp rule is verified (anti-lockout)
#   phase 5  data root (preflight + init-data-root; --chown deferred to deploy)
#   phase 6  app checkout + .env scaffold (secrets generated, never echoed)
#
# EVERY privileged command is printed and individually confirmed (y/N);
# declining a gate SKIPS that action and continues.
#
# Usage:
#   vm-bootstrap.sh [--root DIR] [--app-dir DIR] [--ip ADDR]
#   vm-bootstrap.sh --print-config           # resolved config, no actions
#   vm-bootstrap.sh --scaffold-env-only DIR  # only write DIR/.env (test seam)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT=/opt/kpi-operations
APP_DIR=""
HOST_IP=192.168.2.234
REPO_URL=https://github.com/ccmanuelf/kpi-operations.git
PRINT_CONFIG=0
SCAFFOLD_ONLY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --app-dir) APP_DIR="$2"; shift 2 ;;
    --ip) HOST_IP="$2"; shift 2 ;;
    --print-config) PRINT_CONFIG=1; shift ;;
    --scaffold-env-only) SCAFFOLD_ONLY="$2"; shift 2 ;;
    -h|--help) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
  esac
done
[ -z "$APP_DIR" ] && APP_DIR="$ROOT/app"

if [ "$PRINT_CONFIG" -eq 1 ]; then
  echo "ROOT=$ROOT"; echo "APP_DIR=$APP_DIR"; echo "IP=$HOST_IP"
  exit 0
fi

confirm() { # confirm <description> — y/N gate; default No; decline returns 1
  printf '\n>> %s\n' "$1"
  read -r -p "   proceed? [y/N] " reply
  case "$reply" in
    y|Y|yes|YES) return 0 ;;
    *) echo "   skipped."; return 1 ;;
  esac
}

run_priv() { # print + confirm + sudo-execute; a declined gate SKIPS (returns 0)
  printf '\n>> sudo %s\n' "$*"
  read -r -p "   proceed? [y/N] " reply
  case "$reply" in
    y|Y|yes|YES) sudo "$@" ;;
    *) echo "   skipped." ;;
  esac
}

# Safe secret generators: DB passwords are URL-interpolated into DATABASE_URL
# and read by compose, so they must avoid @ : / % # ? and $ — plain
# alphanumerics only. SECRET_KEY is not URL-embedded; token_urlsafe is fine.
gen_db_secret() {
  python3 -c "import secrets,string;print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))"
}
gen_secret_key() {
  python3 -c "import secrets;print(secrets.token_urlsafe(64))"
}

scaffold_env() { # scaffold_env <dir with .env.prod.example> — writes <dir>/.env
  local dir="$1" env_file secret_key db_pw root_pw
  env_file="$dir/.env"
  if [ -f "$env_file" ]; then
    echo "   $env_file already exists — keeping it (idempotent re-run)."
    return 0
  fi
  if [ ! -f "$dir/.env.prod.example" ]; then
    echo "ERROR: $dir/.env.prod.example not found — is the app checked out?" >&2
    return 1
  fi
  secret_key="$(gen_secret_key)"
  db_pw="$(gen_db_secret)"
  root_pw="$(gen_db_secret)"
  ( umask 077
    sed -e "s|^SECRET_KEY=.*|SECRET_KEY=${secret_key}|" \
        -e "s|^DB_PASSWORD=.*|DB_PASSWORD=${db_pw}|" \
        -e "s|^DB_ROOT_PASSWORD=.*|DB_ROOT_PASSWORD=${root_pw}|" \
        -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://${HOST_IP}|" \
        "$dir/.env.prod.example" > "$env_file"
    printf 'TZ=America/Monterrey\n' >> "$env_file"
  )
  chmod 600 "$env_file"
  echo "   wrote $env_file (mode 600; secrets generated, intentionally not shown)."
}

if [ -n "$SCAFFOLD_ONLY" ]; then
  scaffold_env "$SCAFFOLD_ONLY"
  exit $?
fi

echo "== KPI VM bootstrap: ROOT=$ROOT APP_DIR=$APP_DIR IP=$HOST_IP"

# --- phase 1: sanity (read-only, no sudo) -------------------------------------
echo "-- phase 1: sanity"
. /etc/os-release 2>/dev/null || true
echo "   OS: ${PRETTY_NAME:-unknown}"
if command -v docker >/dev/null 2>&1; then
  docker --version | sed 's/^/   /'
else
  echo "   docker: MISSING (phase 2 will install)"
fi
if docker compose version >/dev/null 2>&1; then
  docker compose version | sed 's/^/   /'
else
  echo "   docker compose plugin: MISSING (phase 2 will install)"
fi
base="$(dirname "$ROOT")"; [ -d "$base" ] || base=/
free_kb=$(df -Pk "$base" | awk 'NR==2 {print $4}')
free_gb=$((free_kb / 1024 / 1024))
echo "   free disk at $base: ${free_gb}G"
if [ "$free_gb" -lt 20 ]; then
  echo "ERROR: need >= 20 GB free at $base (have ${free_gb}G)." >&2
  exit 1
fi
# Case-sensitivity probe on a throwaway dir (assumed same filesystem as ROOT;
# the real ROOT is probed again with sudo in phase 5). Fatal here by design:
# a case-insensitive datadir corrupts MariaDB (errno 1033 — PR-3 lesson).
pf_tmp="$(mktemp -d "$base/kpi-preflight.XXXXXX" 2>/dev/null || mktemp -d)"
bash "$SCRIPT_DIR/preflight.sh" "$pf_tmp"
rm -rf "$pf_tmp"
echo "   preflight (case-sensitivity): OK"

# --- phase 2: docker install (guarded) -----------------------------------------
echo "-- phase 2: docker install"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "   docker + compose already installed — skipping install."
else
  # Official Docker CE apt repo (docs.docker.com/engine/install/ubuntu). If the
  # release codename has no channel yet (brand-new Ubuntu), fall back to the
  # latest LTS channel.
  codename="${VERSION_CODENAME:-noble}"
  if ! curl -fsIo /dev/null "https://download.docker.com/linux/ubuntu/dists/${codename}/Release"; then
    echo "   NOTE: no Docker apt channel for '${codename}' — falling back to 'noble'."
    codename=noble
  fi
  run_priv install -m 0755 -d /etc/apt/keyrings
  if confirm "download Docker GPG key -> /etc/apt/keyrings/docker.asc (sudo tee)"; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
  fi
  if confirm "add Docker apt repository for '${codename}' (sudo tee sources.list.d/docker.list)"; then
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${codename} stable" \
      | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  fi
  run_priv apt-get update
  run_priv apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

# --- phase 3: docker group ------------------------------------------------------
echo "-- phase 3: docker group"
if id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
  echo "   $USER already in the docker group."
else
  run_priv usermod -aG docker "$USER"
fi
if ! groups | tr ' ' '\n' | grep -qx docker; then
  echo "   NOTE: docker group is NOT active in this session — log out and back in"
  echo "         before running 'docker compose' without sudo."
fi

# --- phase 4: ufw ----------------------------------------------------------------
echo "-- phase 4: ufw (deny incoming; allows preserve the co-tenants)"
echo "   current listeners (for the record):"
if command -v ss >/dev/null 2>&1; then ss -tlnp 2>/dev/null | sed 's/^/   /'; fi
run_priv ufw status verbose
run_priv ufw default deny incoming
run_priv ufw default allow outgoing
for port in 22 443 80 7070 5443 3389; do
  run_priv ufw allow "${port}/tcp"
done
if confirm "sudo ufw --force enable  (verifies the 22/tcp allow first — anti-lockout)"; then
  if ! sudo ufw show added | grep -q "allow 22/tcp"; then
    echo "ERROR: no 22/tcp allow rule staged — refusing to enable ufw (lockout guard)." >&2
    exit 1
  fi
  sudo ufw --force enable
  sudo ufw status verbose | sed 's/^/   /'
fi

# --- phase 5: data root -----------------------------------------------------------
echo "-- phase 5: data root"
run_priv bash "$SCRIPT_DIR/preflight.sh" "$ROOT"
run_priv bash "$SCRIPT_DIR/init-data-root.sh" "$ROOT"
echo "   NOTE: ownership (--chown) runs during deploy, after the image build"
echo "         (the backend uid is only known then)."

# --- phase 6: app checkout + .env ---------------------------------------------------
echo "-- phase 6: app checkout + .env"
if [ -d "$APP_DIR/.git" ]; then
  echo "   $APP_DIR already cloned."
  if confirm "git -C $APP_DIR pull --ff-only"; then
    git -C "$APP_DIR" pull --ff-only
  fi
else
  if confirm "sudo git clone $REPO_URL $APP_DIR, then chown to $USER"; then
    sudo git clone "$REPO_URL" "$APP_DIR"
    sudo chown -R "$USER":"$USER" "$APP_DIR"
  fi
fi
scaffold_env "$APP_DIR"

echo "== bootstrap complete. Next: runbook Phase 2 (build, chown, up -d)."
```

Then: `chmod +x deploy/vm-bootstrap.sh`

- [ ] **Step 4: Run the test to verify it passes**

Run: `bash tests/scripts/test_vm_bootstrap.sh`
Expected: all `PASS:` lines, exit 0. (On macOS the final confirm-gate run exits at the phase-1 preflight — expected; the sudo-log assertion still verifies zero privileged calls.)

- [ ] **Step 5: Run the sibling tooling tests (shared fixtures untouched)**

Run: `for t in tests/scripts/*.sh; do echo "== $t"; bash "$t" || echo "FAILED: $t"; done`
Expected: every test passes (no `FAILED:` lines)

- [ ] **Step 6: Commit**

```bash
git add deploy/vm-bootstrap.sh tests/scripts/test_vm_bootstrap.sh
git commit -m "feat(deploy): interactive VM bootstrap script with per-step sudo confirmation"
```

---

### Task 3: Runbook + DEPLOYMENT.md pointer

**Files:**
- Create: `docs/deployment/vm-deploy-runbook.md`
- Modify: `docs/DEPLOYMENT.md` (insert a blockquote directly after the `## Docker Deployment` heading — line 498 at time of writing)

**Interfaces:**
- Consumes: `deploy/vm-bootstrap.sh` (Task 2, invoked with no args), `python -m backend.scripts.create_admin --username <name>` (Task 1), merged PR-3 artifacts (`docker-compose.prod.yml` services `db`/`backend`/`frontend`/`caddy`/`backup`, `deploy/init-data-root.sh`, `deploy/backup/backup-loop.sh --once`, `deploy/backup/restore-verify.sh`).
- Produces: the operational document the live deployment executes phase-by-phase. No code contracts.

- [ ] **Step 1: Write the runbook**

Create `docs/deployment/vm-deploy-runbook.md` with exactly this content:

````markdown
# VM Production Deploy Runbook — kpi-operations on 192.168.2.234

**Scope:** first production deployment of the 5-service compose stack
(`docker-compose.prod.yml`: db, backend, frontend, caddy, backup) on the shared
Ubuntu VM at `192.168.2.234`, plus client CA trust and verification.
The Render deployment is unaffected — it remains the permanent demo.

**Ground rules (both co-admins):**
- Every `sudo` command is shown and confirmed before it runs — by
  `deploy/vm-bootstrap.sh`'s own per-step y/N gate AND by the operator.
- Secrets are generated on the VM and live only in
  `/opt/kpi-operations/app/.env` (mode 600). They are never echoed, never
  committed, never pasted into a chat session. Passwords never appear on a
  command line (`ps`-visibility).
- Failure at any phase stops the deploy for joint diagnosis — no improvised
  recovery on the production host. VMware console access is the SSH-lockout
  recovery path.

## Living captures

Fill in during execution; commit the completed block back to this file
afterwards (docs-only follow-up commit).

```text
deploy date/time         :
main commit deployed     :
backend image uid        :
ufw rules applied        :
CA root SHA-256 fp       :
admin username           :
phase 5 verification     :
notes / deviations       :
```

## Phase 0 — Preflight (read-only)

From your workstation:

```bash
ssh manuel@192.168.2.234 'head -2 /etc/os-release; docker --version; docker compose version; df -h /opt; ss -tln'
```

**Exit criterion:** Ubuntu 26.04; Docker ≥ 29 with compose ≥ 2.40; ≥ 20 GB free;
the listener inventory shows only the expected co-tenants (7070/5443 bridge,
3389 RDP, 11434 ollama local, 631 cups) and 80/443 free.

## Phase 1 — Bootstrap (sudo, confirm-per-step)

```bash
ssh manuel@192.168.2.234
git clone https://github.com/ccmanuelf/kpi-operations.git ~/kpi-operations   # initial checkout; the canonical one lands in /opt in the script's phase 6
cd ~/kpi-operations
bash deploy/vm-bootstrap.sh
```

Answer each y/N gate. Script phases: sanity → docker install (no-op on this
VM) → docker group → ufw (`deny incoming` + allows `22 443 80 7070 5443 3389`,
enable last after the 22/tcp check) → data root → app checkout + `.env`.

Then **log out and back in** so the docker group takes effect:

```bash
exit
ssh manuel@192.168.2.234
docker ps        # must work WITHOUT sudo now
```

**Exit criterion:** `docker ps` works unprivileged; `sudo ufw status verbose`
shows default deny-incoming with the six allows; `/opt/kpi-operations/`
contains the data-root manifest (mariadb-data, backups, uploads, reports,
logs, caddy/data, caddy/config) and `app/` checkout; `app/.env` exists,
mode `600`.

## Phase 2 — Deploy

```bash
cd /opt/kpi-operations/app
docker compose -f docker-compose.prod.yml build
uid=$(docker compose -f docker-compose.prod.yml run --rm --no-deps --entrypoint id backend -u)
echo "backend uid: $uid"                       # capture in Living captures
sudo bash deploy/init-data-root.sh /opt/kpi-operations --chown "$uid"
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps   # repeat until all healthy
```

First boot takes a few minutes: MariaDB initializes its datadir, then the
backend entrypoint waits for the DB and runs `alembic upgrade head` once
before the 4 gunicorn workers start.

**Exit criterion:** all 5 services `healthy` in `compose ps`;
`docker compose -f docker-compose.prod.yml logs backend | grep -i alembic`
shows the migration ran exactly once (entrypoint-owned).

## Phase 3 — First admin

Interactive (getpass prompts; password never on argv):

```bash
docker compose -f docker-compose.prod.yml exec backend \
    python -m backend.scripts.create_admin --username <name>
```

Non-TTY alternative (still never on argv, never in shell history):

```bash
read -rs ADMIN_PASSWORD && export ADMIN_PASSWORD
docker compose -f docker-compose.prod.yml exec -e ADMIN_PASSWORD backend \
    python -m backend.scripts.create_admin --username <name>
unset ADMIN_PASSWORD
```

The script refuses on an unmigrated DB, a weak password (SEC-002 policy), or
if any admin already exists — subsequent users come from the admin UI.

**Exit criterion:** script prints `Created admin user: USER-<NAME>`; a browser
login at `https://192.168.2.234` succeeds and lands on the dashboard
(certificate warning is expected until Phase 4).

## Phase 4 — CA trust (clients)

Caddy's internal CA signs the TLS cert. Export its root and trust it on each
client. On the VM:

```bash
sudo cp /opt/kpi-operations/caddy/data/caddy/pki/authorities/local/root.crt /tmp/kpi-root.crt
sudo chmod 644 /tmp/kpi-root.crt
openssl x509 -in /tmp/kpi-root.crt -noout -fingerprint -sha256
openssl x509 -in /tmp/kpi-root.crt -noout -fingerprint -sha1    # for Windows comparison
```

Record the SHA-256 fingerprint in Living captures.

**macOS (this Mac, and the Luna MacBook Pro `192.168.2.244`):**

```bash
scp manuel@192.168.2.234:/tmp/kpi-root.crt ~/Downloads/
openssl x509 -in ~/Downloads/kpi-root.crt -noout -fingerprint -sha256   # MUST match the VM's output
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/Downloads/kpi-root.crt
```

**Windows LAN users (admin Command Prompt):** copy `kpi-root.crt` to the
machine, compare the certificate thumbprint against the VM's SHA-1
fingerprint, then install to the Trusted Root store:

```bat
certutil -dump kpi-root.crt          &REM "Cert Hash(sha1)" must match the VM's sha1 fingerprint
certutil -addstore -f Root kpi-root.crt
```

(GUI alternative: double-click the .crt → Install Certificate → Local
Machine → "Trusted Root Certification Authorities".)

Bare-IP note: Caddy's `on_demand` internal CA mints a certificate for the IP
SNI. If a browser still warns after trusting the root, the documented
one-line fix is `default_sni 192.168.2.234` in `deploy/caddy/Caddyfile`
(tiny follow-up commit) — do not improvise other TLS changes.

**Exit criterion:** at least one trusted client loads
`https://192.168.2.234` with no TLS warning; fingerprint recorded.

## Phase 5 — Verification

From a trusted client (note: NO `-k` — trust must be real):

```bash
curl https://192.168.2.234/health/live
```

In the UI: log in as the new admin and perform one real write (e.g. create a
production entry), confirm it appears in the grid after a reload.

On the VM — backup + scratch restore:

```bash
cd /opt/kpi-operations/app
docker compose -f docker-compose.prod.yml exec backup bash /backup-loop.sh --once
ls -lh /opt/kpi-operations/backups/          # a fresh kpi_platform-*.sql.gz
bash deploy/backup/restore-verify.sh         # restores the latest dump into a scratch DB
docker compose -f docker-compose.prod.yml logs backup | tail -5   # nightly loop armed
```

**Exit criterion:** health 200 over trusted TLS; admin write persisted;
`restore-verify.sh` reports the scratch restore produced tables; backup loop
armed. Living captures complete.

## Phase 6 — Operations

- **Failed migration recovery:** MariaDB DDL is non-transactional — a failed
  `alembic upgrade head` can leave a half-applied revision. Recovery: restore
  the latest dump (verify with `restore-verify.sh` first), or for a fresh
  install drop and recreate the database and let the entrypoint re-migrate on
  `up -d`. Never hand-edit `alembic_version`.
- **Image rebuild ⇒ re-chown:** the backend uid is dynamic. After every
  `docker compose -f docker-compose.prod.yml build`, re-query the uid (Phase 2
  command) and re-run `sudo bash deploy/init-data-root.sh /opt/kpi-operations
  --chown <uid>` before `up -d`.
- **Upgrades:** `git -C /opt/kpi-operations/app pull --ff-only` → build →
  re-chown check → `up -d`. The entrypoint migrates once per boot.
- **Snapshots:** take a VMware snapshot before any upgrade or schema change;
  weekly cadence recommended. Snapshots complement — never replace — the
  nightly dumps in `/opt/kpi-operations/backups/` (14-day retention, 02:00
  America/Monterrey).
- **Never set `DEMO_MODE=true` or `FORCE_RESEED` on this host** — those are
  demo/CI paths that seed or reset data.
- **Firewall changes:** `sudo ufw allow <port>/tcp` (confirmed, recorded in
  Living captures). Current allows: 22, 443, 80, 7070 (bridge), 5443 (bridge),
  3389 (RDP).
- **Single-tenancy policy (decided 2026-07-10):** the kpi-ops MariaDB
  container serves `kpi_platform` only — other projects on this VM
  (novalink-bridge, Claude Cowork / Luna data stores) run their own database
  containers with their own credentials, storage, and backups. No foreign
  schemas in this instance; its root credentials never leave the kpi-ops
  stack.
````

- [ ] **Step 2: Add the DEPLOYMENT.md pointer**

In `docs/DEPLOYMENT.md`, insert directly after the `## Docker Deployment` heading line (line 498 at time of writing), separated by blank lines:

```markdown
> **Deploying to the production VM (LAN, MariaDB + Caddy)?** Follow the
> step-by-step runbook: [deployment/vm-deploy-runbook.md](deployment/vm-deploy-runbook.md).
> It wraps this section with host bootstrap (`deploy/vm-bootstrap.sh`),
> first-admin creation (`backend/scripts/create_admin.py`), client CA trust,
> and verification with exit criteria per phase.
```

- [ ] **Step 3: Verify document integrity**

Run: `grep -c "Exit criterion" docs/deployment/vm-deploy-runbook.md`
Expected: `6` (Phases 0–5; Phase 6 is reference material, no gate)

Run: `grep -n "vm-deploy-runbook" docs/DEPLOYMENT.md`
Expected: one match inside the Docker Deployment section

- [ ] **Step 4: Commit (pre-commit hooks must pass — detect-secrets scans the new doc)**

```bash
git add docs/deployment/vm-deploy-runbook.md docs/DEPLOYMENT.md
git commit -m "docs(deploy): VM deploy runbook with exit criteria + living captures"
```

If detect-secrets flags a line (e.g. the `ADMIN_PASSWORD` keyword in prose), append `<!-- pragma: allowlist secret -->` to that exact line and re-commit — never add real-looking secret values to the baseline.

---

## Verification (whole-PR definition of done)

1. `cd backend && pytest tests/` — all pass, coverage ≥ 75%.
2. `for t in tests/scripts/*.sh; do bash "$t" || echo FAILED; done` — no failures.
3. `bash -n deploy/vm-bootstrap.sh` — clean.
4. No diffs to `Dockerfile`, `render.yaml`, `docker-compose*.yml`, `frontend/docker-entrypoint.sh`, `backend/bootstrap/` (verify with `git diff main...HEAD --stat`).
5. Final whole-branch review + `/code-review` + `/cross-review`, then PR; all 7 CI checks green; merge on user confirmation.
6. Post-merge: live deployment per the runbook (separate execution, not part of this plan's tasks).
