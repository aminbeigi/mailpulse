"""Synchronous mail-receiving health checks (MX, DNS, SMTP EHLO) for an email domain."""

import smtplib
import socket

import dns.exception
import dns.resolver

from mailpulse.schemas.email_health import EmailHealthChecks, EmailHealthResponse

DNS_TIMEOUT_SECONDS = 5
SMTP_TIMEOUT_SECONDS = 10
SMTP_LOCAL_HOSTNAME = "mailpulse.local"


def _parse_domain_from_email(email: str) -> str:
    """Return the domain part of *email* after basic validation.

    Splits on the last ``@``, requires non-empty local and domain parts, and requires
    at least one dot in the domain. Raises ``ValueError`` if validation fails.
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
    """Strip a trailing dot from a DNS MX exchange hostname, if present."""
    if exchange.endswith("."):
        return exchange[:-1]
    return exchange


def _resolve_mx(domain: str) -> list[tuple[int, str]]:
    """Look up MX records for *domain* and return ``(preference, host)`` rows sorted for delivery.

    Rows are ordered by ascending preference, then hostname, so the first row is the
    chosen primary MX. Returns an empty list when lookup fails or there are no MX RRs.
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
    """Resolve *host* to an IPv4 or IPv6 address string, or return ``None`` if none found."""
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


def _probe_smtp_socket(address: str) -> bool:
    """Return whether TCP port 25 on *address* accepts a connection within the SMTP timeout."""
    try:
        sock = socket.create_connection((address, 25), timeout=SMTP_TIMEOUT_SECONDS)
    except OSError:
        return False
    else:
        sock.close()
        return True


def _smtp_ehlo_ok(address: str) -> bool:
    """Return whether an SMTP server at *address*:25 completes EHLO with a 2xx/3xx code."""
    try:
        with smtplib.SMTP(
            host=address,
            port=25,
            timeout=SMTP_TIMEOUT_SECONDS,
            local_hostname=SMTP_LOCAL_HOSTNAME,
        ) as smtp:
            code, _message = smtp.ehlo()
    except OSError:
        return False
    return 200 <= code < 400


def check_email_health(email: str) -> EmailHealthResponse:
    """Run MX, resolution, reachability, and EHLO checks for the domain in *email*.

    Stops at the first failed step; later check flags remain ``False``. Raises
    ``ValueError`` when *email* is not accepted by :func:`_parse_domain_from_email`.
    """
    domain = _parse_domain_from_email(email)

    mx_records_found = False
    mx_resolves = False
    smtp_reachable = False
    smtp_handshake_ok = False
    reason: str | None = None

    mx_rows = _resolve_mx(domain)
    if not mx_rows:
        checks = EmailHealthChecks(
            mx_records_found=mx_records_found,
            mx_resolves=mx_resolves,
            smtp_reachable=smtp_reachable,
            smtp_handshake_ok=smtp_handshake_ok,
        )
        return EmailHealthResponse(
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
        checks = EmailHealthChecks(
            mx_records_found=mx_records_found,
            mx_resolves=mx_resolves,
            smtp_reachable=smtp_reachable,
            smtp_handshake_ok=smtp_handshake_ok,
        )
        return EmailHealthResponse(
            domain=domain,
            healthy=False,
            status="unhealthy",
            reason=reason,
            checks=checks,
        )

    mx_resolves = True
    if not _probe_smtp_socket(ip_address):
        reason = "SMTP unreachable on port 25"
        checks = EmailHealthChecks(
            mx_records_found=mx_records_found,
            mx_resolves=mx_resolves,
            smtp_reachable=smtp_reachable,
            smtp_handshake_ok=smtp_handshake_ok,
        )
        return EmailHealthResponse(
            domain=domain,
            healthy=False,
            status="unhealthy",
            reason=reason,
            checks=checks,
        )

    smtp_reachable = True
    if not _smtp_ehlo_ok(ip_address):
        reason = "SMTP did not respond to EHLO"
        checks = EmailHealthChecks(
            mx_records_found=mx_records_found,
            mx_resolves=mx_resolves,
            smtp_reachable=smtp_reachable,
            smtp_handshake_ok=smtp_handshake_ok,
        )
        return EmailHealthResponse(
            domain=domain,
            healthy=False,
            status="unhealthy",
            reason=reason,
            checks=checks,
        )

    smtp_handshake_ok = True
    checks = EmailHealthChecks(
        mx_records_found=mx_records_found,
        mx_resolves=mx_resolves,
        smtp_reachable=smtp_reachable,
        smtp_handshake_ok=smtp_handshake_ok,
    )
    return EmailHealthResponse(
        domain=domain,
        healthy=True,
        status="healthy",
        reason=None,
        checks=checks,
    )
