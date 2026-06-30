# Kronos Service for Render Free Tier
# CPU-only, 512MB RAM optimized

# Build command
pip install -r requirements.txt

# Start command
uvicorn main:app --host 0.0.0.0 --port $PORT --log-level info