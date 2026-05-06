# Vacant — minimal container image
#
# Build:
#   docker build -t vacant:dev .
#
# Run a demo:
#   docker run --rm vacant:dev demo law_firm
#
# Serve a vacant on port 8443:
#   docker run --rm -p 8443:8443 -v $PWD/.env:/app/.env vacant:dev serve --host 0.0.0.0 --port 8443
#
# The image bundles uv + the locked dependency set + the project itself,
# launched via the `vacant` console script.

# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install uv via the official Astral image
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

# Layer 1: dependency lock — cached unless lock changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Layer 2: project source
COPY src/ ./src/
COPY architecture/ ./architecture/
COPY README.md LICENSE ./
RUN uv sync --frozen --no-dev

# Non-root user (defense in depth — vacant doesn't need root for anything)
RUN useradd --create-home --shell /bin/bash vacant && \
    chown -R vacant:vacant /app
USER vacant

# `vacant` is the console_script declared in pyproject.toml
ENTRYPOINT ["vacant"]
CMD ["--help"]
