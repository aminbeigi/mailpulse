"""Tests for domain and email input normalization."""

import pytest

from mailpulse.core.helper import resolve_domain_input


def test_resolve_domain_input_email_extracts_domain() -> None:
    assert resolve_domain_input(email="me@Example.COM", domain=None) == "example.com"


def test_resolve_domain_input_email_strips_whitespace() -> None:
    assert resolve_domain_input(email="  me@example.com  ", domain=None) == "example.com"


def test_resolve_domain_input_domain_normalises_case() -> None:
    assert resolve_domain_input(email=None, domain="Example.COM") == "example.com"


def test_resolve_domain_input_domain_strips_whitespace() -> None:
    assert resolve_domain_input(email=None, domain="  example.com  ") == "example.com"


def test_resolve_domain_input_rejects_both() -> None:
    with pytest.raises(ValueError, match="not both"):
        resolve_domain_input(email="me@example.com", domain="example.com")


def test_resolve_domain_input_rejects_neither() -> None:
    with pytest.raises(ValueError):
        resolve_domain_input(email=None, domain=None)


def test_resolve_domain_input_rejects_invalid_email_no_at() -> None:
    with pytest.raises(ValueError):
        resolve_domain_input(email="not-an-email", domain=None)


def test_resolve_domain_input_rejects_invalid_email_empty_local() -> None:
    with pytest.raises(ValueError):
        resolve_domain_input(email="@example.com", domain=None)


def test_resolve_domain_input_rejects_invalid_email_empty_domain() -> None:
    with pytest.raises(ValueError):
        resolve_domain_input(email="a@", domain=None)


def test_resolve_domain_input_rejects_invalid_email_domain_without_dot() -> None:
    with pytest.raises(ValueError):
        resolve_domain_input(email="a@b", domain=None)


def test_resolve_domain_input_rejects_empty_domain() -> None:
    with pytest.raises(ValueError):
        resolve_domain_input(email=None, domain="")


def test_resolve_domain_input_rejects_domain_without_dot() -> None:
    with pytest.raises(ValueError):
        resolve_domain_input(email=None, domain="nodot")


def test_resolve_domain_input_rejects_domain_with_at_sign() -> None:
    with pytest.raises(ValueError):
        resolve_domain_input(email=None, domain="me@example.com")
