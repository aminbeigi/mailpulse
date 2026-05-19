"""Route handler for GET /api/v1/mail-health.

Accepts either an ``email`` or a ``domain`` query parameter (mutually
exclusive) and delegates to :func:`~mailpulse.services.mail_health.check_mail_health`.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from mailpulse.core.helper import resolve_domain_input
from mailpulse.schemas.mail_health import MailHealthResponse
from mailpulse.services.mail_health import check_mail_health

MAIL_HEALTH_EXAMPLE = {
    "domain": "example.com",
    "status": "healthy",
    "checks": [
        {
            "name": "mx_records_found",
            "passed": True,
            "detail": "MX records found: 10 mx1.example.com, 20 mx2.example.com",
        },
        {
            "name": "not_null_mx",
            "passed": True,
            "detail": "Domain does not publish a null MX record",
        },
        {
            "name": "mx_not_ip_literal",
            "passed": True,
            "detail": "Top MX target mx1.example.com is a hostname",
        },
        {
            "name": "mx_not_cname",
            "passed": True,
            "detail": "Top MX target mx1.example.com is not a CNAME",
        },
        {
            "name": "mx_resolves",
            "passed": True,
            "detail": "Top MX target mx1.example.com resolved to 203.0.113.10",
        },
        {
            "name": "multiple_mx_records",
            "passed": True,
            "detail": "Multiple MX records found for failover",
        },
        {
            "name": "spf_record_present",
            "passed": True,
            "detail": "SPF record found",
        },
        {
            "name": "dmarc_record_present",
            "passed": True,
            "detail": "DMARC record found",
        },
        {
            "name": "domain_not_expiring_soon",
            "passed": True,
            "detail": "Domain expiry is more than 30 days away",
        },
    ],
}

router = APIRouter(tags=["Mail Health"])


def _get_domain(email: str | None, domain: str | None) -> str:
    """Resolve query inputs to a normalised domain or raise HTTP 422.

    Args:
        email: Email address whose domain should be extracted.
        domain: Bare domain name to validate and normalise.

    Returns:
        Lowercased, normalised domain string.

    Raises:
        HTTPException: 422 if the inputs fail :func:`~mailpulse.core.domains.resolve_domain_input`.
    """
    try:
        return resolve_domain_input(email=email, domain=domain)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/mail-health",
    response_model=MailHealthResponse,
    summary="Check inbound mail configuration",
    description=(
        "Inspect a domain's inbound mail readiness using DNS and WHOIS data. "
        "Provide exactly one query parameter: `email` to extract the domain from "
        "an address, or `domain` to check a bare domain directly.\n\n"
        "MailPulse checks MX presence, null-MX declarations, MX target validity, "
        "MX resolution, multiple-MX failover, SPF, DMARC, and domain expiry. "
        "WHOIS-backed expiry checks may be omitted when registry data is "
        "unavailable."
    ),
    response_description="Mail-health verdict and ordered check results for the domain.",
    responses={
        200: {
            "description": (
                "The domain was evaluated. The `status` field is `healthy` only "
                "when every emitted check passed."
            ),
            "content": {
                "application/json": {
                    "example": MAIL_HEALTH_EXAMPLE,
                },
            },
        },
        422: {
            "description": (
                "Invalid input. Provide exactly one non-empty `email` or `domain` "
                "query parameter, and ensure the value contains a valid domain."
            ),
        },
    },
)
async def get_mail_health(
    email: str | None = Query(
        default=None,
        min_length=1,
        description=(
            "Email address whose domain should be checked. Use this when a monitor "
            "or user-facing form naturally collects an email address. Mutually "
            "exclusive with `domain`."
        ),
        examples=["admin@example.com"],
    ),
    domain: str | None = Query(
        default=None,
        min_length=1,
        description=(
            "Bare domain to check directly, such as `example.com`. Mutually exclusive with `email`."
        ),
        examples=["example.com"],
    ),
) -> MailHealthResponse:
    """Return mail-health checks for a domain.

    Exactly one of ``email`` or ``domain`` must be supplied.  When
    ``email`` is given the domain is extracted from the address.  When
    ``domain`` is given it is validated and used directly.

    Args:
        email: Email address whose domain is evaluated.
        domain: Bare domain name to evaluate (e.g. ``example.com``).

    Returns:
        A :class:`~mailpulse.schemas.mail_health.MailHealthResponse`
        describing the health of the domain.

    Raises:
        HTTPException: 422 if both or neither parameters are provided, or
            if the supplied value fails validation.
    """
    resolved_domain = _get_domain(email=email, domain=domain)
    return await run_in_threadpool(check_mail_health, resolved_domain)
