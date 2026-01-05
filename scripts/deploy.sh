#!/bin/bash

###############################################################################
# KPI Operations Platform - Production Deployment Script
# Version: 1.0.0
# Date: January 2, 2026
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="kpi-operations"
DEPLOYMENT_DIR="/var/www/${APP_NAME}"
BACKUP_DIR="/var/backups/${APP_NAME}"
LOG_FILE="/var/log/${APP_NAME}/deployment.log"

# Functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

check_requirements() {
    log "Checking system requirements..."

    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        error "Please run as root or with sudo"
    fi

    # Check Python version
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is required but not installed"
    fi

    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
    if [ $(echo "$PYTHON_VERSION < 3.8" | bc) -eq 1 ]; then
        error "Python 3.8 or higher is required (found $PYTHON_VERSION)"
    fi

    # Check Node.js version
    if ! command -v node &> /dev/null; then
        error "Node.js is required but not installed"
    fi

    NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 16 ]; then
        error "Node.js 16 or higher is required (found $NODE_VERSION)"
    fi

    # Check required packages
    for cmd in git nginx sqlite3 systemctl; do
        if ! command -v $cmd &> /dev/null; then
            error "$cmd is required but not installed"
        fi
    done

    log "✅ All system requirements met"
}

check_environment_variables() {
    log "Checking environment variables..."

    required_vars=(
        "DATABASE_URL"
        "JWT_SECRET"
        "API_BASE_URL"
        "SMTP_HOST"
        "SMTP_USER"
        "SMTP_PASS"
    )

    missing_vars=()

    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        error "Missing required environment variables: ${missing_vars[*]}"
    fi

    log "✅ All required environment variables are set"
}

create_backup() {
    log "Creating backup..."

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="${BACKUP_DIR}/backup_${TIMESTAMP}"

    mkdir -p "$BACKUP_PATH"

    # Backup database
    if [ -f "${DEPLOYMENT_DIR}/kpi_platform.db" ]; then
        cp "${DEPLOYMENT_DIR}/kpi_platform.db" "${BACKUP_PATH}/kpi_platform.db"
        log "✅ Database backed up to ${BACKUP_PATH}"
    fi

    # Backup configuration
    if [ -f "${DEPLOYMENT_DIR}/.env" ]; then
        cp "${DEPLOYMENT_DIR}/.env" "${BACKUP_PATH}/.env"
    fi

    log "✅ Backup created: ${BACKUP_PATH}"
    echo "$BACKUP_PATH" > /tmp/last_backup_path
}

setup_database() {
    log "Setting up database..."

    cd "${DEPLOYMENT_DIR}/database"

    # Run schema initialization
    if [ ! -f "${DEPLOYMENT_DIR}/kpi_platform.db" ]; then
        log "Creating new database..."
        sqlite3 "${DEPLOYMENT_DIR}/kpi_platform.db" < schema_complete_multitenant.sql
        log "✅ Database schema created"
    else
        log "Database already exists, running migrations..."
        # Run migration scripts here if needed
    fi

    # Load seed data if empty database
    TABLE_COUNT=$(sqlite3 "${DEPLOYMENT_DIR}/kpi_platform.db" "SELECT COUNT(*) FROM CLIENT;")
    if [ "$TABLE_COUNT" -eq 0 ]; then
        log "Loading seed data..."
        python3 ../scripts/generate_complete_sample_data.py
        log "✅ Seed data loaded"
    fi

    log "✅ Database setup complete"
}

install_backend() {
    log "Installing backend dependencies..."

    cd "${DEPLOYMENT_DIR}/backend"

    # Create virtual environment
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi

    source venv/bin/activate

    # Install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt

    log "✅ Backend dependencies installed"
}

install_frontend() {
    log "Installing frontend dependencies..."

    cd "${DEPLOYMENT_DIR}/frontend"

    # Install npm dependencies
    npm install

    # Build frontend
    log "Building frontend..."
    npm run build

    log "✅ Frontend built successfully"
}

setup_systemd() {
    log "Setting up systemd service..."

    # Create systemd service file
    cat > /etc/systemd/system/${APP_NAME}-backend.service << EOF
[Unit]
Description=KPI Operations Platform Backend
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${DEPLOYMENT_DIR}/backend
Environment="PATH=${DEPLOYMENT_DIR}/backend/venv/bin"
ExecStart=${DEPLOYMENT_DIR}/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload
    systemctl enable ${APP_NAME}-backend.service

    log "✅ Systemd service configured"
}

setup_nginx() {
    log "Setting up Nginx..."

    # Create Nginx configuration
    cat > /etc/nginx/sites-available/${APP_NAME} << 'EOF'
server {
    listen 80;
    server_name _;

    # Frontend
    location / {
        root /var/www/kpi-operations/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files
    location /static {
        alias /var/www/kpi-operations/frontend/dist/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

    # Enable site
    ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default

    # Test Nginx configuration
    nginx -t || error "Nginx configuration test failed"

    log "✅ Nginx configured"
}

setup_ssl() {
    log "Setting up SSL certificate..."

    if command -v certbot &> /dev/null; then
        certbot --nginx -d $DOMAIN_NAME --non-interactive --agree-tos -m $SSL_EMAIL
        log "✅ SSL certificate installed"
    else
        warning "Certbot not installed. Skipping SSL setup."
        log "To install SSL later, run: sudo certbot --nginx -d yourdomain.com"
    fi
}

start_services() {
    log "Starting services..."

    # Start backend
    systemctl restart ${APP_NAME}-backend.service
    systemctl status ${APP_NAME}-backend.service --no-pager

    # Reload Nginx
    systemctl reload nginx

    log "✅ Services started"
}

run_health_check() {
    log "Running health check..."

    sleep 5  # Wait for services to start

    # Check backend
    if curl -f http://localhost:8000/health &> /dev/null; then
        log "✅ Backend health check passed"
    else
        error "Backend health check failed"
    fi

    # Check frontend
    if curl -f http://localhost/ &> /dev/null; then
        log "✅ Frontend health check passed"
    else
        error "Frontend health check failed"
    fi

    log "✅ All health checks passed"
}

show_summary() {
    log ""
    log "========================================="
    log "DEPLOYMENT COMPLETED SUCCESSFULLY"
    log "========================================="
    log ""
    log "Application: ${APP_NAME}"
    log "Deployment Directory: ${DEPLOYMENT_DIR}"
    log "Backup Location: $(cat /tmp/last_backup_path)"
    log ""
    log "Services:"
    log "  Backend:  systemctl status ${APP_NAME}-backend"
    log "  Nginx:    systemctl status nginx"
    log ""
    log "Logs:"
    log "  Backend:  journalctl -u ${APP_NAME}-backend -f"
    log "  Nginx:    tail -f /var/log/nginx/access.log"
    log "  Deploy:   tail -f ${LOG_FILE}"
    log ""
    log "URLs:"
    log "  Frontend: http://$(hostname -I | awk '{print $1}')"
    log "  API:      http://$(hostname -I | awk '{print $1}')/api"
    log "  Docs:     http://$(hostname -I | awk '{print $1}')/api/docs"
    log ""
    log "Next Steps:"
    log "  1. Configure SSL: sudo certbot --nginx -d yourdomain.com"
    log "  2. Set up monitoring and logging"
    log "  3. Configure firewall rules"
    log "  4. Set up automated backups"
    log "  5. Review /var/log/${APP_NAME}/deployment.log"
    log ""
    log "========================================="
}

rollback() {
    log "Rolling back deployment..."

    LAST_BACKUP=$(cat /tmp/last_backup_path)

    if [ -d "$LAST_BACKUP" ]; then
        # Restore database
        if [ -f "${LAST_BACKUP}/kpi_platform.db" ]; then
            cp "${LAST_BACKUP}/kpi_platform.db" "${DEPLOYMENT_DIR}/kpi_platform.db"
            log "✅ Database restored"
        fi

        # Restart services
        systemctl restart ${APP_NAME}-backend.service
        log "✅ Services restarted"

        log "✅ Rollback completed"
    else
        error "No backup found to rollback to"
    fi
}

# Main deployment flow
main() {
    log "========================================="
    log "KPI OPERATIONS PLATFORM DEPLOYMENT"
    log "========================================="

    check_requirements
    check_environment_variables
    create_backup
    setup_database
    install_backend
    install_frontend
    setup_systemd
    setup_nginx

    # Optional: SSL setup
    if [ -n "$DOMAIN_NAME" ] && [ -n "$SSL_EMAIL" ]; then
        setup_ssl
    fi

    start_services
    run_health_check
    show_summary
}

# Handle script arguments
case "${1:-deploy}" in
    deploy)
        main
        ;;
    rollback)
        rollback
        ;;
    backup)
        create_backup
        ;;
    health-check)
        run_health_check
        ;;
    *)
        echo "Usage: $0 {deploy|rollback|backup|health-check}"
        exit 1
        ;;
esac
