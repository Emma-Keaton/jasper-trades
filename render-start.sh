# Render Start Script - Serves both backend API and frontend
# This script starts the unified server

set -e

echo "🚀 Starting Jasper Trades (Backend API + Frontend)..."

# Check if frontend build exists
if [ ! -d "backend/static/.next" ]; then
    echo "⚠️  Frontend build not found. Running build first..."
    sh render-build.sh
fi

# Start FastAPI with static file serving
echo "🌐 Starting server on port $PORT..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT