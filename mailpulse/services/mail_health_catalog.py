"""Catalog of static metadata for GET /api/v1/mail-health checks.

Every check's stable fields (title, description, reference, severity, and
pass/fail result templates) are defined here. The service layer reads from
:data:`CHECK_CATALOG` and uses :func:`make_check` to merge static metadata
with runtime values.
"""

from dataclasses import dataclass

from mailpulse.schemas.mail_health import CheckSeverity, MailHealthCheck


@dataclass(frozen=True)
class CheckDefinition:
    """Static metadata and result templates for one mail-health check.

    Args:
        name: Stable machine-readable identifier.
        title: Short human-readable check name.
        description: What the check verifies and why it matters.
        reference: Relevant RFC or standard, or ``None``.
        severity: Impact tier — ``critical`` or ``warning``.
        pass_result: Template string for a passing result, or ``None``
            when a pass truly has nothing to report.
        fail_result: Template string for a failing result.
    """

    name: str
    title: str
    description: str
    reference: str | None
    severity: CheckSeverity
    pass_result: str | None
    fail_result: str


CHECK_CATALOG: dict[str, CheckDefinition] = {
    "mx_records_found": CheckDefinition(
        name="mx_records_found",
        title="MX records present",
        description=(
            "Confirms the domain publishes at least one DNS MX record so sending "
            "mail systems know where to deliver inbound mail. Without MX records, "
            "there is no standard inbound route and delivery cannot be attempted "
            "for this domain."
        ),
        reference="RFC 5321",
        severity=CheckSeverity.CRITICAL,
        pass_result="{mx_count} MX record(s): {mx_list}",
        fail_result="No MX records found",
    ),
    "not_null_mx": CheckDefinition(
        name="not_null_mx",
        title="Not a null MX",
        description=(
            "Confirms the domain does not publish an RFC 7505 null MX (preference 0 "
            "with an empty exchange). A null MX is an explicit signal that the domain "
            "does not accept inbound mail, which is valid for non-mail domains but "
            "means delivery is intentionally off."
        ),
        reference="RFC 7505",
        severity=CheckSeverity.CRITICAL,
        pass_result="MX RRset is not null MX; top target: {preference} {mx_host}",
        fail_result="Domain advertises a null MX (RFC 7505): explicitly refusing mail",
    ),
    "mx_not_ip_literal": CheckDefinition(
        name="mx_not_ip_literal",
        title="MX target is a hostname",
        description=(
            "Confirms the highest-priority MX exchange is a hostname, not an "
            "IPv4/IPv6 literal. RFC 5321 requires MX targets to be domain names; "
            "IP literals in MX records break interoperability with many MTAs."
        ),
        reference="RFC 5321 §5.1",
        severity=CheckSeverity.CRITICAL,
        pass_result="Top MX target {mx_host} is a hostname (not an IP literal)",
        fail_result=(
            "Top MX target is an IP literal ({mx_host}); "
            "RFC 5321 §5.1 forbids IP addresses in MX exchanges"
        ),
    ),
    "mx_not_cname": CheckDefinition(
        name="mx_not_cname",
        title="MX target is not a CNAME",
        description=(
            "Confirms the highest-priority MX exchange is not a CNAME alias. MX "
            "records must point to hostnames that resolve directly; CNAME at the MX "
            "target is not allowed and causes unpredictable behavior for mail delivery."
        ),
        reference="RFC 5321 §5.1",
        severity=CheckSeverity.CRITICAL,
        pass_result="Top MX target {mx_host} is not a CNAME",
        fail_result=(
            "Top MX target {mx_host} is a CNAME to {cname_target}; "
            "RFC 5321 §5.1 forbids CNAMEs as MX exchanges"
        ),
    ),
    "mx_resolves": CheckDefinition(
        name="mx_resolves",
        title="Top MX resolves",
        description=(
            "Confirms the highest-priority MX hostname resolves to at least one IP "
            "address (A or AAAA). If the MX host does not resolve, sending MTAs "
            "cannot connect and inbound mail will fail even when MX records exist."
        ),
        reference="RFC 5321",
        severity=CheckSeverity.CRITICAL,
        pass_result="{mx_host} resolved to {ip}",
        fail_result="Highest-priority MX {mx_host} did not resolve to an A or AAAA record",
    ),
    "multiple_mx_records": CheckDefinition(
        name="multiple_mx_records",
        title="Multiple MX records",
        description=(
            "Checks for more than one MX record so mail can fail over if a primary "
            "host is unavailable. A single MX is often enough for delivery, but one "
            "record means no DNS-level redundancy if that host is down."
        ),
        reference=None,
        severity=CheckSeverity.WARNING,
        pass_result="{mx_count} MX records: {mx_list}",
        fail_result="Only one MX record ({preference} {mx_host}); no DNS failover",
    ),
    "spf_record_present": CheckDefinition(
        name="spf_record_present",
        title="SPF record at apex",
        description=(
            "Checks for a TXT record at the domain apex beginning with v=spf1. SPF "
            "defines which hosts may send mail using this domain name. It does not "
            "control whether inbound mail can be delivered, but missing SPF weakens "
            "authentication and DMARC alignment."
        ),
        reference="RFC 7208",
        severity=CheckSeverity.WARNING,
        pass_result="SPF present: {spf_record}",
        fail_result="No v=spf1 TXT record at apex",
    ),
    "dmarc_record_present": CheckDefinition(
        name="dmarc_record_present",
        title="DMARC record published",
        description=(
            "Checks for a TXT record at _dmarc.{domain} beginning with v=DMARC1. "
            "DMARC tells receivers how to handle mail that fails SPF/DKIM alignment "
            "and enables reporting. Missing DMARC does not block inbound delivery but "
            "reduces visibility and policy control for spoofing."
        ),
        reference="RFC 7489",
        severity=CheckSeverity.WARNING,
        pass_result="DMARC present: {dmarc_record}",
        fail_result="No v=DMARC1 TXT record at _dmarc.{domain}",
    ),
    "domain_not_expiring_soon": CheckDefinition(
        name="domain_not_expiring_soon",
        title="Domain registration not expiring soon",
        description=(
            "Uses WHOIS to see whether the domain registration is expired or expiring "
            "within 30 days. Expiry does not stop mail today, but an expired domain "
            "will eventually break MX and all mail flow. Omitted when WHOIS data is "
            "unavailable."
        ),
        reference=None,
        severity=CheckSeverity.WARNING,
        pass_result="Registration valid; expires {expiry_date} ({days_remaining} days remaining)",
        fail_result="",
    ),
}


def make_check(name: str, *, passed: bool, result: str | None) -> MailHealthCheck:
    """Merge catalog static fields with runtime passed/result into a MailHealthCheck.

    Args:
        name: Key into :data:`CHECK_CATALOG`.
        passed: Whether the check passed at runtime.
        result: Per-run detail string, or ``None``.

    Returns:
        A fully populated :class:`~mailpulse.schemas.mail_health.MailHealthCheck`.

    Raises:
        KeyError: If ``name`` is not in :data:`CHECK_CATALOG`.
    """
    defn = CHECK_CATALOG[name]
    return MailHealthCheck(
        name=defn.name,
        title=defn.title,
        description=defn.description,
        reference=defn.reference,
        severity=defn.severity,
        passed=passed,
        result=result,
    )
