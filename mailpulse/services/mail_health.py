"""Mail receiving health checks for email domains.

This module performs synchronous DNS probes to estimate whether a domain is
configured to accept inbound mail: MX record discovery and resolution of the
preferred MX host to an IP address.

The public entry point is :func:`check_mail_health`, which returns a
structured :class:`~mailpulse.schemas.mail_health.MailHealthResponse`.
"""

import dns.exception
import dns.resolver

from mailpulse.schemas.mail_health import MailHealthChecks, MailHealthResponse

DNS_TIMEOUT_SECONDS = 5


def _parse_domain_from_email(email: str) -> str:
    """Extract and validate the domain part of an email address.

    Args:
        email: Email address to parse. Leading and trailing whitespace is
            stripped before validation.

    Returns:
        Lowercased domain part of the email (the portion after the last
        ``@``).

    Raises:
        ValueError: If the address has no ``@``, empty local or domain
            parts, or a domain without at least one dot.
    """
    stripped = email.strip()
    if "@" not in stripped:
        msg = "Invalid email address"
        raise ValueError(msg)
    local_part, domain = stripped.rsplit("@", 1)
    if not local_part or not domain:
        msg = "Invalid email address"
        raise ValueError(msg)
    if "." not in domain:
        msg = "Invalid email address"
        raise ValueError(msg)
    return domain.lower()


def _normalize_mx_exchange(exchange: str) -> str:
    """Normalize an MX exchange hostname from DNS text form.

    Args:
        exchange: MX exchange hostname as returned by DNS (may end with a
            trailing dot denoting the root zone).

    Returns:
        The hostname with a single trailing dot removed, if present;
        otherwise the original string unchanged.
    """
    if exchange.endswith("."):
        return exchange[:-1]
    return exchange


def _resolve_mx(domain: str) -> list[tuple[int, str]]:
    """Resolve MX records for a mail domain.

    Args:
        domain: Mail domain to look up (for example ``example.com``).

    Returns:
        A list of ``(preference, host)`` tuples sorted by ascending
        preference then hostname. The first entry is the highest-priority
        MX. Returns an empty list when lookup fails or no MX records
        exist.
    """
    resolver = dns.resolver.Resolver()
    resolver.timeout = DNS_TIMEOUT_SECONDS
    resolver.lifetime = DNS_TIMEOUT_SECONDS
    try:
        answers = resolver.resolve(domain, "MX")
    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
    ):
        return []

    rows: list[tuple[int, str]] = []
    for rdata in answers:
        preference = int(rdata.preference)
        host = _normalize_mx_exchange(rdata.exchange.to_text())
        rows.append((preference, host))
    rows.sort(key=lambda row: (row[0], row[1]))
    return rows


def _resolve_ip_for_mx_host(host: str) -> str | None:
    """Resolve an MX host to an IP address.

    Tries A records first, then AAAA.

    Args:
        host: MX exchange hostname to resolve.

    Returns:
        The first IPv4 or IPv6 address string found, or ``None`` if
        resolution fails or yields no addresses.
    """
    resolver = dns.resolver.Resolver()
    resolver.timeout = DNS_TIMEOUT_SECONDS
    resolver.lifetime = DNS_TIMEOUT_SECONDS
    for rtype in ("A", "AAAA"):
        try:
            answers = resolver.resolve(host, rtype)
        except (
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.resolver.NoNameservers,
            dns.exception.Timeout,
        ):
            continue
        for rdata in answers:
            return rdata.address
    return None


def check_mail_health(email: str) -> MailHealthResponse:
    """Assess whether mail can likely be received for an email domain.

    Runs MX lookup and A/AAAA resolution for the highest-priority MX host.
    Checks after the first failure are left ``False`` in the response.

    Args:
        email: Email address whose domain is evaluated.

    Returns:
        A :class:`~mailpulse.schemas.mail_health.MailHealthResponse` with
        per-step check flags, overall health status, and an optional
        failure reason.

    Raises:
        ValueError: If ``email`` fails validation in
            :func:`_parse_domain_from_email`.
    """
    domain = _parse_domain_from_email(email)

    mx_records_found = False
    mx_resolves = False
    reason: str | None = None

    mx_rows = _resolve_mx(domain)
    if not mx_rows:
        checks = MailHealthChecks(
            mx_records_found=mx_records_found,
            mx_resolves=mx_resolves,
        )
        return MailHealthResponse(
            domain=domain,
            healthy=False,
            status="unhealthy",
            reason="No MX records found",
            checks=checks,
        )

    mx_records_found = True
    _preference, mx_host = mx_rows[0]
    ip_address = _resolve_ip_for_mx_host(mx_host)
    if not ip_address:
        reason = "Highest-priority MX did not resolve"
        checks = MailHealthChecks(
            mx_records_found=mx_records_found,
            mx_resolves=mx_resolves,
        )
        return MailHealthResponse(
            domain=domain,
            healthy=False,
            status="unhealthy",
            reason=reason,
            checks=checks,
        )

    mx_resolves = True
    checks = MailHealthChecks(
        mx_records_found=mx_records_found,
        mx_resolves=mx_resolves,
    )
    return MailHealthResponse(
        domain=domain,
        healthy=True,
        status="healthy",
        reason=None,
        checks=checks,
    )
