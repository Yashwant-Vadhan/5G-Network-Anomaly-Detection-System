# Multi-stage Dockerfile for 5G-NADS: React SPA + FastAPI Telemetry Gateway (T18-007)
# Non-root execution, minimal attack surface, self-contained single-port deployment

# -----------------------------------------------------------------------------
# Stage 1: Build the React SPA
# -----------------------------------------------------------------------------
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2: Python Runtime with FastAPI backend
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NADS_STATIC_DIR=/app/frontend/dist \
    NADS_ALLOW_LAN=true \
    PORT=8000

WORKDIR /app

# Install curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pinned Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code and necessary pipeline artifacts
COPY ml/ ./ml/
COPY agents/ ./agents/
COPY streaming/ ./streaming/
COPY pipelines/ ./pipelines/
COPY models/ ./models/
COPY data/sample/ ./data/sample/
COPY pyproject.toml ./
COPY agents/ ./agents/
# Copy compiled frontend SPA from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create a non-root system user and set ownership
RUN groupadd -g 10001 nads && \
    useradd -u 10001 -g nads -s /bin/bash -m nads && \
    chown -R nads:nads /app

USER nads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["python", "-m", "streaming.server"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--mode", "public", "--allow-lan"]
