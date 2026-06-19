#!/bin/bash
# Render Build Script - Backend with OpenWA (WhatsApp)
# This script runs during Render build phase

set -e

echo "============================================"
echo "  Building Jasper Trades Backend + OpenWA"
echo "============================================"
echo ""

# Install Python dependencies
echo "[1/4] Installing Python dependencies..."
pip install -r backend/requirements.txt
echo "✅ Python dependencies installed"
echo ""

# Install Node.js (if not already available)
echo "[2/4] Checking Node.js installation..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found! Render should provide Node.js..."
    echo "Installing Node.js 20.x..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi
node --version
npm --version
echo "✅ Node.js ready"
echo ""

# Install OpenWA with proper error handling
echo "[3/4] Installing OpenWA (WhatsApp API)..."
cd backend

# Create package.json if it doesn't exist
if [ ! -f package.json ]; then
    echo "Creating package.json..."
    npm init -y
fi

# Install OpenWA with legacy peer deps to avoid conflicts
echo "Installing @open-wa/wa-automate (this may take 2-3 minutes)..."
npm install @open-wa/wa-automate --legacy-peer-deps --no-audit --no-fund

# Verify installation
if [ -d "node_modules/@open-wa/wa-automate" ]; then
    echo "✅ OpenWA installed successfully"
else
    echo "❌ OpenWA installation failed!"
    echo "Contents of node_modules/@open-wa:"
    ls -la node_modules/@open-wa/ 2>/dev/null || echo "Directory not found"
    exit 1
fi

# Install Chromium dependencies for WhatsApp
echo "Installing Chromium dependencies..."
apt-get update
apt-get install -y \
    chromium \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    || echo "⚠️ Some Chromium deps may already be installed"

cd ..
echo "✅ OpenWA + Chromium ready"
echo ""

# Create directories
echo "[4/4] Creating runtime directories..."
mkdir -p backend/static
echo "Backend-only mode" > backend/static/index.html

mkdir -p backend/data/sqlite
mkdir -p backend/data/swarm_tasks
mkdir -p backend/data/openwa-session
mkdir -p backend/data/logs

echo "✅ Directories created"
echo ""

# Verify installation
echo "============================================"
echo "  Installation Summary"
echo "============================================"
echo "Python: $(python --version 2>&1 | head -1)"
echo "Node: $(node --version)"
echo "npm: $(npm --version)"
echo "OpenWA: $(ls -d backend/node_modules/@open-wa/wa-automate 2>/dev/null && echo '✅ Installed' || echo '❌ Missing')"
echo ""
echo "✅ Build complete!"
echo "============================================"