# Unified Dockerfile - Backend + Frontend (Monorepo)
# For split deployment: Backend on Render, Frontend on Vercel
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (Python + Node.js)
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
    && rm -rf /var/lib/apt/lists/* \
    && node --version

# Install Python dependencies
COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /app/backend/data/sqlite /app/backend/data/logs /app/backend/data/models

# Create empty static folder (frontend served separately on Vercel)
RUN mkdir -p /app/backend/static && echo "Backend-only mode - frontend served on Vercel" > /app/backend/static/index.html

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