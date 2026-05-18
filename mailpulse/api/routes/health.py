"""Liveness route for process and load-balancer health checks.

Exposes GET ``/api/v1/health`` with a minimal JSON payload.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Report that the API process is running.

    Returns:
        A mapping with ``status`` set to ``ok``.
    """
    return {"status": "ok"}
