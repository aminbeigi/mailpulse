"""Aggregate API v1 routes for the MailPulse service.

Mounts health and mail-health routers under the ``/api/v1`` prefix.
"""

from fastapi import APIRouter

from mailpulse.api.routes import health, mail_health

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(mail_health.router)
