# Multi-stage Dockerfile for KPI Operations Platform

# Stage 1: Build stage
# Production: pin to @sha256: digest from docker.io for reproducible builds
# docker pull python:3.11.11-slim-bookworm && docker inspect --format='{{index .RepoDigests 0}}' python:3.11.11-slim-bookworm
FROM python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5 as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the hash-pinned lock first for layer caching
COPY backend/requirements.lock ./backend/

# Install Python dependencies — hash-verified, wheels-only (reproducible, tamper-resistant)
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: --prefix=/usr/local -r backend/requirements.lock

# Stage 2: Production stage (same base as builder for consistency)
# Production: pin to @sha256: digest from docker.io for reproducible builds
FROM python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5 as production

LABEL maintainer="KPI Operations Team"
LABEL version="1.1.0"
LABEL description="KPI Operations Platform - FastAPI Backend"

WORKDIR /app

# Install runtime dependencies (curl for healthcheck, minizinc for the
# SimPy V2 optimization layer — Pattern 1+ uses MZ models executed via
# subprocess from `backend/simulation_v2/optimization/`).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    minizinc \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
# -m creates /home/kpiuser. Without it, useradd -r makes a system user with no
# home while still setting HOME=/home/kpiuser, so gunicorn 26's control server
# fails to initialise there and logs
#   [ERROR] Control server error: [Errno 13] Permission denied: '/home/kpiuser'
# on every boot. Nothing uses that control interface, so the error is harmless in
# itself -- but a permanent ERROR line in production logs is how people learn to
# skim past ERROR lines, and the next one might matter.
RUN groupadd -r kpiuser && useradd -r -m -g kpiuser kpiuser

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

# Default command - start uvicorn server.
# --forwarded-allow-ips '*': this CMD is also Render's actual container
# entrypoint (Render terminates TLS at its edge and proxies to the container
# over its own internal network — the container is never reachable except
# through that edge) and, unmodified, the same CMD docker-compose.yml (local
# dev) runs directly. Without trusting X-Forwarded-Proto, uvicorn's default
# forwarded_allow_ips ("127.0.0.1" only) ignores it from any real proxy peer,
# so redirect_slashes Location headers report scheme="http" even behind
# HTTPS — the scheme-downgraded-redirect bug (ISSUE-012). --proxy-headers is
# uvicorn's default already; named explicitly here for clarity alongside the
# trust-list change. (The VM compose stack overrides this CMD with gunicorn +
# the equivalent --forwarded-allow-ips — see docker-compose.prod.yml.)
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
