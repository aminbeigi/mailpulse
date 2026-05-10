from fastapi import FastAPI

from mailpulse.api.router import api_router
from mailpulse.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
    )

    app.include_router(api_router)

    return app
