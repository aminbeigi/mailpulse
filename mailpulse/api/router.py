from fastapi import APIRouter

from mailpulse.api.routes import health, mail_health

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(mail_health.router)
