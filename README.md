# MailPulse

MailPulse is a backend tool that checks whether your **mail server** and domain are set up so incoming mail can be delivered (MX records, DNS, and basic SMTP checks).

It came out of a real incident: my mail server failed without me noticing. For several days, messages to my domain were not delivered, and I missed important email.

MailPulse is meant to surface that kind of failure early, before silent delivery loss drags on.

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

## Tests

Automated tests live in the top-level `tests/` directory (for example `tests/test_health.py`). They use [pytest](https://docs.pytest.org/) together with FastAPI’s test client (via [httpx](https://www.python-httpx.org/)).

Install dev dependencies (including pytest) if you have not already:

```bash
uv sync --group dev
```

Run the full suite:

```bash
uv run pytest
```

Run a single file or test:

```bash
uv run pytest tests/test_health.py
uv run pytest tests/test_health.py::test_health_returns_ok
```

## Docker

Build and run the API in a container (the image sets `MAILPULSE_HOST=0.0.0.0` so the server accepts connections from outside the container):

```bash
docker build -t mailpulse .

docker run --rm -p 8000:8000 mailpulse
```



| Endpoint                 | Description                                      |
| ------------------------ | ------------------------------------------------ |
| `GET /health`            | Health check                                     |
| `GET /v1/mail-health`    | Mail-receiving health for an email’s domain      |
| `GET /docs`              | Swagger UI                                       |


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
│       ├── health.py  # GET /health
│       └── email_health.py  # GET /v1/mail-health
├── core/
│   └── config.py      # Settings via pydantic-settings
├── schemas/           # Pydantic request/response models
│   └── email_health.py
└── services/          # Business logic
    └── email_health.py
tests/
├── test_health.py     # Example API test (GET /health)
└── test_email_health.py  # GET /v1/mail-health
```

