# Unified Dockerfile - Backend + Frontend + OpenWA (Monorepo)
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (Python + Node.js + Chromium for OpenWA)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    wget \
    curl \
    gnupg \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    # Chromium dependencies for OpenWA
    && apt-get install -y \
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
    && rm -rf /var/lib/apt/lists/* \
    && chromium --version

# Install Python dependencies
COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install Node.js dependencies for frontend
RUN cd frontend && npm ci

# Build frontend with static export
RUN cd frontend && NEXT_TELEMETRY_DISABLED=1 npm run build

# Copy frontend static export to backend/static
RUN mkdir -p /app/backend/static && \
    cp -r /app/frontend/out/* /app/backend/static/ && \
    echo "Frontend static files copied to backend/static"

# OpenWA for WhatsApp is optional. To enable, install @open-wa/wa-automate in the backend directory.
# RUN cd/backend && npm install @open-wa/wa-automate

# Create data directories
RUN mkdir -p /app/backend/data/sqlite /app/backend/data/logs /app/backend/data/models

# Expose port (use PORT env variable from Render)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --spider -q http://localhost:8080/api/v1/health || exit 1

# Set working directory to backend
WORKDIR /app/backend

# Run application with automatic migrations and start server
# Migrations run automatically on app startup via lifespan event
CMD ["sh", "-c", "echo '🚀 Starting Jasper Trades with automatic migrations...' && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]