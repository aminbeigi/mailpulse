# MailPulse

A modular FastAPI service managed by [uv](https://docs.astral.sh/uv/) and linted/formatted by [ruff](https://docs.astral.sh/ruff/).

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Setup

```bash
# Install dependencies into a managed .venv
uv sync

# Copy the example env file and adjust as needed
cp .env.example .env
```

## Run

```bash
uv run python -m mailpulse
```

The server starts at `http://127.0.0.1:8000` by default.


| Endpoint      | Description  |
| ------------- | ------------ |
| `GET /health` | Health check |
| `GET /docs`   | Swagger UI   |


## Configuration

All settings are read from environment variables (or a `.env` file) with the `MAILPULSE_` prefix:


| Variable             | Default     | Description         |
| -------------------- | ----------- | ------------------- |
| `MAILPULSE_HOST`     | `127.0.0.1` | Bind host           |
| `MAILPULSE_PORT`     | `8000`      | Bind port           |
| `MAILPULSE_RELOAD`   | `false`     | Enable hot-reload   |
| `MAILPULSE_APP_NAME` | `MailPulse` | Application name    |
| `MAILPULSE_VERSION`  | `0.1.0`     | Application version |


## Lint & Format

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

## Pre-commit

```bash
# Install hooks (run once after cloning)
uv run pre-commit install

# Run hooks manually against all files
uv run pre-commit run --all-files
```

## Project structure

```
mailpulse/
├── __init__.py
├── __main__.py        # Entry point: python -m mailpulse
├── app.py             # FastAPI app factory
├── api/
│   ├── router.py      # Aggregates all route modules
│   └── routes/
│       └── health.py  # GET /health
├── core/
│   └── config.py      # Settings via pydantic-settings
├── schemas/           # Pydantic request/response models
└── services/          # Business logic
```

