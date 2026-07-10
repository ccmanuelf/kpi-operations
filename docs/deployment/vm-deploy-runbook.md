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
read -rs ADMIN_PASSWORD && export ADMIN_PASSWORD <!-- pragma: allowlist secret -->
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
