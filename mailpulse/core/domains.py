"""Domain and email string validation for API and service callers.

Exposes :func:`parse_domain_from_email` and :func:`validate_domain` to
normalize user-supplied identifiers before DNS or WHOIS checks run.
"""


def parse_domain_from_email(email: str) -> str:
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
    invalid_message = "Invalid email address"
    stripped = email.strip()
    if "@" not in stripped:
        raise ValueError(invalid_message)
    local_part, domain = stripped.rsplit("@", 1)
    if not local_part or not domain:
        raise ValueError(invalid_message)
    domain = domain.strip()
    if not domain:
        raise ValueError(invalid_message)
    if "." not in domain:
        raise ValueError(invalid_message)
    return domain.lower()


def validate_domain(domain: str) -> str:
    """Validate and normalise a bare domain name.

    Args:
        domain: Domain name to validate. Leading and trailing whitespace is
            stripped before validation.

    Returns:
        Lowercased domain string.

    Raises:
        ValueError: If the string is empty, contains an ``@``, or has no
            dot (i.e. is not a valid domain).
    """
    invalid_message = "Invalid domain"
    stripped = domain.strip()
    if not stripped:
        raise ValueError(invalid_message)
    if "@" in stripped:
        msg = "Invalid domain: use the 'email' parameter to pass an email address"
        raise ValueError(msg)
    if "." not in stripped:
        raise ValueError(invalid_message)
    return stripped.lower()
