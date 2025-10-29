# Multi-stage build for discovery service
FROM python:3.13-slim AS builder

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies with increased timeout
ENV UV_HTTP_TIMEOUT=120
RUN uv pip install --system --no-cache-dir -r pyproject.toml

# Runtime stage
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code and configuration
COPY app/ ./app/

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Run application (PORT env var is set by Cloud Run)
CMD python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
