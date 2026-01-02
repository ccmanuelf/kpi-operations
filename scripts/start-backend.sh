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

# Check if database exists
if [ ! -f "database/kpi_platform.db" ]; then
    echo "❌ Database not found!"
    echo "   Run: python3 database/init_sqlite_schema.py"
    echo "   Then: python3 database/generators/generate_complete_sample_data.py"
    exit 1
fi

echo "✓ Database found: database/kpi_platform.db"
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

# Use python -m to ensure proper module resolution
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
