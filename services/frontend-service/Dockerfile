# Stage 1: Build React SPA
FROM node:20 AS frontend-build

WORKDIR /web

# Copy package files
COPY app/web/package.json app/web/package-lock.json* ./

# Install dependencies
RUN npm ci || npm install

# Copy source code
COPY app/web/ ./

# Build the React app
RUN npm run build

# Stage 2: FastAPI proxy + serve built SPA
FROM python:3.13-slim

WORKDIR /app

# Install curl for healthchecks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies directly with uv pip
RUN uv venv && \
    uv pip install fastapi==0.119.1 uvicorn[standard]==0.34.0 pydantic==2.10.6 pydantic-settings==2.11.0 google-auth==2.42.0 requests==2.32.5 httpx==0.28.1 sse-starlette==3.0.2

# Copy FastAPI proxy code
COPY app/main.py ./main.py

# Copy built React SPA from stage 1
COPY --from=frontend-build /web/dist ./static

# Expose port
EXPOSE 8080

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Run with uvicorn from the virtual environment (use absolute path)
CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
