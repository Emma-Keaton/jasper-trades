#!/bin/sh
# Render Build Script - Builds both backend and frontend
# This script runs before the start command
# Build v2 - Clean node_modules before install

set -e

echo "🔨 Building Jasper Trades (Backend + Frontend)..."

# Clean any existing build artifacts
echo "🧹 Cleaning previous builds..."
rm -rf frontend/node_modules frontend/.next frontend/out 2>/dev/null || true

# Install backend dependencies
echo "📦 Installing Python dependencies..."
pip install -r backend/requirements.txt

# Install frontend dependencies
echo "📦 Installing Node.js dependencies..."
cd frontend
npm ci

# Build frontend with environment variables for production
# NEXT_PUBLIC_WS_URL and NEXT_PUBLIC_API_URL should be set in Render dashboard
echo "🏗️  Building Next.js frontend..."
echo "   API URL: ${NEXT_PUBLIC_API_URL:-'not set'}"
echo "   WS URL:  ${NEXT_PUBLIC_WS_URL:-'not set'}"
NEXT_TELEMETRY_DISABLED=1 npm run build

# Copy built frontend to backend static files
echo "📋 Copying frontend build to backend..."
cd ..
mkdir -p backend/static

# Ensure data directories exist for runtime
echo "📁 Creating data directories..."
mkdir -p backend/data/sqlite
mkdir -p backend/data/swarm_tasks

echo ""
echo "✅ Build complete!"
echo "   Backend: Ready"
echo "   Frontend: Built and copied to backend/static"
echo "   Data directories: Created"
echo ""
echo "⚠️  IMPORTANT: Make sure NEXT_PUBLIC_WS_URL is set in Render dashboard"
echo "   Example: wss://your-backend.onrender.com"