FROM python:3.15.2-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PYTHON_DOWNLOADS=never TZ=Europe/Moscow
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git libpq5 tzdata && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev
COPY . .
RUN mkdir -p logs
CMD ["sh", "-c", "uv run --frozen alembic upgrade head && uv run --frozen python scripts/init_db.py && uv run --frozen python -m bot"]
