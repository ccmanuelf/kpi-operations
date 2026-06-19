#!/bin/bash
#
# Manufacturing KPI Platform - Backend Launcher
# Starts FastAPI backend server with SQLite database
#

echo "🚀 Manufacturing KPI Platform - Backend Launcher"
echo "=" * 70
echo ""

# Navigate to project root
cd "$(dirname "$0")/.." || exit 1

# With DEMO_MODE=true the backend auto-creates the schema and seeds demo
# data on first boot, so a missing database file is fine (it will be created).
if [ ! -f "database/kpi_platform.db" ]; then
    echo "ℹ️  No database yet — DEMO_MODE will auto-create and seed it on boot."
else
    echo "✓ Database found: database/kpi_platform.db"
fi
echo ""

# Kill any existing backend processes
echo "🧹 Cleaning up existing processes..."
pkill -f "uvicorn backend.main" 2>/dev/null
sleep 2

# Start backend
echo "🔧 Starting FastAPI backend on http://localhost:8000"
echo "   API Documentation: http://localhost:8000/docs"
echo "   Alternative docs: http://localhost:8000/redoc"
echo ""
echo "Press CTRL+C to stop the server"
echo "=" * 70
echo ""

# Use python -m to ensure proper module resolution.
# DEMO_MODE=true triggers the on-boot schema create + demo seed.
DEMO_MODE=true python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
