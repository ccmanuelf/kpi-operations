# Deployment Guide - Manufacturing KPI Platform

## Quick Start

### 1. Database Setup

```bash
# Create database and user
mysql -u root -p << EOF
CREATE DATABASE kpi_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'kpi_user'@'localhost' IDENTIFIED BY 'CHANGE_THIS_PASSWORD';
GRANT ALL PRIVILEGES ON kpi_platform.* TO 'kpi_user'@'localhost';
FLUSH PRIVILEGES;
EOF

# Run schema
mysql -u kpi_user -p kpi_platform < database/schema.sql

# Load seed data (optional for production)
mysql -u kpi_user -p kpi_platform < database/seed_data.sql
```

### 2. Backend Deployment

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with production values

# Run with uvicorn (development)
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Run with Gunicorn (production)
gunicorn backend.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### 3. Frontend Deployment

```bash
cd frontend

# Install dependencies
npm install

# Build for production
npm run build

# Serve with nginx (see nginx config below)
```

## Production Environment Variables

### Backend `.env`

```env
# Database
DATABASE_URL=mysql+pymysql://kpi_user:SECURE_PASSWORD@localhost:3306/kpi_platform
DB_HOST=localhost
DB_PORT=3306
DB_NAME=kpi_platform
DB_USER=kpi_user
DB_PASSWORD=SECURE_PASSWORD

# JWT (Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=YOUR_SUPER_SECRET_KEY_MINIMUM_32_CHARACTERS_LONG
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# CORS (Update with your frontend domain)
CORS_ORIGINS=https://kpi.yourdomain.com

# Application
DEBUG=False
LOG_LEVEL=INFO

# File Upload
MAX_UPLOAD_SIZE=10485760
UPLOAD_DIR=/var/www/kpi-platform/uploads

# Reports
REPORT_OUTPUT_DIR=/var/www/kpi-platform/reports
```

## Nginx Configuration

### Backend Proxy

```nginx
# /etc/nginx/sites-available/kpi-backend

upstream kpi_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name api.kpi.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.kpi.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api.kpi.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.kpi.yourdomain.com/privkey.pem;

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    location / {
        proxy_pass http://kpi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # File upload size
    client_max_body_size 10M;
}
```

### Frontend

```nginx
# /etc/nginx/sites-available/kpi-frontend

server {
    listen 80;
    server_name kpi.yourdomain.com;

    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name kpi.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/kpi.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kpi.yourdomain.com/privkey.pem;

    root /var/www/kpi-platform/frontend/dist;
    index index.html;

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Content-Security-Policy "default-src 'self' https://api.kpi.yourdomain.com;";

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 10240;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json;

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
        proxy_pass https://api.kpi.yourdomain.com;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Systemd Service (Backend)

```ini
# /etc/systemd/system/kpi-backend.service

[Unit]
Description=KPI Platform Backend
After=network.target mariadb.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/kpi-platform/backend
Environment="PATH=/var/www/kpi-platform/backend/venv/bin"
ExecStart=/var/www/kpi-platform/backend/venv/bin/gunicorn backend.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile - \
    --error-logfile -

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable kpi-backend
sudo systemctl start kpi-backend
sudo systemctl status kpi-backend
```

## Docker Deployment

### docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: mariadb:10.11
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MYSQL_DATABASE: kpi_platform
      MYSQL_USER: kpi_user
      MYSQL_PASSWORD: ${DB_PASSWORD}
    volumes:
      - db_data:/var/lib/mysql
      - ./database/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
      - ./database/seed_data.sql:/docker-entrypoint-initdb.d/02-seed.sql
    networks:
      - kpi_network

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: mysql+pymysql://kpi_user:${DB_PASSWORD}@db:3306/kpi_platform
      SECRET_KEY: ${SECRET_KEY}
      CORS_ORIGINS: ${CORS_ORIGINS}
    depends_on:
      - db
    volumes:
      - ./uploads:/app/uploads
      - ./reports:/app/reports
    networks:
      - kpi_network

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
    networks:
      - kpi_network

volumes:
  db_data:

networks:
  kpi_network:
```

## Security Checklist

- [ ] Change all default passwords
- [ ] Generate strong SECRET_KEY for JWT
- [ ] Configure CORS origins properly
- [ ] Enable HTTPS with valid SSL certificates
- [ ] Set DEBUG=False in production
- [ ] Configure firewall (only allow 80/443)
- [ ] Enable database backups
- [ ] Set up log rotation
- [ ] Configure rate limiting
- [ ] Enable database connection pooling
- [ ] Review user permissions
- [ ] Set up monitoring (e.g., Prometheus, Grafana)

## Backup Strategy

### Database Backup

```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/kpi-platform"
mkdir -p $BACKUP_DIR

mysqldump -u kpi_user -p$DB_PASSWORD kpi_platform | gzip > $BACKUP_DIR/kpi_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "kpi_*.sql.gz" -mtime +30 -delete
```

Add to crontab:

```bash
0 2 * * * /usr/local/bin/backup-kpi-db.sh
```

## Monitoring

### Health Check Endpoint

```bash
# Backend health
curl https://api.kpi.yourdomain.com/

# Database connection
curl https://api.kpi.yourdomain.com/api/products
```

### Log Monitoring

```bash
# Backend logs
journalctl -u kpi-backend -f

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

## Performance Optimization

### Database Indexing

Already configured in schema.sql:
- Composite indexes on frequently queried columns
- Foreign key indexes
- Date range indexes

### Caching

Consider adding Redis for:
- Session storage
- API response caching
- Real-time dashboard data

### Connection Pooling

Configured in backend/database.py:
- pool_size=10
- max_overflow=20
- pool_pre_ping=True

## Troubleshooting

### Backend won't start

```bash
# Check logs
journalctl -u kpi-backend -n 50

# Test manually
cd /var/www/kpi-platform/backend
source venv/bin/activate
python -c "from backend.main import app; print('OK')"
```

### Database connection issues

```bash
# Test connection
mysql -u kpi_user -p -h localhost kpi_platform

# Check MariaDB status
sudo systemctl status mariadb
```

### Frontend not loading

```bash
# Check nginx status
sudo systemctl status nginx

# Test nginx config
sudo nginx -t

# Check error logs
tail -f /var/log/nginx/error.log
```

---

**Need help?** Check the main README.md or contact support.
