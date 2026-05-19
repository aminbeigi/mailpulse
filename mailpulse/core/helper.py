"""Domain and email string validation for API and service callers.

Exposes :func:`resolve_domain_input` as the primary entry point for
normalising user-supplied email addresses or bare domain names before
DNS or WHOIS checks run.

"""


def resolve_domain_input(email: str | None, domain: str | None) -> str:
    """Resolve exactly one email or domain query input to a normalised domain.

    Exactly one of ``email`` or ``domain`` must be supplied.  If ``email``
    is given the domain part is extracted from the address.  If ``domain``
    is given it is validated and returned directly.

    Args:
        email: Email address whose domain should be extracted.
        domain: Bare domain name to validate and normalise.

    Returns:
        Lowercased, normalised domain string.

    Raises:
        ValueError: If both or neither parameters are supplied, or if the
            supplied value fails format validation.
    """
    if email is not None and domain is not None:
        raise ValueError("Provide either 'email' or 'domain', not both.")
    if email is not None:
        return _domain_from_email(email)
    if domain is not None:
        return _normalize_domain(domain)
    raise ValueError("Provide either 'email' or 'domain'.")


def _domain_from_email(email: str) -> str:
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


def _normalize_domain(domain: str) -> str:
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
