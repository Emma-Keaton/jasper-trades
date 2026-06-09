#!/bin/sh
# Render Build Script - Builds both backend and frontend
# This script runs before the start command

set -e

echo "🔨 Building Jasper Trades (Backend + Frontend)..."

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

# Copy .next static files (for standalone output)
if [ -d "frontend/.next/static" ]; then
    cp -r frontend/.next/static backend/static/
    echo "   Copied .next/static"
fi

# Copy public assets
if [ -d "frontend/public" ]; then
    cp -r frontend/public backend/static/
    echo "   Copied public assets"
fi

# Copy standalone output if it exists (Next.js production build)
if [ -d "frontend/.next/standalone" ]; then
    cp -r frontend/.next/standalone/* backend/static/ 2>/dev/null || true
    echo "   Copied standalone build"
fi

# Copy index.html from exported build if exists
if [ -f "frontend/out/index.html" ]; then
    cp frontend/out/index.html backend/static/ 2>/dev/null || true
fi

echo ""
echo "✅ Build complete!"
echo "   Backend: Ready"
echo "   Frontend: Built and copied to backend/static"
echo ""
echo "⚠️  IMPORTANT: Make sure NEXT_PUBLIC_WS_URL is set in Render dashboard"
echo "   Example: wss://your-backend.onrender.com"