#!/bin/bash
# Docker entrypoint script for KPI Operations Platform
# Handles database initialization, migrations, and application startup

set -e

echo "=============================================="
echo "KPI Operations Platform - Docker Entrypoint"
echo "=============================================="
echo "Starting at: $(date)"
echo ""

# Environment variables with defaults
RUN_MIGRATIONS=${RUN_MIGRATIONS:-true}
DEMO_MODE=${DEMO_MODE:-false}

echo "Configuration:"
echo "  RUN_MIGRATIONS: $RUN_MIGRATIONS"
echo "  DEMO_MODE: $DEMO_MODE"
echo ""

# Function to run database migrations (Alembic is the ONLY schema mechanism — C5)
run_migrations() {
    echo "[INIT] Running Alembic migrations..."
    cd /app/backend
    python -m alembic upgrade head
    cd /app
    echo "[INIT] Migrations complete (head)"
}

# Demo seeding is handled by main.py lifespan (smart reseed with TestDataFactory).
# The entrypoint only handles infrastructure (DB connectivity, migrations).

# Function to verify database connectivity
check_database() {
    echo "[INIT] Checking database connectivity..."
    python -c "
from backend.database import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        result.fetchone()
    print('[INIT] Database connection successful')
except Exception as e:
    print(f'[ERROR] Database connection failed: {e}')
    exit(1)
" 2>&1
}

# Main initialization logic
main() {
    # Wait for database to be ready (retry loop, max 30s at 2s intervals)
    echo "[INIT] Waiting for database to be ready..."
    local max_wait=30
    local interval=2
    local elapsed=0
    while [ $elapsed -lt $max_wait ]; do
        if check_database 2>/dev/null; then
            break
        fi
        echo "[INIT] Database not ready, retrying in ${interval}s... (${elapsed}/${max_wait}s)"
        sleep $interval
        elapsed=$((elapsed + interval))
    done

    # Final check
    check_database

    # Run migrations if enabled
    if [ "$RUN_MIGRATIONS" = "true" ]; then
        run_migrations
    fi

    # Note: demo data seeding is handled by main.py lifespan (smart reseed)

    echo ""
    echo "[INIT] Initialization complete"
    echo "=============================================="
    echo ""
}

# Run initialization
main

# Execute the main command (e.g., uvicorn)
echo "[START] Executing command: $@"
exec "$@"
