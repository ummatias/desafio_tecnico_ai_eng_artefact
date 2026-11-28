# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.11.26 AS uv

FROM python:3.12-slim-bookworm AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY data ./data
COPY knowledge ./knowledge
COPY fixtures ./fixtures
COPY docs/assumptions.md ./docs/assumptions.md
RUN mkdir -p /app/var && chown app:app /app/var
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
USER app
ENTRYPOINT ["emporio"]
CMD ["chat"]
