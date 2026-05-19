"""Mail receiving health checks for email domains.

This module performs DNS and WHOIS probes to assess whether a domain is
configured to accept inbound mail. Checks cover MX record presence, null-MX
detection (RFC 7505), RFC 5321 MX target validity (no IP literals, no CNAMEs),
MX resolution, multiple-MX resilience, SPF and DMARC presence, and domain
expiry.

The public entry point is :func:`check_mail_health`, which returns a
structured :class:`~mailpulse.schemas.mail_health.MailHealthResponse`.
"""

import ipaddress
from datetime import UTC, datetime

import dns.exception
import dns.resolver
import whois

from mailpulse.schemas.mail_health import (
    HealthStatus,
    MailHealthCheck,
    MailHealthResponse,
)

DNS_TIMEOUT_SECONDS = 5
WHOIS_TIMEOUT_SECONDS = 5
DOMAIN_EXPIRY_WARN_DAYS = 30


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


def _is_null_mx(rows: list[tuple[int, str]]) -> bool:
    """Return True if the MX RRset is an RFC 7505 null MX (preference 0, ".").

    Args:
        rows: Sorted list of ``(preference, host)`` tuples from
            :func:`_resolve_mx`.

    Returns:
        ``True`` when the RRset consists of exactly one record with
        preference ``0`` and an empty exchange (the trailing dot is
        stripped by :func:`_normalize_mx_exchange`).
    """
    return len(rows) == 1 and rows[0] == (0, "")


def _is_ip_literal(host: str) -> bool:
    """Return True if *host* is an IP address rather than a hostname.

    RFC 5321 §5.1 forbids IP address literals as MX exchange targets.

    Args:
        host: MX exchange hostname string to check.

    Returns:
        ``True`` when ``host`` parses as a valid IPv4 or IPv6 address.
    """
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _resolve_txt(name: str) -> list[str]:
    """Look up TXT records for *name*.

    Each DNS TXT record may consist of multiple strings; this function joins
    them into a single string per record.

    Args:
        name: DNS name to query (for example ``example.com`` or
            ``_dmarc.example.com``).

    Returns:
        A list of decoded TXT record strings. Returns an empty list on any
        DNS failure.
    """
    resolver = dns.resolver.Resolver()
    resolver.timeout = DNS_TIMEOUT_SECONDS
    resolver.lifetime = DNS_TIMEOUT_SECONDS
    try:
        answers = resolver.resolve(name, "TXT")
    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
    ):
        return []
    result: list[str] = []
    for rdata in answers:
        joined = b"".join(rdata.strings).decode("utf-8", errors="replace")
        result.append(joined)
    return result


def _resolve_cname(host: str) -> str | None:
    """Look up a CNAME record for *host*.

    An explicit CNAME query is used rather than relying on dnspython's
    implicit following, so that a CNAME at an MX target can be detected
    as the RFC 5321 §5.1 violation it is.

    Args:
        host: Hostname to query for a CNAME.

    Returns:
        The CNAME target with any trailing dot stripped, or ``None`` if no
        CNAME exists or the lookup fails.
    """
    resolver = dns.resolver.Resolver()
    resolver.timeout = DNS_TIMEOUT_SECONDS
    resolver.lifetime = DNS_TIMEOUT_SECONDS
    try:
        answers = resolver.resolve(host, "CNAME")
    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
    ):
        return None
    for rdata in answers:
        target = rdata.target.to_text()
        if target.endswith("."):
            target = target[:-1]
        return target
    return None


def _resolve_domain_expiry(domain: str) -> datetime | None:
    """Return the domain's WHOIS expiry date, or None if unavailable.

    WHOIS coverage varies by TLD and shared servers rate-limit; any
    failure or unparseable response returns ``None`` so the caller can
    omit the check rather than falsely report expiry.

    Args:
        domain: Registered domain name to look up (for example
            ``example.com``).

    Returns:
        The earliest expiry ``datetime`` found, or ``None`` if the lookup
        fails or returns no expiry.
    """
    try:
        info = whois.whois(domain)
        expiry = info.expiration_date
        if expiry is None:
            return None
        if isinstance(expiry, list):
            dates = [d for d in expiry if isinstance(d, datetime)]
            if not dates:
                return None
            return min(dates)
        if isinstance(expiry, datetime):
            return expiry
        return None
    except Exception:
        return None


def check_mail_health(domain: str) -> MailHealthResponse:
    """Assess whether mail can likely be received for a domain.

    Runs a suite of DNS and WHOIS checks in sequence. Each check is
    emitted only when its prerequisites have passed. Checks whose data
    cannot be obtained (e.g. WHOIS unreachable) are omitted from the
    response rather than emitted as failed.

    Checks performed (in order):

    - ``mx_records_found`` — MX RRset exists.
    - ``not_null_mx`` — Not an RFC 7505 null MX.
    - ``mx_not_ip_literal`` — Top MX exchange is a hostname, not an IP.
    - ``mx_not_cname`` — Top MX exchange is not a CNAME.
    - ``mx_resolves`` — Top MX exchange resolves to an IP.
    - ``multiple_mx_records`` — More than one MX record exists.
    - ``spf_record_present`` — A ``v=spf1`` TXT record exists at the apex.
    - ``dmarc_record_present`` — A ``v=DMARC1`` TXT record exists at
      ``_dmarc.<domain>``.
    - ``domain_not_expiring_soon`` — Domain expiry is not within
      :data:`DOMAIN_EXPIRY_WARN_DAYS` days (omitted when WHOIS is
      unavailable).

    Args:
        domain: Validated, lowercased domain name to evaluate (e.g.
            ``example.com``). Use :func:`~mailpulse.core.helper.resolve_domain_input`
            to obtain this value from caller input.

    Returns:
        A :class:`~mailpulse.schemas.mail_health.MailHealthResponse` with
        a ``status`` of ``"healthy"`` or ``"unhealthy"`` and a list of
        per-check results.
    """
    checks: list[MailHealthCheck] = []

    mx_rows = _resolve_mx(domain)
    if not mx_rows:
        checks.append(
            MailHealthCheck(
                name="mx_records_found",
                passed=False,
                detail="No MX records found",
            )
        )
        return MailHealthResponse(
            domain=domain,
            status=HealthStatus.UNHEALTHY,
            checks=checks,
        )

    checks.append(MailHealthCheck(name="mx_records_found", passed=True))

    if _is_null_mx(mx_rows):
        checks.append(
            MailHealthCheck(
                name="not_null_mx",
                passed=False,
                detail="Domain advertises a null MX (RFC 7505): explicitly refusing mail.",
            )
        )
        return MailHealthResponse(
            domain=domain,
            status=HealthStatus.UNHEALTHY,
            checks=checks,
        )

    checks.append(MailHealthCheck(name="not_null_mx", passed=True))

    _preference, mx_host = mx_rows[0]
    critical_failed = False

    if _is_ip_literal(mx_host):
        checks.append(
            MailHealthCheck(
                name="mx_not_ip_literal",
                passed=False,
                detail=(
                    f"Top MX target is an IP literal ({mx_host}); "
                    "RFC 5321 §5.1 forbids IP addresses in MX exchanges."
                ),
            )
        )
        critical_failed = True
    else:
        checks.append(MailHealthCheck(name="mx_not_ip_literal", passed=True))

        cname_target = _resolve_cname(mx_host)
        if cname_target is not None:
            checks.append(
                MailHealthCheck(
                    name="mx_not_cname",
                    passed=False,
                    detail=(
                        f"Top MX target {mx_host} is a CNAME to {cname_target}; "
                        "RFC 5321 §5.1 forbids CNAMEs as MX exchanges."
                    ),
                )
            )
            critical_failed = True
        else:
            checks.append(MailHealthCheck(name="mx_not_cname", passed=True))

    if critical_failed:
        status = HealthStatus.UNHEALTHY
    else:
        ip_address = _resolve_ip_for_mx_host(mx_host)
        if not ip_address:
            checks.append(
                MailHealthCheck(
                    name="mx_resolves",
                    passed=False,
                    detail="Highest-priority MX did not resolve",
                )
            )
            critical_failed = True
        else:
            checks.append(
                MailHealthCheck(
                    name="mx_resolves",
                    passed=True,
                    detail=f"{mx_host} resolved to {ip_address}",
                )
            )

    if len(mx_rows) == 1:
        checks.append(
            MailHealthCheck(
                name="multiple_mx_records",
                passed=False,
                detail="Only one MX record; mail flow has no failover.",
            )
        )
    else:
        checks.append(
            MailHealthCheck(
                name="multiple_mx_records",
                passed=True,
                detail=f"{len(mx_rows)} MX records found",
            )
        )

    txt_records = _resolve_txt(domain)
    spf_present = any(r.lower().startswith("v=spf1") for r in txt_records)
    if spf_present:
        checks.append(MailHealthCheck(name="spf_record_present", passed=True))
    else:
        checks.append(
            MailHealthCheck(
                name="spf_record_present",
                passed=False,
                detail=f"No SPF (v=spf1) TXT record at apex of {domain}.",
            )
        )

    dmarc_records = _resolve_txt(f"_dmarc.{domain}")
    dmarc_present = any(r.upper().startswith("V=DMARC1") for r in dmarc_records)
    if dmarc_present:
        checks.append(MailHealthCheck(name="dmarc_record_present", passed=True))
    else:
        checks.append(
            MailHealthCheck(
                name="dmarc_record_present",
                passed=False,
                detail=f"No DMARC TXT record at _dmarc.{domain}.",
            )
        )

    expiry = _resolve_domain_expiry(domain)
    if expiry is not None:
        now = datetime.now(tz=UTC)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        days_remaining = (expiry - now).days
        expiry_str = expiry.strftime("%Y-%m-%d")
        if days_remaining < 0:
            checks.append(
                MailHealthCheck(
                    name="domain_not_expiring_soon",
                    passed=False,
                    detail=f"Domain registration expired on {expiry_str}.",
                )
            )
        elif days_remaining <= DOMAIN_EXPIRY_WARN_DAYS:
            checks.append(
                MailHealthCheck(
                    name="domain_not_expiring_soon",
                    passed=False,
                    detail=f"Domain expires in {days_remaining} days ({expiry_str}).",
                )
            )
        else:
            checks.append(
                MailHealthCheck(
                    name="domain_not_expiring_soon",
                    passed=True,
                    detail=f"Domain expires on {expiry_str}.",
                )
            )

    all_passed = all(c.passed for c in checks)
    if all_passed:
        status = HealthStatus.HEALTHY
    else:
        status = HealthStatus.UNHEALTHY

    return MailHealthResponse(
        domain=domain,
        status=status,
        checks=checks,
    )
