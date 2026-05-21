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
    CheckSeverity,
    HealthStatus,
    MailHealthCheck,
    MailHealthResponse,
)
from mailpulse.services.mail_health_catalog import make_check

_DNS_TIMEOUT_SECONDS = 5
_WHOIS_TIMEOUT_SECONDS = 5
_DOMAIN_EXPIRY_WARN_DAYS = 30
_SPF_DMARC_TRUNCATE_CHARS = 120


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
    resolver.timeout = _DNS_TIMEOUT_SECONDS
    resolver.lifetime = _DNS_TIMEOUT_SECONDS
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
    resolver.timeout = _DNS_TIMEOUT_SECONDS
    resolver.lifetime = _DNS_TIMEOUT_SECONDS
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
    resolver.timeout = _DNS_TIMEOUT_SECONDS
    resolver.lifetime = _DNS_TIMEOUT_SECONDS
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
    resolver.timeout = _DNS_TIMEOUT_SECONDS
    resolver.lifetime = _DNS_TIMEOUT_SECONDS
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


def _format_mx_list(rows: list[tuple[int, str]]) -> str:
    """Format MX rows as a comma-separated preference/host string.

    Args:
        rows: Sorted list of ``(preference, host)`` tuples.

    Returns:
        A string like ``"10 mx1.example.com, 20 mx2.example.com"``.
    """
    return ", ".join(f"{pref} {host}" for pref, host in rows)


def _truncate(text: str, limit: int = _SPF_DMARC_TRUNCATE_CHARS) -> str:
    """Truncate *text* to *limit* characters, appending ``…`` if cut.

    Args:
        text: Input string.
        limit: Maximum character count before truncation.

    Returns:
        The original string, or the first ``limit`` characters followed
        by ``…`` when longer.
    """
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _find_spf_record(records: list[str]) -> str | None:
    """Return the first TXT record beginning with ``v=spf1`` (case-insensitive).

    Args:
        records: List of decoded TXT record strings.

    Returns:
        The matching record string, or ``None`` if none found.
    """
    for record in records:
        if record.lower().startswith("v=spf1"):
            return record
    return None


def _find_dmarc_record(records: list[str]) -> str | None:
    """Return the first TXT record beginning with ``v=DMARC1`` (case-insensitive).

    Args:
        records: List of decoded TXT record strings.

    Returns:
        The matching record string, or ``None`` if none found.
    """
    for record in records:
        if record.upper().startswith("V=DMARC1"):
            return record
    return None


def _compute_status(checks: list[MailHealthCheck]) -> HealthStatus:
    """Derive top-level status from critical checks only.

    Args:
        checks: All emitted checks for the run.

    Returns:
        ``HealthStatus.HEALTHY`` when every emitted critical check passed;
        ``HealthStatus.UNHEALTHY`` otherwise.
    """
    critical = [c for c in checks if c.severity == CheckSeverity.CRITICAL]
    if all(c.passed for c in critical):
        return HealthStatus.HEALTHY
    return HealthStatus.UNHEALTHY


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
      :data:`_DOMAIN_EXPIRY_WARN_DAYS` days (omitted when WHOIS is
      unavailable).

    Top-level ``status`` is ``healthy`` only when every emitted critical
    check passes; warning failures do not affect it.

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
            make_check(
                "mx_records_found",
                passed=False,
                result="No MX records found",
            )
        )
        return MailHealthResponse(
            domain=domain,
            status=HealthStatus.UNHEALTHY,
            checks=checks,
        )

    mx_list = _format_mx_list(mx_rows)
    mx_count = len(mx_rows)
    checks.append(
        make_check(
            "mx_records_found",
            passed=True,
            result=f"{mx_count} MX record(s): {mx_list}",
        )
    )

    if _is_null_mx(mx_rows):
        checks.append(
            make_check(
                "not_null_mx",
                passed=False,
                result="Domain advertises a null MX (RFC 7505): explicitly refusing mail",
            )
        )
        return MailHealthResponse(
            domain=domain,
            status=HealthStatus.UNHEALTHY,
            checks=checks,
        )

    preference, mx_host = mx_rows[0]
    checks.append(
        make_check(
            "not_null_mx",
            passed=True,
            result=f"MX RRset is not null MX; top target: {preference} {mx_host}",
        )
    )

    critical_failed = False

    if _is_ip_literal(mx_host):
        checks.append(
            make_check(
                "mx_not_ip_literal",
                passed=False,
                result=(
                    f"Top MX target is an IP literal ({mx_host}); "
                    "RFC 5321 §5.1 forbids IP addresses in MX exchanges"
                ),
            )
        )
        critical_failed = True
    else:
        checks.append(
            make_check(
                "mx_not_ip_literal",
                passed=True,
                result=f"Top MX target {mx_host} is a hostname (not an IP literal)",
            )
        )

        cname_target = _resolve_cname(mx_host)
        if cname_target is not None:
            checks.append(
                make_check(
                    "mx_not_cname",
                    passed=False,
                    result=(
                        f"Top MX target {mx_host} is a CNAME to {cname_target}; "
                        "RFC 5321 §5.1 forbids CNAMEs as MX exchanges"
                    ),
                )
            )
            critical_failed = True
        else:
            checks.append(
                make_check(
                    "mx_not_cname",
                    passed=True,
                    result=f"Top MX target {mx_host} is not a CNAME",
                )
            )

    if not critical_failed:
        ip_address = _resolve_ip_for_mx_host(mx_host)
        if not ip_address:
            checks.append(
                make_check(
                    "mx_resolves",
                    passed=False,
                    result=f"Highest-priority MX {mx_host} did not resolve to an A or AAAA record",
                )
            )
            critical_failed = True
        else:
            checks.append(
                make_check(
                    "mx_resolves",
                    passed=True,
                    result=f"{mx_host} resolved to {ip_address}",
                )
            )

    if mx_count == 1:
        checks.append(
            make_check(
                "multiple_mx_records",
                passed=False,
                result=f"Only one MX record ({preference} {mx_host}); no DNS failover",
            )
        )
    else:
        checks.append(
            make_check(
                "multiple_mx_records",
                passed=True,
                result=f"{mx_count} MX records: {mx_list}",
            )
        )

    txt_records = _resolve_txt(domain)
    spf_record = _find_spf_record(txt_records)
    if spf_record is not None:
        checks.append(
            make_check(
                "spf_record_present",
                passed=True,
                result=f"SPF present: {_truncate(spf_record)}",
            )
        )
    else:
        checks.append(
            make_check(
                "spf_record_present",
                passed=False,
                result="No v=spf1 TXT record at apex",
            )
        )

    dmarc_records = _resolve_txt(f"_dmarc.{domain}")
    dmarc_record = _find_dmarc_record(dmarc_records)
    if dmarc_record is not None:
        checks.append(
            make_check(
                "dmarc_record_present",
                passed=True,
                result=f"DMARC present: {_truncate(dmarc_record)}",
            )
        )
    else:
        checks.append(
            make_check(
                "dmarc_record_present",
                passed=False,
                result=f"No v=DMARC1 TXT record at _dmarc.{domain}",
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
                make_check(
                    "domain_not_expiring_soon",
                    passed=False,
                    result=f"Domain registration expired on {expiry_str}",
                )
            )
        elif days_remaining <= _DOMAIN_EXPIRY_WARN_DAYS:
            checks.append(
                make_check(
                    "domain_not_expiring_soon",
                    passed=False,
                    result=f"Domain expires in {days_remaining} days ({expiry_str})",
                )
            )
        else:
            checks.append(
                make_check(
                    "domain_not_expiring_soon",
                    passed=True,
                    result=f"Registration valid; expires {expiry_str} ({days_remaining} days remaining)",
                )
            )

    return MailHealthResponse(
        domain=domain,
        status=_compute_status(checks),
        checks=checks,
    )
