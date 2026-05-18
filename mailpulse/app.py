"""FastAPI application factory for MailPulse.

Exposes :func:`create_app` as the ASGI entry point used by uvicorn and tests.
"""

from fastapi import FastAPI

from mailpulse.api.router import api_router
from mailpulse.core.config import get_settings


def create_app() -> FastAPI:
    """Build and configure the MailPulse FastAPI application.

    Returns:
        A FastAPI instance with API routes mounted under ``/api/v1``.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        redoc_url=None,
    )

    app.include_router(api_router)

    return app
