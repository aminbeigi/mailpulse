"""FastAPI application factory for MailPulse.

Exposes :func:`create_app` as the ASGI entry point used by uvicorn and tests.
"""

from fastapi import FastAPI

from mailpulse.api.router import api_router
from mailpulse.core.config import get_settings

_API_DESCRIPTION = "Check whether email domains are configured to receive inbound mail."

_OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": "Lightweight service liveness checks for load balancers and monitors.",
    },
    {
        "name": "Mail Health",
        "description": (
            "DNS and WHOIS based checks that assess whether a domain can likely "
            "receive inbound email."
        ),
    },
]


def create_app() -> FastAPI:
    """Build and configure the MailPulse FastAPI application.

    Returns:
        A FastAPI instance with API routes mounted under ``/api/v1``.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=_API_DESCRIPTION,
        version=settings.version,
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        redoc_url=None,
        openapi_tags=_OPENAPI_TAGS,
        contact={
            "name": "Amin Beigi",
            "url": "https://aminbeigi.com",
        },
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 2,
            "displayRequestDuration": True,
            "docExpansion": "list",
            "tryItOutEnabled": True,
        },
    )

    app.include_router(api_router)

    return app
