from fastapi import APIRouter

from mailpulse.api.routes import email_health, health

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(email_health.router)
