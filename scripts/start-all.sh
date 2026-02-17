#!/bin/bash
#
# Manufacturing KPI Platform - Complete Application Launcher
# Starts both backend and frontend in separate terminal tabs
#

echo "🚀 Manufacturing KPI Platform - Complete Launcher"
echo "=" * 70
echo ""

cd "$(dirname "$0")/.." || exit 1

# Check if database exists
if [ ! -f "database/kpi_platform.db" ]; then
    echo "❌ Database not found!"
    echo "   Initializing database..."
    python3 database/init_sqlite_schema.py
    echo ""
    echo "   Generating sample data..."
    python3 database/generators/generate_complete_sample_data.py
    echo ""
fi

echo "✅ Database ready"
echo ""

# macOS - Open new Terminal tabs
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🍎 macOS detected - Opening backend and frontend in new tabs..."

    # Backend tab
    osascript -e 'tell application "Terminal"
        do script "cd \"'$(pwd)'\" && ./scripts/start-backend.sh"
        activate
    end tell'

    sleep 3

    # Frontend tab
    osascript -e 'tell application "Terminal"
        do script "cd \"'$(pwd)'\" && ./scripts/start-frontend.sh"
    end tell'

    echo ""
    echo "✅ Application launched in separate Terminal tabs!"
    echo ""
    echo "📱 Access points:"
    echo "   Frontend: http://localhost:3000"
    echo "   Backend API: http://localhost:8000/docs"
    echo "   Database: ./database/kpi_platform.db (SQLite)"
    echo ""
    echo "👤 Demo Credentials: See QUICKSTART.md"
    echo ""

# Linux/Windows - Use tmux if available
elif command -v tmux &> /dev/null; then
    echo "🐧 Linux detected - Starting tmux session..."

    # Create tmux session with two panes
    tmux new-session -d -s kpi-platform
    tmux send-keys -t kpi-platform:0 "./scripts/start-backend.sh" C-m
    tmux split-window -h -t kpi-platform
    tmux send-keys -t kpi-platform:1 "./scripts/start-frontend.sh" C-m
    tmux attach-session -t kpi-platform

else
    echo "⚠️  Please start backend and frontend in separate terminals:"
    echo ""
    echo "   Terminal 1: ./scripts/start-backend.sh"
    echo "   Terminal 2: ./scripts/start-frontend.sh"
    echo ""
fi
