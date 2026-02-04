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
CAPACITY_PLANNING_ENABLED=${CAPACITY_PLANNING_ENABLED:-true}

echo "Configuration:"
echo "  RUN_MIGRATIONS: $RUN_MIGRATIONS"
echo "  DEMO_MODE: $DEMO_MODE"
echo "  CAPACITY_PLANNING_ENABLED: $CAPACITY_PLANNING_ENABLED"
echo ""

# Function to run database migrations
run_migrations() {
    echo "[INIT] Running database migrations..."

    # Create capacity planning tables if enabled
    if [ "$CAPACITY_PLANNING_ENABLED" = "true" ]; then
        echo "[INIT] Creating capacity planning tables..."
        python -c "
from backend.db.migrations.capacity_planning_tables import create_capacity_tables, verify_capacity_tables
try:
    created = create_capacity_tables()
    if created:
        print(f'[INIT] Created capacity tables: {created}')
    else:
        print('[INIT] All capacity tables already exist')

    # Verify tables
    result = verify_capacity_tables()
    if result['valid']:
        print(f'[INIT] Capacity tables verified: {result[\"present_count\"]} tables')
    else:
        print(f'[WARN] Missing capacity tables: {result[\"missing_tables\"]}')
except Exception as e:
    print(f'[WARN] Failed to create capacity tables: {e}')
" 2>&1 || echo "[WARN] Capacity table creation returned non-zero (may be expected if tables exist)"
    fi

    echo "[INIT] Migrations complete"
}

# Function to seed demo data
seed_demo_data() {
    echo "[INIT] Seeding demo data..."
    python -c "
from backend.database import SessionLocal
from backend.db.migrations.demo_seeder import DemoDataSeeder

try:
    db = SessionLocal()
    seeder = DemoDataSeeder(db)
    counts = seeder.seed_all()
    db.close()
    print(f'[INIT] Demo data seeded: {counts}')
except Exception as e:
    print(f'[WARN] Demo data seeding failed: {e}')
" 2>&1 || echo "[WARN] Demo data seeding returned non-zero"

    echo "[INIT] Demo data seeding complete"
}

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
    # Wait a moment for any dependent services (like databases) to be ready
    sleep 2

    # Check database connectivity
    check_database

    # Run migrations if enabled
    if [ "$RUN_MIGRATIONS" = "true" ]; then
        run_migrations
    fi

    # Seed demo data if in demo mode
    if [ "$DEMO_MODE" = "true" ]; then
        seed_demo_data
    fi

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
