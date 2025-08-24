FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Install Python dependencies
COPY --chown=app:app requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Add user's pip bin to PATH
ENV PATH=/home/app/.local/bin:$PATH

# Copy application code
COPY --chown=app:app app ./app
COPY --chown=app:app data ./data

# Create directories with proper permissions
USER root
RUN mkdir -p /app/uploads /app/data && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE $PORT

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT


