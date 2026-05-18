"""Pydantic schemas for the mail-health endpoint.

Defines the response shape for GET /api/v1/mail-health, including the
per-check model and the top-level response with a binary healthy/unhealthy
status.
"""

from enum import StrEnum

from pydantic import BaseModel


class HealthStatus(StrEnum):
    """Overall deliverability verdict for a domain."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class MailHealthCheck(BaseModel):
    """Result of a single mail-health check."""

    name: str
    passed: bool
    detail: str | None = None


class MailHealthResponse(BaseModel):
    """Aggregate mail-health response for an email's domain."""

    domain: str
    status: HealthStatus
    checks: list[MailHealthCheck]
