# Multi-stage Dockerfile for KPI Operations Platform

# Stage 1: Build stage
# python:3.11.11-slim-bookworm — pin to digest for reproducible builds:
# docker pull python:3.11.11-slim-bookworm && docker inspect --format='{{index .RepoDigests 0}}' python:3.11.11-slim-bookworm
FROM python:3.11.11-slim-bookworm as builder

LABEL maintainer="KPI Operations Team"
LABEL version="1.0.4"
LABEL description="KPI Operations Platform - FastAPI Backend"

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY backend/requirements.txt ./backend/

# Install Python dependencies
RUN pip install --no-cache-dir --prefix=/usr/local -r backend/requirements.txt

# Stage 2: Production stage (same base as builder for consistency)
FROM python:3.11.11-slim-bookworm as production

WORKDIR /app

# Install runtime dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r kpiuser && useradd -r -g kpiuser kpiuser

# Copy installed packages from builder
COPY --from=builder /usr/local /usr/local

# Copy application code
COPY backend/ ./backend/
COPY database/ ./database/

# Copy entrypoint script
COPY backend/scripts/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Create necessary directories
RUN mkdir -p /app/uploads /app/reports /app/database /app/logs && \
    chown -R kpiuser:kpiuser /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # Feature flags
    CAPACITY_PLANNING_ENABLED=true \
    # Default log level
    LOG_LEVEL=INFO

# Expose port
EXPOSE 8000

# Health check using the /health/live endpoint for liveness
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Run as non-root user
USER kpiuser

# Use entrypoint script for initialization
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command - start uvicorn server
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
