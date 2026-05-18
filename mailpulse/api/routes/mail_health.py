"""Route handler for GET /api/v1/mail-health.

Accepts either an ``email`` or a ``domain`` query parameter (mutually
exclusive) and delegates to :func:`~mailpulse.services.mail_health.check_mail_health`.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from mailpulse.core.domains import parse_domain_from_email, validate_domain
from mailpulse.schemas.mail_health import MailHealthResponse
from mailpulse.services.mail_health import check_mail_health

router = APIRouter(tags=["mail-health"])


@router.get("/mail-health", response_model=MailHealthResponse)
async def get_mail_health(
    email: str | None = Query(default=None, min_length=1),
    domain: str | None = Query(default=None, min_length=1),
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
    if email is not None and domain is not None:
        raise HTTPException(
            status_code=422,
            detail="Provide either 'email' or 'domain', not both.",
        )
    if email is None and domain is None:
        raise HTTPException(
            status_code=422,
            detail="Provide either 'email' or 'domain'.",
        )
    try:
        if email is not None:
            resolved_domain = parse_domain_from_email(email)
        else:
            resolved_domain = validate_domain(domain)  # type: ignore[arg-type]
        return await run_in_threadpool(check_mail_health, resolved_domain)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
