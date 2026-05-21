"""Pydantic schemas for the mail-health endpoint.

Defines the response shape for GET /api/v1/mail-health, including the
per-check model with catalog metadata and the top-level response whose
status reflects critical-check outcomes only.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class HealthStatus(StrEnum):
    """Overall deliverability verdict for a domain."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class CheckSeverity(StrEnum):
    """Severity tier for a mail-health check."""

    CRITICAL = "critical"
    WARNING = "warning"


class MailHealthCheck(BaseModel):
    """Result of a single mail-health check."""

    name: str = Field(
        description="Stable machine-readable check identifier.",
        examples=["mx_records_found"],
    )
    title: str = Field(
        description="Short human-readable check name.",
        examples=["MX records present"],
    )
    description: str = Field(
        description="What this check verifies and why it matters.",
        examples=[
            "Confirms the domain publishes at least one DNS MX record so sending "
            "mail systems know where to deliver inbound mail."
        ],
    )
    reference: str | None = Field(
        default=None,
        description="Relevant RFC or standard, or null when none applies.",
        examples=["RFC 5321"],
    )
    severity: CheckSeverity = Field(
        description=(
            "Impact tier. `critical` failures mark the domain unhealthy; "
            "`warning` failures are reported but do not affect top-level status."
        ),
        examples=[CheckSeverity.CRITICAL],
    )
    passed: bool = Field(
        description="Whether this individual check passed.",
        examples=[True],
    )
    result: str | None = Field(
        default=None,
        description="Per-run detail: what was found or why the check failed.",
        examples=["2 MX record(s): 10 mx1.example.com, 20 mx2.example.com"],
    )


class MailHealthResponse(BaseModel):
    """Aggregate mail-health response for an email's domain."""

    domain: str = Field(
        description="Normalized domain that was evaluated.",
        examples=["example.com"],
    )
    status: HealthStatus = Field(
        description=(
            "Overall deliverability verdict. `healthy` when every emitted check "
            "with severity `critical` has passed; `unhealthy` when any emitted "
            "critical check has failed. Warning failures are included in `checks` "
            "but do not affect this field."
        ),
        examples=[HealthStatus.HEALTHY],
    )
    checks: list[MailHealthCheck] = Field(
        description=(
            "Ordered check results. Critical checks appear first, then warnings. "
            "Some checks are omitted when their prerequisite data cannot be "
            "obtained, such as unavailable WHOIS expiry data."
        ),
    )
