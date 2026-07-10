# KPI-Operations — PR-4: VM Bootstrap + First Admin + Deploy Runbook — Design

**Date:** 2026-07-10
**Status:** Design approved (user, 2026-07-10) — pending implementation plan
**Parent:** `2026-06-26-kpi-operations-production-deployment-design.md` (PR-4 section). PR-1 (#128), PR-2 (#129), PR-3 (#130) are merged: the schema is MariaDB-proven and Alembic-only, and the 5-service VM compose stack is CI-proven end-to-end (`compose-stack-smoke`, both phases).
**Scope:** The last artifacts PR — `deploy/vm-bootstrap.sh`, `backend/scripts/create_admin.py`, and the VM deploy runbook — followed (post-merge, same session) by the live deployment to `192.168.2.234`.

---

## Verified VM reality (read-only probe, 2026-07-10 — supersedes the 2026-06-26 snapshot)

- Ubuntu 26.04 LTS (resolute), 8 cores / 30 GiB RAM / 57 GB free, **ext4** (preflight will pass).
- **Docker 29.1.3 + compose v2.40.3 ALREADY INSTALLED** (Ubuntu distro packages — the "install Docker CE w/ resolute fallback" concern is moot here; a guarded install branch stays in the script for future VMs).
- `manuel` is in `sudo` (password-required) but **NOT in the `docker` group** (docker.sock permission denied).
- **Co-tenants live on this box**: novalink-bridge listeners on 7070 + 5443, RDP on 3389, ollama on localhost:11434, cups local. Ports **80/443 are free** for Caddy. ufw state unknown (needs sudo — checked during deployment).

## Decisions (user-approved 2026-07-10)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Deploy shape | **Merge artifacts first, then deploy live in the same session from merged `main`.** Every sudo command is shown and confirmed before it runs. The runbook is validated by its first real execution. |
| D2 | Firewall | **ufw deny-incoming default with explicit allows: 22, 443, 80, 7070, 5443, 3389** (co-tenants preserved). The runbook inventories `ufw status` + listeners first so nothing running gets orphaned; each allow is confirmed during the deploy. The parent spec's "22+443 only" is superseded — it would cut off the bridge and RDP. |
| D3 | CA trust targets | Runbook covers **this Mac, the Luna MacBook Pro (192.168.2.244), and Windows LAN users** (macOS Keychain + Windows certmgr procedures, with root-cert fingerprint verification). |

## Components

### 1. `deploy/vm-bootstrap.sh`
Interactive, idempotent host-preparation script. **Its own discipline: every privileged command is printed and individually confirmed** (y/N) before execution — independent of the session-level confirmation practice.

Phases:
1. **Sanity (read-only):** OS/codename check, docker + compose versions, free disk ≥ 20 GB, `deploy/preflight.sh` on the target root (case-sensitivity — ext4 passes).
2. **Docker install (guarded):** no-ops when docker + compose plugin exist (this VM). Otherwise Docker CE via the official apt repo with a documented fallback if the codename channel is missing (kept for reproducibility on future hosts).
3. **Group:** `usermod -aG docker <user>` (+ note that a re-login is needed; the script detects and says so).
4. **ufw:** print current `ufw status verbose` + `ss -tlnp` listener inventory; then apply, one confirmed rule at a time: `default deny incoming`, `default allow outgoing`, `allow 22/tcp`, `allow 443/tcp`, `allow 80/tcp`, `allow 7070/tcp`, `allow 5443/tcp`, `allow 3389/tcp`; then `ufw enable` (last, after the SSH allow is verified in the rule list — anti-lockout ordering).
5. **Data root:** `deploy/preflight.sh` + `deploy/init-data-root.sh /opt/kpi-operations` (uid `--chown` deferred to the deploy phase, after the image build).
6. **App checkout + .env scaffold:** clone (or pull) the repo to the app directory; `cp .env.prod.example .env`; generate `SECRET_KEY` / `DB_PASSWORD` / `DB_ROOT_PASSWORD` with the safe alphanumeric generator and write them into `.env` (never echoed to the terminal); set `CORS_ORIGINS=https://192.168.2.234` and `TZ=America/Monterrey`.

The script takes `--root <dir>` (default `/opt/kpi-operations`) and `--app-dir <dir>` (default `/opt/kpi-operations/app`); `bash -n` clean; non-privileged logic covered by a hermetic tooling test (stubbed `sudo`/`docker`/generators).

### 2. `backend/scripts/create_admin.py`
First-admin management command, following the repo's script conventions exactly (sys.path shim; `DATABASE_URL` env with the standard fallback; direct `from backend.auth.password import hash_password`).

Contract:
- **Fail-fast guards:** refuses if the DB is unmigrated (no `alembic_version` / no USER table → actionable message), and refuses if **any `role="admin"` user already exists** (points to the admin UI for subsequent users; no `--force`).
- `--username <name>` (required; sanitized to the `USER-{USERNAME}` id convention from the seeder).
- **Password: `ADMIN_PASSWORD` env var or interactive `getpass` — never argv** (ps-visibility policy). Enforced through the full SEC-002 `validate_password_strength` (same validator as the API; `admin123` is blocklisted by construction). <!-- pragma: allowlist secret -->
- Creates: `user_id=USER-{USERNAME}`, `email=<username>@kpi-operations.com` unless `--email` given, `role="admin"`, `is_active=True`, `client_id_assigned=None`, argon2id hash.
- Prints the created user_id; exits nonzero on any guard.
- Invocation on the VM: `docker compose -f docker-compose.prod.yml exec backend python -m backend.scripts.create_admin --username <name>` (interactive TTY for getpass) — documented in the runbook.
- Unit tests (template-clone DB, exact assertions): creates the admin correctly (all fields), second run refuses (exit/exception), weak password rejected via the real policy, unmigrated-DB guard fires.

### 3. Runbook — `docs/deployment/vm-deploy-runbook.md`
Borrows the bridge checklist's two best conventions: an **Exit criterion** gating every phase, and a **Living captures** fenced block filled in during execution (bootstrap date, backend image uid, ufw rules applied, CA root fingerprint, admin username, verification results). Structure:

1. **Phase 0 — Preflight (read-only):** ssh reachability, OS/docker/compose/disk checks, listener inventory, repo clone freshness. *Exit: all checks pass.*
2. **Phase 1 — Bootstrap (sudo, confirm-per-step):** run `deploy/vm-bootstrap.sh`. *Exit: docker group active (re-login verified), ufw enabled with the 6 allows, data root exists, `.env` populated.*
3. **Phase 2 — Deploy:** `docker compose -f docker-compose.prod.yml build` → query backend uid → `sudo deploy/init-data-root.sh /opt/kpi-operations --chown <uid>` → `up -d`. *Exit: all 5 services healthy in `compose ps`.*
4. **Phase 3 — First admin:** `create_admin.py` via compose exec. *Exit: login via `https://192.168.2.234/api/auth/login` returns a token for the new admin.*
5. **Phase 4 — CA trust:** root cert location (`/opt/kpi-operations/caddy/data/caddy/pki/authorities/local/root.crt`), fingerprint capture, then per-platform: macOS Keychain import + trust (this Mac — executed live; Luna MacBook), Windows certmgr (Trusted Root store) for LAN users. Includes the bare-IP SNI check (verify the browser reaches `https://192.168.2.234` cleanly; `default_sni` in the Caddyfile is the documented knob if not). *Exit: no TLS warnings on at least one trusted client.*
6. **Phase 5 — Verification:** HTTPS health, admin login + one real write via the UI, `deploy/backup/restore-verify.sh` after a manual `--once` dump, backup sidecar loop armed, `docker compose logs` migration-ownership check. *Exit: all green; living captures complete.*
7. **Phase 6 — Operations:** failed-migration recovery (restore or drop/recreate + re-run — non-transactional DDL), **image-rebuild ⇒ re-chown reminder** (dynamic uid), VMware snapshot cadence recommendation, `FORCE_RESEED`/`DEMO_MODE` must never be set here, ufw/port change procedure, where the dumps live.

`docs/DEPLOYMENT.md` gets a short pointer to the runbook from the Docker section.

### 4. Tests/CI
- `create_admin` tests ride `backend-tests` (coverage counts).
- `tests/scripts/test_vm_bootstrap.sh`: hermetic tooling test of the script's non-privileged logic — arg parsing/defaults, confirm-gate declines skip actions, `.env` scaffolding writes all required keys with generated values (stubbed generator), idempotent re-run. Runs in `tooling-tests`.
- No new CI job; `bash -n` + actionlint-clean workflow untouched.

## Post-merge: the live deployment (same session)
Executed from merged `main`, phase-by-phase per the runbook. Read-only steps run without ceremony; **every sudo command is individually shown to and confirmed by the user** (session-level), on top of the script's own per-step confirmation. Failure at any phase stops for joint diagnosis — no improvised recovery on the production host. The deployment closes with Phase 5 verification, living captures committed back into the runbook (follow-up docs commit), and memory/ledger closure of the 4-PR program.

## Risks & mitigations
- **ufw lockout:** SSH allow applied and verified in the rules list before `ufw enable`; the script orders it that way and the runbook double-checks. VMware console access exists as the recovery path.
- **docker group re-login:** the script detects that group membership isn't active in the current session and instructs; deploy phase uses `sudo docker compose` only if the re-login hasn't happened (runbook prefers re-login).
- **Co-tenant disruption:** no bridge/RDP processes are touched; ufw allows cover their observed ports; the listener inventory is re-checked after enable.
- **Secrets:** generated on the VM, written only to `/opt/kpi-operations/app/.env` (mode 600), never echoed, never committed, never pasted into the session.
- **Bare-IP TLS:** on_demand internal CA should mint for the IP SNI; if a client balks, `default_sni 192.168.2.234` in the Caddyfile is the documented one-line fix (would be a tiny follow-up commit).

## Verification (definition of done)
- PR: all 7 CI checks green; cross-review + /code-review per gates; merge on green (user confirms).
- Deployment: runbook Phases 0–5 all exit-criteria met on 192.168.2.234; living captures recorded; Render demo unaffected (no code changes land after PR-4's merge as part of the deploy).

## Out of scope
- PR-3b follow-ups (full-suite-on-MariaDB, buildx cache, login-idiom dedup).
- Luna-agent integration (CORS origin append when that work starts).
- Any change to novalink-bridge or its ports beyond the ufw allows.
- Dockerfile uid pinning (Render-shared; revisit with PR-3b).
