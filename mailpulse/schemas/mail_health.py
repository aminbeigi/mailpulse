"""Pydantic schemas for the mail-health endpoint.

Defines the response shape for GET /api/v1/mail-health, including the
per-check model and the top-level response with a binary healthy/unhealthy
status.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class HealthStatus(StrEnum):
    """Overall deliverability verdict for a domain."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class MailHealthCheck(BaseModel):
    """Result of a single mail-health check."""

    name: str = Field(
        description="Stable machine-readable check identifier.",
        examples=["mx_records_found"],
    )
    passed: bool = Field(
        description="Whether this individual check passed.",
        examples=[True],
    )
    detail: str | None = Field(
        default=None,
        description="Human-readable explanation, usually present when a check fails.",
        examples=["MX records found: 10 mx1.example.com, 20 mx2.example.com"],
    )


class MailHealthResponse(BaseModel):
    """Aggregate mail-health response for an email's domain."""

    domain: str = Field(
        description="Normalized domain that was evaluated.",
        examples=["example.com"],
    )
    status: HealthStatus = Field(
        description=(
            "Overall deliverability verdict. `healthy` means every emitted check "
            "passed; `unhealthy` means at least one emitted check failed."
        ),
        examples=[HealthStatus.HEALTHY],
    )
    checks: list[MailHealthCheck] = Field(
        description=(
            "Ordered check results. Some checks are omitted when their prerequisite "
            "data cannot be obtained, such as unavailable WHOIS expiry data."
        ),
    )
