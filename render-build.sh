#!/bin/bash
# Render Build Script - Backend Only (Frontend on Vercel)
# This script runs before the start command

set -e

echo "🔨 Building Jasper Trades Backend..."

# Install backend dependencies
echo "📦 Installing Python dependencies..."
pip install -r backend/requirements.txt

# Install OpenWA for WhatsApp notifications
echo "💬 Installing OpenWA for WhatsApp..."
cd backend
npm init -y
npm install @open-wa/wa-automate
cd ..

# Create empty static folder (frontend served on Vercel)
echo "📁 Creating static folder (backend-only mode)..."
mkdir -p backend/static
echo "Backend-only mode - frontend served on Vercel" > backend/static/index.html

# Ensure data directories exist for runtime
echo "📁 Creating data directories..."
mkdir -p backend/data/sqlite
mkdir -p backend/data/swarm_tasks
mkdir -p backend/data/openwa-session

echo ""
echo "✅ Build complete!"
echo "   Backend: Ready"
echo "   Frontend: Deployed separately on Vercel"
echo "   OpenWA: Installed"
echo "   Data directories: Created"