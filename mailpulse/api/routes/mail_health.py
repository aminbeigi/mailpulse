"""Route handler for GET /api/v1/mail-health.

Accepts either an ``email`` or a ``domain`` query parameter (mutually
exclusive) and delegates to :func:`~mailpulse.services.mail_health.check_mail_health`.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from mailpulse.core.helper import resolve_domain_input
from mailpulse.schemas.mail_health import MailHealthResponse
from mailpulse.services.mail_health import check_mail_health

router = APIRouter(tags=["mail-health"])


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
    resolved_domain = _get_domain(email=email, domain=domain)
    return await run_in_threadpool(check_mail_health, resolved_domain)
