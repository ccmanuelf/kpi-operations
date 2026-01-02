#!/bin/bash
#
# Manufacturing KPI Platform - Frontend Launcher
# Starts Vue 3 + Vuetify development server
#

echo "🎨 Manufacturing KPI Platform - Frontend Launcher"
echo "=" * 70
echo ""

# Navigate to frontend directory
cd "$(dirname "$0")/../frontend" || exit 1

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
    echo ""
fi

echo "✓ Dependencies ready"
echo ""

# Kill any existing frontend processes
echo "🧹 Cleaning up existing processes..."
pkill -f "vite" 2>/dev/null
sleep 2

# Start frontend
echo "🔧 Starting Vue 3 development server"
echo "   Application: http://localhost:5173"
echo "   Backend API: http://localhost:8000"
echo ""
echo "Press CTRL+C to stop the server"
echo "=" * 70
echo ""

npm run dev
