# ============================================================================
# ModelServe — FastAPI Inference Service Dockerfile
# ============================================================================
# TODO: Implement a multi-stage Docker build.
#
# Requirements:
#   - Multi-stage build (at least two FROM statements)
#   - Final image must be under 800 MB
#   - Must run as a non-root user
#   - Must use a production WSGI/ASGI server (gunicorn with uvicorn workers)
#   - Must include a HEALTHCHECK directive
#   - Must copy only what's needed (use .dockerignore too)
#
# Suggested stages:
#   Stage 1 (builder):
#     - Start from python:3.10-slim
#     - Install build dependencies (gcc, etc.)
#     - Copy requirements.txt and install Python packages
#
#   Stage 2 (runtime):
#     - Start from python:3.10-slim (clean)
#     - Copy installed packages from builder stage
#     - Copy application code
#     - Create a non-root user and switch to it
#     - Expose the service port
#     - Set the healthcheck
#     - Define the CMD with gunicorn/uvicorn
# ============================================================================

# ─────────────────────────────────────────────────────────────
#  Stage 1 — builder
#  Installs all Python packages including compiled ones (gcc needed)
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ─────────────────────────────────────────────────────────────
#  Stage 2 — runtime
#  Clean image — only installed packages + app code
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# runtime system deps only (libpq for psycopg2, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
  && rm -rf /var/lib/apt/lists/*

# copy installed python packages from builder
COPY --from=builder /install /usr/local

# copy application code
COPY app/         ./app/
COPY feast_repo/  ./feast_repo/

# create non-root user
RUN useradd --no-create-home --shell /bin/false appuser \
 && chown -R appuser:appuser /app \
 && chmod -R 777 /app/feast_repo

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# gunicorn with uvicorn workers — production ASGI server
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]