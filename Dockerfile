# =============================================================================
# Library Bus Project - Multi-Stage Production Dockerfile (Non-Root Hardened)
# =============================================================================

# --- Stage 1: Builder ---
FROM python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Final Runtime ---
FROM python:3.11-slim AS final

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/install/bin:$PATH \
    PYTHONPATH=/install/lib/python3.11/site-packages:$PYTHONPATH \
    DJANGO_SETTINGS_MODULE=library_bus_project.settings

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    libjpeg62-turbo \
    zlib1g \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -u 1000 -m -s /bin/bash appuser

# Copy installed dependencies from builder
COPY --from=builder /install /install

# Copy application source code
COPY --chown=appuser:appuser library_bus_project/ /app/

# Ensure logs, media, static directories exist and are owned by appuser
RUN mkdir -p /app/logs /app/media /app/staticfiles \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Default command: Run Gunicorn WSGI server
CMD ["gunicorn", "library_bus_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--timeout", "60"]
