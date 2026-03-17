FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src /app/src
COPY lastwords.py /app/lastwords.py
COPY data /app/data
RUN uv sync --frozen --no-dev

FROM python:3.13-slim-bookworm AS runtime

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["lastwords"]
CMD ["sync"]
