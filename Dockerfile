FROM dhi.io/python:3.13-debian13-sfw-dev AS builder

COPY --from=dhi.io/uv:0.10-debian13 /usr/local/bin/uv /usr/local/bin/uv

WORKDIR /app

ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src /app/src
COPY lastwords.py /app/lastwords.py
COPY data /app/data
RUN uv sync --frozen --no-dev --no-editable

FROM dhi.io/python:3.13-debian13 AS runtime

COPY --from=dhi.io/uv:0.10-debian13 /usr/local/bin/uv /usr/local/bin/uv

WORKDIR /app

ENV UV_CACHE_DIR=/tmp/uv-cache

COPY --from=builder /app /app

ENTRYPOINT ["uv", "run", "--frozen", "--no-dev", "--no-sync", "lastwords"]
CMD ["sync"]
