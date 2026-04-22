FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies for asyncpg and lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install production dependencies (no dev group)
RUN uv sync --frozen --no-dev --no-install-project 2>/dev/null || uv sync --no-dev --no-install-project

# Copy application code
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

ENV PYTHONPATH=/app
# Prevent uv from reading .env files (env vars come from docker-compose)
ENV UV_NO_ENV_FILE=1

EXPOSE 8000

# Run migrations (with retry for DB readiness) then start the server
# Use venv directly instead of `uv run` to avoid .env file interference
CMD ["sh", "-c", "\
  . /app/.venv/bin/activate && \
  echo \"DB target: ${DATABASE_URL##*@}\" && \
  for i in 1 2 3 4 5; do \
    alembic upgrade head && break; \
    echo \"Waiting for database... (attempt $i/5)\"; \
    sleep 3; \
  done && \
  uvicorn app.main:app --host 0.0.0.0 --port 8000"]
