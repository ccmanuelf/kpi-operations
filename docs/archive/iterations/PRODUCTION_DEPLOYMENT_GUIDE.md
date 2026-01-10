# Production Deployment Guide
## KPI Operations Dashboard Platform - Enterprise Edition

**Version:** 1.0.0
**Date:** January 2, 2026
**Status:** Production Ready ✅

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Deployment Steps](#deployment-steps)
4. [Post-Deployment Validation](#post-deployment-validation)
5. [Monitoring & Logging](#monitoring--logging)
6. [Rollback Procedures](#rollback-procedures)
7. [Common Issues](#common-issues)
8. [Security Hardening](#security-hardening)

---

## Prerequisites

### System Requirements

**Server Specifications:**
- **OS:** Ubuntu 20.04 LTS / Ubuntu 22.04 LTS (recommended)
- **CPU:** 4 cores minimum (8 cores for 50+ clients)
- **RAM:** 8GB minimum (16GB for 50+ clients)
- **Disk:** 100GB SSD (with room for database growth)
- **Network:** 100 Mbps minimum

**Software Dependencies:**
- Python 3.8+ (3.11 recommended)
- Node.js 16+ (18 LTS recommended)
- Nginx 1.18+
- SQLite 3.31+
- Git 2.25+
- systemd (standard on Ubuntu)

### Required Accounts

- **Domain:** Registered domain name (for SSL)
- **Email:** SMTP server credentials for notifications
- **SSL Certificate:** Let's Encrypt (free) or commercial

---

## Pre-Deployment Checklist

### 1. Environment Configuration

Create `/var/www/kpi-operations/.env`:

```bash
# Database
DATABASE_URL=sqlite:///kpi_platform.db
DATABASE_BACKUP_DIR=/var/backups/kpi-operations

# API Configuration
API_BASE_URL=https://yourdomain.com
API_PORT=8000

# Authentication
JWT_SECRET=<GENERATE_STRONG_SECRET_HERE>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=<APP_SPECIFIC_PASSWORD>
SMTP_FROM=noreply@yourdomain.com

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE=10485760  # 10MB
ALLOWED_ORIGINS=https://yourdomain.com

# Multi-Tenant
DEFAULT_CLIENT_LIMIT=50
MAX_EMPLOYEES_PER_CLIENT=200

# Feature Flags
ENABLE_CSV_UPLOAD=true
ENABLE_EMAIL_REPORTS=true
ENABLE_AUTO_BACKUP=true
```

### 2. Generate Secrets

```bash
# Generate JWT secret (use this in .env)
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Generate database encryption key
openssl rand -base64 32
```

### 3. Firewall Configuration

```bash
# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow SSH (if needed)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

### 4. Create Application User

```bash
# Create service user
sudo useradd -r -s /bin/bash -d /var/www/kpi-operations kpiuser
sudo mkdir -p /var/www/kpi-operations
sudo chown -R kpiuser:kpiuser /var/www/kpi-operations
```

---

## Deployment Steps

### Step 1: Clone Repository

```bash
cd /var/www
sudo git clone https://github.com/your-org/kpi-operations.git
cd kpi-operations
sudo chown -R kpiuser:kpiuser .
```

### Step 2: Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
sudo apt install -y python3 python3-pip python3-venv

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install Nginx
sudo apt install -y nginx

# Install SQLite
sudo apt install -y sqlite3

# Install Certbot (for SSL)
sudo apt install -y certbot python3-certbot-nginx
```

### Step 3: Run Automated Deployment

```bash
# Make deployment script executable
chmod +x scripts/deploy.sh

# Set environment variables
export DOMAIN_NAME=yourdomain.com
export SSL_EMAIL=admin@yourdomain.com
export DATABASE_URL=sqlite:///kpi_platform.db
export JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")

# Run deployment
sudo -E ./scripts/deploy.sh deploy
```

The deployment script will:
1. ✅ Check system requirements
2. ✅ Validate environment variables
3. ✅ Create database backup
4. ✅ Initialize database schema
5. ✅ Install backend dependencies
6. ✅ Build frontend
7. ✅ Configure systemd services
8. ✅ Set up Nginx
9. ✅ Install SSL certificate
10. ✅ Start all services
11. ✅ Run health checks

### Step 4: Manual Verification

```bash
# Check backend service
sudo systemctl status kpi-operations-backend

# Check Nginx
sudo systemctl status nginx

# Test API health endpoint
curl http://localhost:8000/health

# Test frontend
curl http://localhost/

# View logs
sudo journalctl -u kpi-operations-backend -f
```

---

## Post-Deployment Validation

### 1. Run Comprehensive Validation Suite

```bash
cd /var/www/kpi-operations

# Schema validation
python3 tests/validation/comprehensive_schema_validation.py

# API endpoint validation
python3 tests/validation/api_endpoint_validation.py

# Security audit
python3 tests/validation/security_audit.py

# Performance benchmarks
python3 tests/validation/performance_benchmarks.py
```

**Expected Results:**
- ✅ Schema: 100% fields present
- ✅ API: All 78+ endpoints functional
- ✅ Security: No critical vulnerabilities
- ✅ Performance: GET < 200ms, POST < 500ms

### 2. Create Test User

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "SecurePassword123!",
    "email": "admin@yourdomain.com",
    "role": "ADMIN"
  }'
```

### 3. Test Multi-Tenant Isolation

```bash
# Create two test clients
curl -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "TEST_A",
    "client_name": "Test Client A"
  }'

curl -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "TEST_B",
    "client_name": "Test Client B"
  }'

# Verify isolation
# Should only see data for assigned client
```

### 4. Test CSV Upload

```bash
# Upload sample production data
curl -X POST http://localhost:8000/api/production/csv-upload \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@database/sample_production_data.csv"
```

### 5. Verify AG Grid Functionality

Access frontend at `https://yourdomain.com` and test:
- ✅ Excel-like editing (cell editing, copy/paste)
- ✅ Fill handle
- ✅ Keyboard navigation (arrows, Enter, Tab)
- ✅ Real-time KPI calculations
- ✅ CSV export
- ✅ Bulk operations
- ✅ Client selector

---

## Monitoring & Logging

### Application Logs

```bash
# Backend logs (systemd)
sudo journalctl -u kpi-operations-backend -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Application logs
sudo tail -f /var/log/kpi-operations/app.log
```

### Health Monitoring

**Health Check Endpoint:**
```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-02T10:00:00Z",
  "uptime": 3600,
  "dependencies": {
    "database": "connected",
    "cache": "connected",
    "email": "configured"
  }
}
```

### Set Up Monitoring (Recommended)

**Option 1: Simple Monitoring Script**

Create `/usr/local/bin/monitor-kpi-ops.sh`:

```bash
#!/bin/bash
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)

if [ "$STATUS" != "200" ]; then
    echo "KPI Operations is DOWN (HTTP $STATUS)" | mail -s "Alert: KPI Ops Down" admin@yourdomain.com
    sudo systemctl restart kpi-operations-backend
fi
```

Add to crontab:
```bash
*/5 * * * * /usr/local/bin/monitor-kpi-ops.sh
```

**Option 2: Enterprise Monitoring**

Consider integrating:
- **Prometheus + Grafana:** For metrics and dashboards
- **ELK Stack:** For log aggregation
- **Uptime Robot / Pingdom:** For external monitoring
- **Sentry:** For error tracking

---

## Rollback Procedures

### Automatic Rollback

If deployment fails, the script automatically creates a backup.

```bash
# Rollback to last backup
sudo ./scripts/deploy.sh rollback
```

### Manual Rollback

```bash
# List backups
ls -la /var/backups/kpi-operations/

# Restore specific backup
BACKUP_DATE=20260102_100000
sudo cp /var/backups/kpi-operations/backup_${BACKUP_DATE}/kpi_platform.db \
        /var/www/kpi-operations/kpi_platform.db

# Restart services
sudo systemctl restart kpi-operations-backend
sudo systemctl reload nginx

# Verify
curl http://localhost:8000/health
```

### Database Recovery

```bash
# Check database integrity
sqlite3 /var/www/kpi-operations/kpi_platform.db "PRAGMA integrity_check;"

# Export data
sqlite3 /var/www/kpi-operations/kpi_platform.db .dump > backup.sql

# Restore from SQL dump
sqlite3 /var/www/kpi-operations/kpi_platform.db < backup.sql
```

---

## Common Issues

### Issue 1: Backend Won't Start

**Symptoms:**
- Service fails to start
- Port 8000 already in use

**Solutions:**
```bash
# Check if port is in use
sudo lsof -i :8000

# Kill process using port
sudo kill -9 <PID>

# Check Python virtual environment
cd /var/www/kpi-operations/backend
source venv/bin/activate
python -c "import fastapi; print('FastAPI OK')"

# Check logs
sudo journalctl -u kpi-operations-backend -n 50
```

### Issue 2: Database Locked

**Symptoms:**
- "database is locked" errors
- Slow queries

**Solutions:**
```bash
# Check for other processes
sudo lsof /var/www/kpi-operations/kpi_platform.db

# Enable WAL mode (if not already)
sqlite3 /var/www/kpi-operations/kpi_platform.db "PRAGMA journal_mode=WAL;"

# Optimize database
sqlite3 /var/www/kpi-operations/kpi_platform.db "VACUUM;"
```

### Issue 3: Nginx 502 Bad Gateway

**Symptoms:**
- Frontend loads but API calls fail
- 502 errors in browser

**Solutions:**
```bash
# Check if backend is running
sudo systemctl status kpi-operations-backend

# Check Nginx configuration
sudo nginx -t

# Check Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Restart both services
sudo systemctl restart kpi-operations-backend
sudo systemctl reload nginx
```

### Issue 4: SSL Certificate Issues

**Symptoms:**
- HTTPS not working
- Certificate warnings

**Solutions:**
```bash
# Renew certificate manually
sudo certbot renew

# Force renewal
sudo certbot renew --force-renewal

# Set up auto-renewal (cron)
sudo crontab -e
# Add: 0 0 * * * certbot renew --quiet
```

### Issue 5: High Memory Usage

**Symptoms:**
- Server becomes slow
- Out of memory errors

**Solutions:**
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head -10

# Optimize SQLite
sqlite3 kpi_platform.db "PRAGMA optimize;"

# Increase server resources (if cloud)
# Or implement caching with Redis

# Configure Nginx caching
# (add to Nginx config)
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m;
```

---

## Security Hardening

### 1. Database Security

```bash
# Set proper permissions
sudo chown kpiuser:kpiuser /var/www/kpi-operations/kpi_platform.db
sudo chmod 600 /var/www/kpi-operations/kpi_platform.db

# Enable foreign keys (should already be in schema)
sqlite3 kpi_platform.db "PRAGMA foreign_keys=ON;"
```

### 2. Application Security

**Configure CORS properly** (backend/config.py):
```python
ALLOWED_ORIGINS = [
    "https://yourdomain.com",
    "https://www.yourdomain.com"
]
```

**Set security headers** (Nginx):
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
```

### 3. OS Security

```bash
# Keep system updated
sudo apt update && sudo apt upgrade -y

# Install fail2ban (prevents brute force)
sudo apt install fail2ban
sudo systemctl enable fail2ban

# Disable root login
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Enable automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 4. Backup Automation

Create `/usr/local/bin/backup-kpi-ops.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/kpi-operations"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup
mkdir -p "${BACKUP_DIR}/backup_${TIMESTAMP}"
cp /var/www/kpi-operations/kpi_platform.db "${BACKUP_DIR}/backup_${TIMESTAMP}/"
cp /var/www/kpi-operations/.env "${BACKUP_DIR}/backup_${TIMESTAMP}/"

# Compress
tar -czf "${BACKUP_DIR}/backup_${TIMESTAMP}.tar.gz" -C "${BACKUP_DIR}" "backup_${TIMESTAMP}"
rm -rf "${BACKUP_DIR}/backup_${TIMESTAMP}"

# Delete old backups
find "${BACKUP_DIR}" -name "backup_*.tar.gz" -mtime +${RETENTION_DAYS} -delete

echo "Backup completed: backup_${TIMESTAMP}.tar.gz"
```

Schedule in crontab:
```bash
# Daily at 2 AM
0 2 * * * /usr/local/bin/backup-kpi-ops.sh
```

---

## Performance Tuning

### SQLite Optimization

```sql
-- Run these periodically
PRAGMA optimize;
PRAGMA wal_checkpoint(TRUNCATE);
ANALYZE;
```

### Nginx Caching

Add to Nginx config:

```nginx
location /api {
    # Cache GET requests for 5 minutes
    proxy_cache api_cache;
    proxy_cache_valid 200 5m;
    proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
    proxy_cache_background_update on;
    proxy_cache_lock on;

    # Existing proxy settings...
}
```

### Frontend Optimization

```bash
# Enable gzip compression in Nginx
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 6;
gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml font/truetype font/opentype application/vnd.ms-fontobject image/svg+xml;

# Set cache headers for static files
location /static {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

---

## Production Ready Checklist

Before going live, verify:

- [ ] All validation tests passing (schema, API, security, performance)
- [ ] SSL certificate installed and auto-renewal configured
- [ ] Database backed up and restore tested
- [ ] Multi-tenant isolation verified
- [ ] Environment variables secured
- [ ] Monitoring and alerting configured
- [ ] Log rotation configured
- [ ] Firewall rules in place
- [ ] Admin users created
- [ ] Demo/test data removed (if applicable)
- [ ] Documentation reviewed with ops team
- [ ] Rollback procedure tested
- [ ] Performance benchmarks meet requirements (< 200ms GET, < 500ms POST)
- [ ] Security audit passed (no critical vulnerabilities)
- [ ] Pilot users identified and trained

---

## Support

**Documentation:** `/var/www/kpi-operations/docs/`
**Logs:** `/var/log/kpi-operations/`
**Backups:** `/var/backups/kpi-operations/`

**Emergency Contacts:**
- Technical Lead: [email]
- DevOps: [email]
- Database Admin: [email]

---

**Deployment Guide Version:** 1.0.0
**Last Updated:** January 2, 2026
**Status:** Production Ready ✅
