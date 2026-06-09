# Unified Dockerfile - Backend + Frontend + OpenWA (Monorepo)
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (Python + Node.js for OpenWA)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    wget \
    curl \
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
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies for frontend and OpenWA
COPY frontend/package.json frontend/package-lock.json* /app/frontend/
RUN cd frontend && npm ci

# Install OpenWA for WhatsApp
RUN npm install -g @open-wa/wa-automate

# Copy application code
COPY . .

# Build frontend with static export
RUN cd frontend && NEXT_TELEMETRY_DISABLED=1 npm run build

# Copy frontend static export to backend/static
RUN mkdir -p /app/backend/static && \
    cp -r /app/frontend/out/* /app/backend/static/ && \
    echo "Frontend static files copied to backend/static"

# Create data directories
RUN mkdir -p /app/backend/data/sqlite /app/backend/data/logs /app/backend/data/models

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --spider -q http://localhost:8000/api/v1/health || exit 1

# Set working directory to backend
WORKDIR /app/backend

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]