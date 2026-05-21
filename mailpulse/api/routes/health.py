"""Liveness route for process and load-balancer health checks.

Exposes GET ``/api/v1/health`` with a minimal JSON payload.
"""

from fastapi import APIRouter

from mailpulse.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API liveness",
    description="Minimal liveness response for load balancer health checks.",
    response_description="The API process is running.",
    responses={
        200: {
            "description": "MailPulse is running and able to serve HTTP requests.",
            "content": {
                "application/json": {
                    "example": {"status": "ok"},
                },
            },
        },
    },
)
async def health_check() -> HealthResponse:
    """Report that the API process is running.

    Returns:
        A health response with ``status`` set to ``ok``.
    """
    return HealthResponse(status="ok")
