# Deployment Guide - KPI Operations Platform

This guide covers deploying the KPI Operations Platform to a self-hosted MariaDB
production environment. **The go-live target is the Docker Compose stack**
(`docker-compose.prod.yml` — see the [Docker Deployment](#docker-deployment)
section). The systemd + MariaDB + nginx/TLS path documented below remains a
supported alternative for hosts without Docker.

> **Note:** `docker-compose.prod.yml` IS the production VM stack (MariaDB 11.4 +
> Caddy internal-CA TLS + gunicorn backend + static frontend + nightly-backup
> sidecar), proven by the `compose-stack-smoke` CI job on every PR.
> `docker-compose.yml` remains the SQLite development stack. Render deploys the
> Dockerfiles natively (`render.yaml`) and is unaffected by the prod stack.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Variables](#environment-variables)
3. [Database Setup](#database-setup)
4. [Backend Deployment](#backend-deployment)
5. [Frontend Deployment](#frontend-deployment)
6. [Reverse Proxy Configuration](#reverse-proxy-configuration)
7. [Docker Deployment](#docker-deployment)
8. [Render.com Deployment](#rendercom-deployment)
9. [Health Check Endpoints](#health-check-endpoints)
10. [Security Checklist](#security-checklist)
11. [Monitoring & Logging](#monitoring--logging)
12. [Backup Strategy](#backup-strategy)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

| Component | Minimum (bare-metal) | Minimum (Docker stack) | Recommended |
|-----------|----------------------|------------------------|-------------|
| **CPU** | 2 cores | 4 cores | 4+ cores |
| **RAM** | 4 GB | 8 GB | 8+ GB |
| **Storage** | 20 GB | 20 GB | 50+ GB SSD |
| **OS** | Ubuntu 20.04+ / RHEL 8+ | Ubuntu 22.04 LTS (ext4) | Ubuntu 22.04 LTS |

> The **Docker stack** (`docker-compose.prod.yml`) minimum is higher because the
> compose CPU/memory limits alone reserve **2.5 CPU / 2.25 GB** (backend 2.0 CPU /
> 2 GB + frontend 0.5 CPU / 256 MB) *before* MariaDB's own buffers, Caddy, the
> backup sidecar, and the OS. The datadir bind mount also requires a
> case-sensitive filesystem (see the Docker Deployment section).

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| **Python** | 3.11+ | Backend runtime |
| **Node.js** | 22+ LTS | Frontend build |
| **MariaDB** | 10.11+ | Production database |
| **Nginx** | 1.18+ | Reverse proxy |
| **Git** | 2.30+ | Source control |

### Optional Software

| Software | Version | Purpose |
|----------|---------|---------|
| **Docker** | 24+ | Container deployment |
| **Docker Compose** | 2.20+ | Multi-container orchestration |
| **Redis** | 7+ | Session caching (future) |
| **Certbot** | Latest | SSL certificate management |

---

## Environment Variables

### Backend `.env` Configuration

Create `/var/www/kpi-platform/backend/.env`:

```env
# ============================================
# ENVIRONMENT
# ============================================
ENVIRONMENT=production

# ============================================
# DATABASE (MariaDB Production)
# ============================================
DATABASE_URL=mysql+pymysql://kpi_user:SECURE_PASSWORD@localhost:3306/kpi_platform
# DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD are NOT app settings — the
# backend only reads DATABASE_URL above. DB_PASSWORD/DB_ROOT_PASSWORD exist
# only as compose-level (.env) values for docker-compose.prod.yml, which
# builds the MariaDB container and the backend's DATABASE_URL from them; see
# the Docker Deployment section.

# Connection Pool Settings
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600

# ============================================
# JWT AUTHENTICATION
# ============================================
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=YOUR_64_CHARACTER_MINIMUM_SECRET_KEY_CHANGE_THIS
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# ============================================
# CORS CONFIGURATION
# ============================================
CORS_ORIGINS=https://kpi.yourdomain.com,https://www.kpi.yourdomain.com

# ============================================
# APPLICATION SETTINGS
# ============================================
DEBUG=False
LOG_LEVEL=INFO

# Schema migrations run in-process at startup on this systemd/gunicorn deploy
# (there is no container entrypoint to own them), so keep the default true:
RUN_MIGRATIONS_ON_STARTUP=true
# NOTE: container deploys (Render, docker-compose*.yml) set this to false —
# their entrypoint runs `alembic upgrade head` exactly once before workers start.

# ============================================
# FILE UPLOAD
# ============================================
MAX_UPLOAD_SIZE=10485760
UPLOAD_DIR=/var/www/kpi-platform/uploads

# ============================================
# REPORTS
# ============================================
REPORT_OUTPUT_DIR=/var/www/kpi-platform/reports

# ============================================
# EMAIL CONFIGURATION (Choose one)
# ============================================
# Option 1: SendGrid
SENDGRID_API_KEY=SG.your_sendgrid_api_key

# Option 2: SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=reports@yourdomain.com
SMTP_PASSWORD=app_password_here

# Email Settings
REPORT_FROM_EMAIL=reports@yourdomain.com
REPORT_EMAIL_ENABLED=True
REPORT_EMAIL_TIME=06:00
```

### Frontend Environment

Create `/var/www/kpi-platform/frontend/.env.production`:

```env
VITE_API_BASE_URL=https://api.kpi.yourdomain.com
VITE_APP_TITLE=KPI Operations Platform
```

### Content Security Policy (CSP)

The frontend Docker image uses nginx with a strict Content-Security-Policy header. The `connect-src` directive defaults to `'self'` plus the Docker-internal backend hostname. For production deployments where the API is on a different domain, set the `CSP_CONNECT_EXTRA` environment variable:

```env
# In the frontend container or Dockerfile override
CSP_CONNECT_EXTRA=https://api.kpi.yourdomain.com wss://api.kpi.yourdomain.com
```

The `frontend/Dockerfile` declares `ENV CSP_CONNECT_EXTRA=""` and uses `envsubst` at container startup to inject the value into the nginx configuration. Without this variable set, API calls to external domains will be blocked by CSP.

---

## Database Setup

### 1. Install MariaDB

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install mariadb-server mariadb-client

# Start and enable service
sudo systemctl start mariadb
sudo systemctl enable mariadb

# Secure installation
sudo mysql_secure_installation
```

### 2. Create Database and User

```sql
-- Connect as root
sudo mysql -u root -p

-- Create database
CREATE DATABASE kpi_platform
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Create user with secure password
CREATE USER 'kpi_user'@'localhost'
  IDENTIFIED BY 'YOUR_SECURE_PASSWORD';

-- Grant privileges
GRANT ALL PRIVILEGES ON kpi_platform.*
  TO 'kpi_user'@'localhost';

FLUSH PRIVILEGES;
EXIT;
```

### 3. Initialize Schema and Data

No manual SQL import is required. Alembic is the single schema mechanism (`backend/alembic/versions/`): startup applies migrations automatically (`RUN_MIGRATIONS_ON_STARTUP=true` by default, or the entrypoint's `RUN_MIGRATIONS` in Docker — see [Environment Variables](#environment-variables)), and `DEMO_MODE=true` seeds comprehensive demo data on first startup when it detects an empty database.

Simply ensure the database exists and the connection is configured (see [Environment Variables](#environment-variables)), then start the backend. The schema and demo data will be created automatically.

The auto-seed creates 5 demo clients (ACME-MFG, TEXTILE-PRO, FASHION-WORKS, QUALITY-STITCH, GLOBAL-APPAREL) with employees, work orders, production entries, quality data, capacity planning records, hold catalogs, break times, production lines, equipment, and assignments.

> **Note:** The old `CAPACITY_PLANNING_ENABLED` flag has been removed — capacity tables are always part of the Alembic schema and the flag had no effect since the Alembic collapse.

**Demo credentials**: admin/admin123, all other users use password123.

**Upgrading a pre-Alembic database:** if your database was created before this change (schema present, no `alembic_version` table), stamp it once: `cd backend && python -m alembic stamp head`. For demo databases, it's simpler to just delete the DB file and let startup rebuild and reseed it.

---

## Backend Deployment

### 1. Clone Repository

```bash
sudo mkdir -p /var/www/kpi-platform
sudo chown $USER:$USER /var/www/kpi-platform
cd /var/www/kpi-platform
git clone <repository-url> .
```

### 2. Setup Python Environment

```bash
cd /var/www/kpi-platform/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install Gunicorn for production
pip install gunicorn
```

### 3. Configure Environment

```bash
# Copy and edit environment file
cp .env.example .env
nano .env  # Edit with production values
```

### 4. Create Required Directories

```bash
sudo mkdir -p /var/www/kpi-platform/uploads
sudo mkdir -p /var/www/kpi-platform/reports
sudo chown -R www-data:www-data /var/www/kpi-platform/uploads
sudo chown -R www-data:www-data /var/www/kpi-platform/reports
```

### 5. Create Systemd Service

Create `/etc/systemd/system/kpi-backend.service`:

```ini
[Unit]
Description=KPI Platform Backend API
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/kpi-platform/backend
Environment="PATH=/var/www/kpi-platform/backend/venv/bin"
EnvironmentFile=/var/www/kpi-platform/backend/.env

ExecStart=/var/www/kpi-platform/backend/venv/bin/gunicorn \
    backend.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/kpi-platform/access.log \
    --error-logfile /var/log/kpi-platform/error.log \
    --capture-output

Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/www/kpi-platform/uploads /var/www/kpi-platform/reports /var/log/kpi-platform

[Install]
WantedBy=multi-user.target
```

### 6. Start Backend Service

```bash
# Create log directory
sudo mkdir -p /var/log/kpi-platform
sudo chown www-data:www-data /var/log/kpi-platform

# Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable kpi-backend
sudo systemctl start kpi-backend

# Check status
sudo systemctl status kpi-backend
```

---

## Frontend Deployment

### 1. Build Frontend

```bash
cd /var/www/kpi-platform/frontend

# Install dependencies
npm ci --production=false

# Build for production
npm run build

# Output will be in /dist directory
```

### 2. Configure Nginx for Frontend

See [Reverse Proxy Configuration](#reverse-proxy-configuration) below.

---

## Reverse Proxy Configuration

### Nginx Configuration

Create `/etc/nginx/sites-available/kpi-platform`:

```nginx
# Rate limiting zone
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;

# Backend upstream
upstream kpi_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name kpi.yourdomain.com api.kpi.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name kpi.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/kpi.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kpi.yourdomain.com/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security Headers
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' https://api.kpi.yourdomain.com;" always;

    # Frontend static files
    root /var/www/kpi-platform/frontend/dist;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml;

    # Static assets caching
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Vue Router (history mode)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://kpi_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Auth endpoints with stricter rate limiting
    location /api/auth {
        limit_req zone=auth_limit burst=5 nodelay;

        proxy_pass http://kpi_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # File upload size limit
    client_max_body_size 10M;

    # Error pages
    error_page 502 503 504 /50x.html;
    location = /50x.html {
        root /usr/share/nginx/html;
    }
}
```

### Enable Site and Restart

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/kpi-platform /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### SSL Certificate Setup (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d kpi.yourdomain.com -d api.kpi.yourdomain.com

# Auto-renewal is configured automatically
```

---

## Docker Deployment

This is the real, checked-in production stack for the VM: `docker-compose.prod.yml`
(MariaDB 11.4 + gunicorn backend + static frontend + Caddy internal-CA TLS +
nightly-backup sidecar). It is proven end-to-end by `deploy/smoke/compose-smoke.sh`
(readiness + 6 proofs + an uploads-writability proof) via the
`compose-stack-smoke` CI job on every PR, and the same script verifies it locally.

### Prerequisites

- Docker Engine + Compose v2 on the VM.
- Persistent state directories under `${KPI_DATA_ROOT:-/opt/kpi-operations}`
  (`mariadb-data`, `backups`, `uploads`, `reports`, `logs`, `caddy/data`,
  `caddy/config`) — created by `deploy/init-data-root.sh` (the single-source
  manifest), after `deploy/preflight.sh` verifies the path is case-sensitive.
  See the Run section for the exact commands.
- **Bind-mount ownership for the backend's dynamic UID — required after EVERY
  image (re)build.** The backend image runs as a non-root user (`kpiuser`) whose
  UID is assigned dynamically **at image-build time**, so it is not stable: a
  rebuild can change it, and it will not match the host directory owner.
  After each build, discover the UID and chown the three host-writable mounts
  (the shared script does exactly this):

  ```bash
  uid=$(docker compose -f docker-compose.prod.yml run --rm --no-deps --entrypoint "id -u" backend)
  sudo bash deploy/init-data-root.sh "${KPI_DATA_ROOT:-/opt/kpi-operations}" --chown "$uid"
  ```

  Without this, CSV uploads and report generation fail with permission errors
  (the container can't write to the mounts) while everything else — login,
  reads, the database, backups — works, so the failure is easy to misdiagnose.
  The smoke script's writability proof (`touch /app/uploads/.smoke-write`)
  catches a missing/incorrect chown in the running topology. **This is a PR-4
  runbook preflight item.**

> **Hard requirement — Linux case-sensitive filesystem only.** The MariaDB
> datadir bind mount (`${KPI_DATA_ROOT}/mariadb-data`) requires a
> case-sensitive filesystem (ext4 and similar). macOS/Docker Desktop shared
> mounts (virtiofs) are case-insensitive and **corrupt the datadir** (MariaDB
> errno 1033, crash-loop on restart). The Ubuntu/ext4 VM is the supported
> target; local macOS verification of this stack substitutes a named Docker
> volume for the `db` service's bind mount instead.

### Setup

```bash
cp .env.prod.example .env
# Edit .env: SECRET_KEY, DB_PASSWORD, DB_ROOT_PASSWORD, CORS_ORIGINS are
# required — compose fails fast (":?" defaults) if any is unset. KPI_DATA_ROOT,
# DEMO_MODE, BACKUP_RETENTION_DAYS, BACKUP_HOUR are optional overrides;
# see the comments in .env.prod.example.
```

> **Password charset.** `DB_PASSWORD`/`DB_ROOT_PASSWORD` must avoid URL-reserved
> characters (`@ : / % # ?`) and `$`: `DB_PASSWORD` is interpolated into
> `DATABASE_URL` (a URL) and `$` triggers compose variable interpolation.
> Generate a safe 32-char alphanumeric secret:
>
> ```bash
> python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))"
> ```

### Run

```bash
# 1. Verify the datadir path is case-sensitive, then create the data-root layout.
bash deploy/preflight.sh "${KPI_DATA_ROOT:-/opt/kpi-operations}"
bash deploy/init-data-root.sh "${KPI_DATA_ROOT:-/opt/kpi-operations}"

# 2. Build, then chown the writable mounts to the backend image's dynamic uid
#    (see Prerequisites), then start.
docker compose -f docker-compose.prod.yml build
uid=$(docker compose -f docker-compose.prod.yml run --rm --no-deps --entrypoint "id -u" backend)
sudo bash deploy/init-data-root.sh "${KPI_DATA_ROOT:-/opt/kpi-operations}" --chown "$uid"
docker compose -f docker-compose.prod.yml up -d

# 3. Prove the topology end-to-end.
bash deploy/smoke/compose-smoke.sh
```

The smoke script proves: (0) stack readiness through Caddy — it owns the
boot/seed wait, (1) health through Caddy TLS, (1w) the uploads mount is writable
by the backend uid, (2) login, (3) write + JSON readback, (4) data survives a
backend restart, (5) backup + restore into a scratch database (via
`deploy/backup/restore-verify.sh`), (6) single migration owner (entrypoint, not
the app lifespan). With `DEMO_MODE=false` (the production default), proofs 2–3
need an admin user to already exist — PR-4's `create_admin.py` provisions the
first admin on a fresh VM; run it before the login/write proofs will pass. CI
runs the identical script with `DEMO_MODE=true`, so all proofs pass unattended
on every PR — that CI run (plus a separate `DEMO_MODE=false` boot-only phase
asserting an empty prod DB serves health and returns 401 on login) is the
release evidence for this stack.

> **The smoke has side effects.** It writes `SMOKE-####` hold-status rows to the
> `ACME-MFG` client and leaves a `smoke_restore` scratch database behind
> (proof 5's restore target). This is harmless on CI and fresh installs; run it
> knowingly against a live system.

### TLS

Caddy terminates TLS with its **internal CA** (`tls internal { on_demand }` in
`deploy/caddy/Caddyfile` — deliberate, since the VM is reached by bare IP with
no public hostname). The root CA certificate is written on first boot to
`${KPI_DATA_ROOT}/caddy/data/caddy/pki/authorities/local/root.crt`.
Distributing that cert to client machines/browsers and verifying bare-IP SNI
trust are PR-4 runbook items, not covered here.

### Backups

The `backup` sidecar (`deploy/backup/backup-loop.sh`) dumps nightly at
`BACKUP_HOUR` (default `02`, i.e. 02:00) to `${KPI_DATA_ROOT}/backups`,
retaining `BACKUP_RETENTION_DAYS` days (default 14). `BACKUP_HOUR` is
interpreted in the sidecar's timezone, which defaults to UTC — set `TZ`
(e.g. `TZ=America/Monterrey` in `.env`) to schedule at local wall-clock time.
It uses **`mariadb-dump`**, not `mysqldump` — the `mariadb:11` image only ships
the `mariadb-*` binary names — and writes to a `.tmp` file before renaming on
success, so a dump that fails partway can never be mistaken for a good one; the
prune step also sweeps stale `.tmp` files older than a day. In loop mode a
failed dump is logged and retried the next cycle rather than crashing the
sidecar (the `--once` manual/CI run keeps its fail-fast non-zero exit).

Manual run:

```bash
docker compose -f docker-compose.prod.yml exec backup bash /backup-loop.sh --once
```

**Verify a dump into a scratch database first** (the same check `compose-smoke.sh`
proof 5 runs) — this finds the latest dump, restores it into a scratch DB, and
asserts it has tables:

```bash
bash deploy/backup/restore-verify.sh              # scratch DB: smoke_restore
```

Once verified, restore into the real database (manual fallback):

```bash
dump=$(docker compose -f docker-compose.prod.yml exec -T backup sh -c \
  'ls -t /backups/kpi_platform-*.sql.gz | head -1' | tr -d '\r')
docker compose -f docker-compose.prod.yml stop backend
docker compose -f docker-compose.prod.yml exec -T backup sh -c \
  "zcat < $dump | mariadb -h db -u root -p\"\$DB_ROOT_PASSWORD\" kpi_platform"
docker compose -f docker-compose.prod.yml start backend
```

### Failed-migration recovery

MariaDB DDL is non-transactional: a migration that fails partway through
leaves a partially-applied schema with `alembic_version` unadvanced, and it is
not safe to assume `alembic upgrade head` can simply be re-run against that
half-migrated state. Recovery is restore-from-the-latest-backup (procedure
above) or drop and recreate the database, then bring the stack back up so the
entrypoint re-applies migrations from a clean slate.

---

## Render.com Deployment

Render.com provides a managed Docker hosting platform with persistent disks, automatic HTTPS, and zero-config deploys from Git.

### One-Click Deploy

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/YOUR_ORG/kpi-operations)

This uses the `render.yaml` blueprint at the project root to provision both services automatically.

### Architecture on Render

| Service | Type | Runtime | Plan | Port |
|---------|------|---------|------|------|
| `kpi-operations-api` | Web Service | Docker | Starter | 8000 |
| `kpi-operations-frontend` | Web Service | Docker | Starter | 80 |

- **Backend**: Uses the root `Dockerfile` (multi-stage, Python 3.11, non-root user)
- **Frontend**: Uses `frontend/Dockerfile` (nginx serving the Vue 3 SPA)
- **Database**: SQLite on a 1 GB persistent disk mounted at `/app/database`
- **API Proxy**: nginx in the frontend container proxies `/api/` to the backend service

### Manual Setup (Without Blueprint)

If you prefer manual configuration over the `render.yaml` blueprint:

#### 1. Create the Backend Service

1. Go to **Dashboard > New > Web Service**
2. Connect your Git repository
3. Configure:
   - **Name**: `kpi-operations-api`
   - **Runtime**: Docker
   - **Dockerfile Path**: `./Dockerfile`
   - **Docker Context**: `.` (project root)
   - **Plan**: Starter ($7/month) or higher
   - **Health Check Path**: `/health/live`

4. Add a **Persistent Disk**:
   - **Name**: `kpi-database`
   - **Mount Path**: `/app/database`
   - **Size**: 1 GB

5. Add **Environment Variables** (see table below)

#### 2. Create the Frontend Service

1. Go to **Dashboard > New > Web Service**
2. Connect the same Git repository
3. Configure:
   - **Name**: `kpi-operations-frontend`
   - **Runtime**: Docker
   - **Dockerfile Path**: `./frontend/Dockerfile`
   - **Docker Context**: `./frontend`
   - **Plan**: Starter ($7/month) or higher
   - **Health Check Path**: `/health`

4. Set the **Docker Command** (replaces the internal Docker hostname with the backend's public URL):
   ```
   sh -c "sed -i 's|http://backend:8000|https://kpi-operations-api.onrender.com|g' /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"
   ```

5. Add **Environment Variables**:
   - `VITE_API_URL` = `/api`
   - `CSP_CONNECT_EXTRA` = `https://kpi-operations-api.onrender.com` (if the `dockerCommand` sed replacement is not used and the API is on a separate domain)

### Environment Variables

#### Backend (`kpi-operations-api`)

| Variable | Value | Notes |
|----------|-------|-------|
| `ENVIRONMENT` | `production` | Enables production config validation |
| `SECRET_KEY` | (auto-generated) | Render generates a secure random value |
| `DATABASE_URL` | `sqlite:////app/database/kpi_platform.db` | Four slashes: `sqlite:///` + absolute path `/app/...` |
| `CORS_ORIGINS` | `https://kpi-operations-frontend.onrender.com` | Must match the frontend service URL exactly |
| `DEBUG` | `false` | Never enable in production |
| `DEMO_MODE` | `true` | Seeds demo data on first startup |
| `RUN_MIGRATIONS` | `true` | Docker entrypoint: applies Alembic migrations before the app starts (fatal on failure) |
| `RUN_MIGRATIONS_ON_STARTUP` | `true` | In-process (FastAPI lifespan) migrate-on-boot; set `false` in multi-worker prod where the entrypoint already owns migrations, to avoid every worker racing to migrate |
| `LOG_LEVEL` | `INFO` | Set to `DEBUG` for troubleshooting |
| `REPORT_EMAIL_ENABLED` | `false` | Enable only after configuring SMTP/SendGrid |

> **CORS_ORIGINS** is marked `sync: false` in `render.yaml` — you must set it manually after the frontend service URL is known.

#### Frontend (`kpi-operations-frontend`)

| Variable | Value | Notes |
|----------|-------|-------|
| `VITE_API_URL` | `/api` | Relative path; nginx proxies to the backend |
| `CSP_CONNECT_EXTRA` | (optional) | Extra domains for CSP `connect-src`; not needed if using the `dockerCommand` sed approach |

### Persistent Disk and SQLite

Render's persistent disks survive deploys and restarts. The SQLite database file lives at `/app/database/kpi_platform.db` on a 1 GB disk.

**Important considerations:**

- Persistent disks are tied to a single service instance. SQLite does not support concurrent writes from multiple instances.
- Keep the Render plan at a **single instance** (no horizontal scaling) while using SQLite.
- The disk persists across deploys, but **not across service deletions**. Back up regularly.

#### Backup Strategy

A backup script is provided at `backend/scripts/backup_sqlite.sh`:

```bash
# Run manually via Render Shell (Dashboard > Shell)
cd /app && bash backend/scripts/backup_sqlite.sh

# Or schedule via a Render Cron Job:
#   Name:     kpi-backup
#   Schedule: 0 2 * * *  (daily at 2 AM UTC)
#   Command:  bash /app/backend/scripts/backup_sqlite.sh
```

The script:
- Uses the SQLite `.backup` API (safe for concurrent access)
- Saves timestamped copies to `/app/database/backups/`
- Rotates old backups, keeping the last 5 by default (`MAX_BACKUPS` env var)

To download a backup, use Render Shell:
```bash
# List backups
ls -lh /app/database/backups/

# Copy to a temporary URL (Render doesn't have scp)
# Use the Render API or mount the disk to another service
```

### Upgrading to a Managed Database

SQLite is suitable for demos and small single-user deployments. For production with multiple concurrent users, upgrade to a managed database:

#### Option A: Render PostgreSQL

1. Create a **PostgreSQL** database in Render Dashboard
2. Update the backend environment variable:
   ```
   DATABASE_URL=postgresql://user:password@host:5432/kpi_platform
   ```
3. Add `psycopg2-binary` to `backend/requirements.txt`
4. Remove the persistent disk (no longer needed)
5. Redeploy

#### Option B: PlanetScale (MySQL/MariaDB-compatible)

1. Create a PlanetScale database at https://planetscale.com
2. Update the backend environment variable:
   ```
   DATABASE_URL=mysql+pymysql://user:password@host:3306/kpi_platform?ssl_ca=/etc/ssl/certs/ca-certificates.crt
   ```
3. Add `pymysql` and `cryptography` to `backend/requirements.txt` (already present)
4. Remove the persistent disk
5. Redeploy

> **Note:** The backend uses SQLAlchemy ORM, so switching databases requires only changing `DATABASE_URL`. Schema creation is handled automatically on startup via Alembic migrations (`backend/alembic/versions/`).

### CORS Configuration

The CORS validator in `backend/config.py` requires origins to start with `http://` or `https://`. Render URLs use `https://` by default, so they pass validation without changes.

After deploying, set `CORS_ORIGINS` on the backend to the frontend's full URL:

```
CORS_ORIGINS=https://kpi-operations-frontend.onrender.com
```

If using a custom domain:
```
CORS_ORIGINS=https://kpi.yourdomain.com
```

Multiple origins (comma-separated):
```
CORS_ORIGINS=https://kpi.yourdomain.com,https://www.kpi.yourdomain.com
```

### Custom Domains

1. Go to your Render service **Settings > Custom Domains**
2. Add your domain (e.g., `kpi.yourdomain.com`)
3. Configure DNS as instructed by Render
4. Render provisions a free TLS certificate automatically
5. Update `CORS_ORIGINS` on the backend to match the new domain

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Frontend 502 on `/api/*` | Verify the `dockerCommand` sed replacement matches the backend service name |
| CORS errors | Check `CORS_ORIGINS` includes the exact frontend URL (with `https://`) |
| Database lost after deploy | Verify persistent disk is attached at `/app/database` |
| Health check failing | Backend: check `/health/live` returns 200; Frontend: check `/health` returns 200 |
| Demo data missing | Set `DEMO_MODE=true` and `RUN_MIGRATIONS=true`, then redeploy |
| Slow cold starts | Render Starter plan spins down after 15 min inactivity; upgrade to Standard for always-on |

---

## Health Check Endpoints

### Available Health Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Basic API health check |
| `/api/health` | GET | Detailed health status |
| `/api/health/db` | GET | Database connectivity |
| `/api/health/ready` | GET | Kubernetes readiness probe |
| `/api/health/live` | GET | Kubernetes liveness probe |

### Health Check Response

```bash
# Basic health check
curl https://api.kpi.yourdomain.com/

# Response:
{
  "status": "healthy",
  "service": "Manufacturing KPI Platform API",
  "version": "1.0.0",
  "timestamp": "2026-01-25T12:00:00.000Z"
}
```

### Monitoring Health

```bash
# Add to monitoring system (e.g., Prometheus, Nagios)
# Check every 30 seconds

curl -s https://api.kpi.yourdomain.com/api/health | jq '.status'
# Expected: "healthy"
```

---

## Security Checklist

### Pre-Deployment Checklist

- [ ] **SECRET_KEY** - Generated secure 64+ character key
- [ ] **DEBUG=False** - Debug mode disabled
- [ ] **Database password** - Strong, unique password set
- [ ] **CORS origins** - Production domains only, no localhost
- [ ] **HTTPS enabled** - Valid SSL certificate installed
- [ ] **Firewall configured** - Only ports 80/443 exposed
- [ ] **Database backups** - Automated backup schedule configured
- [ ] **Log rotation** - Configured to prevent disk fill
- [ ] **Rate limiting** - Enabled on API and auth endpoints
- [ ] **File permissions** - Appropriate ownership and permissions

### Security Configuration Verification

```bash
# Verify configuration
cd /var/www/kpi-platform/backend
source venv/bin/activate
python -c "from backend.config import validate_production_config; print(validate_production_config(raise_on_critical=True))"
```

---

## Monitoring & Logging

### Log Locations

| Log | Location | Purpose |
|-----|----------|---------|
| Backend access | `/var/log/kpi-platform/access.log` | API requests |
| Backend errors | `/var/log/kpi-platform/error.log` | Application errors |
| Nginx access | `/var/log/nginx/access.log` | HTTP requests |
| Nginx errors | `/var/log/nginx/error.log` | Proxy errors |
| Systemd | `journalctl -u kpi-backend` | Service logs |

### Log Rotation

Create `/etc/logrotate.d/kpi-platform`:

```
/var/log/kpi-platform/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload kpi-backend > /dev/null 2>&1 || true
    endscript
}
```

### Real-time Monitoring

```bash
# Watch backend logs
tail -f /var/log/kpi-platform/access.log

# Watch systemd service
journalctl -u kpi-backend -f

# Check resource usage
htop
# or
docker stats  # For Docker deployment
```

---

## Backup Strategy

### Database Backup Script

Create `/usr/local/bin/backup-kpi-db.sh`:

```bash
#!/bin/bash
set -e

# Configuration
BACKUP_DIR="/backup/kpi-platform"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="kpi_platform"
DB_USER="kpi_user"
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create backup
mysqldump -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" | gzip > "$BACKUP_DIR/kpi_$DATE.sql.gz"

# Remove old backups
find "$BACKUP_DIR" -name "kpi_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Log success
echo "$(date): Backup completed - kpi_$DATE.sql.gz" >> /var/log/kpi-backup.log
```

### Schedule Backup

```bash
# Make executable
sudo chmod +x /usr/local/bin/backup-kpi-db.sh

# Add to crontab (runs daily at 2 AM)
sudo crontab -e
# Add line:
0 2 * * * /usr/local/bin/backup-kpi-db.sh
```

### Restore from Backup

```bash
# Restore database
gunzip < /backup/kpi-platform/kpi_YYYYMMDD_HHMMSS.sql.gz | mysql -u kpi_user -p kpi_platform
```

---

## Troubleshooting

### Backend Issues

```bash
# Check service status
sudo systemctl status kpi-backend

# View recent logs
journalctl -u kpi-backend -n 100

# Test backend manually
cd /var/www/kpi-platform/backend
source venv/bin/activate
python -c "from backend.main import app; print('OK')"

# Check database connection
python -c "from backend.database import engine; engine.connect(); print('DB OK')"
```

### Frontend Issues

```bash
# Check nginx status
sudo systemctl status nginx

# Test nginx configuration
sudo nginx -t

# Check nginx error log
tail -f /var/log/nginx/error.log

# Rebuild frontend
cd /var/www/kpi-platform/frontend
npm run build
```

### Database Issues

```bash
# Check MariaDB status
sudo systemctl status mariadb

# Test connection
mysql -u kpi_user -p -e "SELECT 1" kpi_platform

# Check for locks
mysql -u root -p -e "SHOW PROCESSLIST"
```

### Common Issues

| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | Check backend is running, check Nginx proxy_pass |
| Database connection refused | Verify MariaDB running, check credentials |
| CORS errors | Verify CORS_ORIGINS includes frontend domain |
| Permission denied | Check file ownership (www-data) |
| Out of memory | Increase server RAM or reduce Gunicorn workers |

---

## Support

For deployment issues:
1. Check application logs first
2. Review this documentation
3. Contact the development team

**Emergency Contact**: [Your support contact]

---

**Last Updated**: 2026-02-23
**Version**: 2.0.0
