"""Pydantic schemas for service health endpoints.

Defines the response model returned by the lightweight liveness endpoint.
"""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response returned by the API liveness endpoint."""

    status: Literal["ok"] = Field(
        description="Liveness status for the API process.",
        examples=["ok"],
    )
