FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY mailpulse ./mailpulse

RUN uv sync --frozen --no-dev

ENV MAILPULSE_HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "mailpulse"]
