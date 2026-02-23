# Deployment Guide - Manufacturing KPI Platform v1.0.0

This guide covers deploying the KPI Operations Platform to production environments.

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

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 2 cores | 4+ cores |
| **RAM** | 4 GB | 8+ GB |
| **Storage** | 20 GB | 50+ GB SSD |
| **OS** | Ubuntu 20.04+ / RHEL 8+ | Ubuntu 22.04 LTS |

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| **Python** | 3.11+ | Backend runtime |
| **Node.js** | 20+ LTS | Frontend build |
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
DB_HOST=localhost
DB_PORT=3306
DB_NAME=kpi_platform
DB_USER=kpi_user
DB_PASSWORD=SECURE_PASSWORD

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

No manual SQL import is required. The backend automatically creates all tables (via SQLAlchemy `Base.metadata.create_all()` and `create_capacity_tables()`) and seeds comprehensive demo data on first startup when it detects an empty database.

Simply ensure the database exists and the connection is configured (see [Environment Variables](#environment-variables)), then start the backend. Tables and demo data will be created automatically.

> **Note:** This project does not use Alembic or any migration tooling. Schema is managed directly by SQLAlchemy model definitions in the codebase. To reset the database, drop and recreate it in MariaDB, then restart the backend to re-initialize.

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

### Using Docker Compose

The project includes Docker configuration files:

```bash
cd /var/www/kpi-platform

# Create environment file
cp .env.example .env
nano .env  # Edit production values

# Build and start containers
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop containers
docker-compose down
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: mariadb:10.11
    container_name: kpi_db
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MYSQL_DATABASE: kpi_platform
      MYSQL_USER: kpi_user
      MYSQL_PASSWORD: ${DB_PASSWORD}
    volumes:
      - db_data:/var/lib/mysql
      # No init SQL needed — the backend auto-creates tables on startup
    networks:
      - kpi_network
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: kpi_backend
    restart: unless-stopped
    environment:
      DATABASE_URL: mysql+pymysql://kpi_user:${DB_PASSWORD}@db:3306/kpi_platform
      SECRET_KEY: ${SECRET_KEY}
      CORS_ORIGINS: ${CORS_ORIGINS}
      ENVIRONMENT: production
      DEBUG: "False"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - uploads:/app/uploads
      - reports:/app/reports
    networks:
      - kpi_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: kpi_frontend
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    networks:
      - kpi_network

volumes:
  db_data:
  uploads:
  reports:

networks:
  kpi_network:
    driver: bridge
```

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
| `RUN_MIGRATIONS` | `true` | Creates tables on startup |
| `LOG_LEVEL` | `INFO` | Set to `DEBUG` for troubleshooting |
| `REPORT_EMAIL_ENABLED` | `false` | Enable only after configuring SMTP/SendGrid |

> **CORS_ORIGINS** is marked `sync: false` in `render.yaml` — you must set it manually after the frontend service URL is known.

#### Frontend (`kpi-operations-frontend`)

| Variable | Value | Notes |
|----------|-------|-------|
| `VITE_API_URL` | `/api` | Relative path; nginx proxies to the backend |

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

> **Note:** The backend uses SQLAlchemy ORM, so switching databases requires only changing `DATABASE_URL`. All table creation is handled automatically on startup via `Base.metadata.create_all()`.

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

**Last Updated**: 2026-02-22
**Version**: 1.1.0
