"""Tests for domain and email input normalization."""

import pytest

from mailpulse.core.domains import parse_domain_from_email, validate_domain


def test_validate_domain_normalises_case() -> None:
    assert validate_domain("Example.COM") == "example.com"


def test_validate_domain_strips_whitespace() -> None:
    assert validate_domain("  example.com  ") == "example.com"


def test_validate_domain_rejects_empty() -> None:
    with pytest.raises(ValueError):
        validate_domain("")


def test_validate_domain_rejects_no_dot() -> None:
    with pytest.raises(ValueError):
        validate_domain("nodot")


def test_validate_domain_rejects_at_sign() -> None:
    with pytest.raises(ValueError):
        validate_domain("me@example.com")


def test_parse_domain_from_email_extracts_domain() -> None:
    assert parse_domain_from_email("me@Example.COM") == "example.com"


def test_parse_domain_from_email_strips_whitespace() -> None:
    assert parse_domain_from_email("  me@example.com  ") == "example.com"


def test_parse_domain_from_email_rejects_no_at() -> None:
    with pytest.raises(ValueError):
        parse_domain_from_email("not-an-email")


def test_parse_domain_from_email_rejects_empty_local() -> None:
    with pytest.raises(ValueError):
        parse_domain_from_email("@example.com")


def test_parse_domain_from_email_rejects_empty_domain() -> None:
    with pytest.raises(ValueError):
        parse_domain_from_email("a@")


def test_parse_domain_from_email_rejects_domain_without_dot() -> None:
    with pytest.raises(ValueError):
        parse_domain_from_email("a@b")
