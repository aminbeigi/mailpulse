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
            "title": "MX records present",
            "description": (
                "Confirms the domain publishes at least one DNS MX record so sending "
                "mail systems know where to deliver inbound mail. Without MX records, "
                "there is no standard inbound route and delivery cannot be attempted "
                "for this domain."
            ),
            "reference": "RFC 5321",
            "severity": "critical",
            "passed": True,
            "result": "2 MX record(s): 10 mx1.example.com, 20 mx2.example.com",
        },
        {
            "name": "not_null_mx",
            "title": "Not a null MX",
            "description": (
                "Confirms the domain does not publish an RFC 7505 null MX "
                "(preference 0 with an empty exchange). A null MX is an explicit "
                "signal that the domain does not accept inbound mail."
            ),
            "reference": "RFC 7505",
            "severity": "critical",
            "passed": True,
            "result": "MX RRset is not null MX; top target: 10 mx1.example.com",
        },
        {
            "name": "mx_not_ip_literal",
            "title": "MX target is a hostname",
            "description": (
                "Confirms the highest-priority MX exchange is a hostname, not an "
                "IPv4/IPv6 literal. RFC 5321 requires MX targets to be domain names."
            ),
            "reference": "RFC 5321 §5.1",
            "severity": "critical",
            "passed": True,
            "result": "Top MX target mx1.example.com is a hostname (not an IP literal)",
        },
        {
            "name": "mx_not_cname",
            "title": "MX target is not a CNAME",
            "description": (
                "Confirms the highest-priority MX exchange is not a CNAME alias. "
                "MX records must point to hostnames that resolve directly."
            ),
            "reference": "RFC 5321 §5.1",
            "severity": "critical",
            "passed": True,
            "result": "Top MX target mx1.example.com is not a CNAME",
        },
        {
            "name": "mx_resolves",
            "title": "Top MX resolves",
            "description": (
                "Confirms the highest-priority MX hostname resolves to at least one "
                "IP address (A or AAAA). If the MX host does not resolve, sending "
                "MTAs cannot connect."
            ),
            "reference": "RFC 5321",
            "severity": "critical",
            "passed": True,
            "result": "mx1.example.com resolved to 203.0.113.10",
        },
        {
            "name": "multiple_mx_records",
            "title": "Multiple MX records",
            "description": (
                "Checks for more than one MX record so mail can fail over if a "
                "primary host is unavailable."
            ),
            "reference": None,
            "severity": "warning",
            "passed": True,
            "result": "2 MX records: 10 mx1.example.com, 20 mx2.example.com",
        },
        {
            "name": "spf_record_present",
            "title": "SPF record at apex",
            "description": (
                "Checks for a TXT record at the domain apex beginning with v=spf1. "
                "SPF defines which hosts may send mail using this domain name."
            ),
            "reference": "RFC 7208",
            "severity": "warning",
            "passed": True,
            "result": "SPF present: v=spf1 include:_spf.example.com ~all",
        },
        {
            "name": "dmarc_record_present",
            "title": "DMARC record published",
            "description": (
                "Checks for a TXT record at _dmarc.example.com beginning with "
                "v=DMARC1. DMARC tells receivers how to handle mail that fails "
                "SPF/DKIM alignment."
            ),
            "reference": "RFC 7489",
            "severity": "warning",
            "passed": True,
            "result": "DMARC present: v=DMARC1; p=reject; rua=mailto:dmarc@example.com",
        },
        {
            "name": "domain_not_expiring_soon",
            "title": "Domain registration not expiring soon",
            "description": (
                "Uses WHOIS to see whether the domain registration is expired or "
                "expiring within 30 days. Omitted when WHOIS data is unavailable."
            ),
            "reference": None,
            "severity": "warning",
            "passed": True,
            "result": "Registration valid; expires 2026-12-31 (224 days remaining)",
        },
    ],
}

router = APIRouter(tags=["Mail Health"])


@router.get(
    "/mail-health",
    response_model=MailHealthResponse,
    summary="Check inbound mail configuration",
    description=(
        "Inspect a domain's inbound mail readiness using DNS and WHOIS data. "
        "Provide exactly one query parameter: `email` to extract the domain from "
        "an address, or `domain` to check a bare domain directly.\n\n"
        "Each check has a `severity` of `critical` or `warning`. The top-level "
        "`status` is `healthy` only when every emitted critical check passes; "
        "warning failures are reported in `checks` but do not affect `status`. "
        "WHOIS-backed expiry checks may be omitted when registry data is unavailable."
    ),
    response_description="Mail-health verdict and ordered check results for the domain.",
    responses={
        200: {
            "description": (
                "The domain was evaluated. `status` is `healthy` when every emitted "
                "critical check passed; `unhealthy` when any critical check failed. "
                "Warning failures are included in `checks` but do not affect `status`."
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

    Exactly one of ``email`` or ``domain`` must be supplied. When
    ``email`` is given the domain is extracted from the address. When
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
    try:
        resolved_domain = resolve_domain_input(email=email, domain=domain)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await run_in_threadpool(check_mail_health, resolved_domain)
