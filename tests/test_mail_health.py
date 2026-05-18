"""Tests for GET /api/v1/mail-health."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from mailpulse.app import create_app
from mailpulse.services.mail_health import _validate_domain


@pytest.fixture
def client() -> TestClient:
    """Return a synchronous test client for the app."""
    return TestClient(create_app())


def check_by_name(data: dict, name: str) -> dict | None:
    """Return the check dict with the given name, or None if absent."""
    for check in data.get("checks", []):
        if check["name"] == name:
            return check
    return None


# ---------------------------------------------------------------------------
# Input validation — neither / both params
# ---------------------------------------------------------------------------


def test_mail_health_missing_email(client: TestClient) -> None:
    response = client.get("/api/v1/mail-health")
    assert response.status_code == 422


def test_mail_health_both_email_and_domain_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/mail-health",
        params={"email": "me@example.com", "domain": "example.com"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Input validation — email param
# ---------------------------------------------------------------------------


def test_mail_health_invalid_not_an_email(client: TestClient) -> None:
    response = client.get("/api/v1/mail-health", params={"email": "not-an-email"})
    assert response.status_code == 422


def test_mail_health_invalid_empty(client: TestClient) -> None:
    response = client.get("/api/v1/mail-health", params={"email": ""})
    assert response.status_code == 422


def test_mail_health_invalid_no_domain_dot(client: TestClient) -> None:
    response = client.get("/api/v1/mail-health", params={"email": "a@b"})
    assert response.status_code == 422


def test_mail_health_invalid_a_at(client: TestClient) -> None:
    response = client.get("/api/v1/mail-health", params={"email": "a@"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Input validation — domain param
# ---------------------------------------------------------------------------


def test_mail_health_domain_invalid_empty(client: TestClient) -> None:
    response = client.get("/api/v1/mail-health", params={"domain": ""})
    assert response.status_code == 422


def test_mail_health_domain_invalid_no_dot(client: TestClient) -> None:
    response = client.get("/api/v1/mail-health", params={"domain": "nodot"})
    assert response.status_code == 422


def test_mail_health_domain_invalid_contains_at(client: TestClient) -> None:
    response = client.get(
        "/api/v1/mail-health", params={"domain": "me@aminbeigi.com"}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Unit tests for _validate_domain
# ---------------------------------------------------------------------------


def test_validate_domain_normalises_case() -> None:
    assert _validate_domain("Example.COM") == "example.com"


def test_validate_domain_strips_whitespace() -> None:
    assert _validate_domain("  example.com  ") == "example.com"


def test_validate_domain_rejects_empty() -> None:
    with pytest.raises(ValueError):
        _validate_domain("")


def test_validate_domain_rejects_no_dot() -> None:
    with pytest.raises(ValueError):
        _validate_domain("nodot")


def test_validate_domain_rejects_at_sign() -> None:
    with pytest.raises(ValueError):
        _validate_domain("me@example.com")


def test_mail_health_domain_param_no_mx_records(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [],
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"domain": "aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "aminbeigi.com"
    assert data["status"] == "unhealthy"
    assert check_by_name(data, "mx_records_found") == {
        "name": "mx_records_found",
        "passed": False,
        "detail": "No MX records found",
    }


def test_mail_health_domain_param_all_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    far_future = datetime.now(tz=UTC) + timedelta(days=365)
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [(10, "mx1.example.com"), (20, "mx2.example.com")],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_ip_for_mx_host",
        lambda host: "10.0.0.1",
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_cname",
        lambda host: None,
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_txt",
        lambda name: ["v=spf1 include:example.com ~all"]
        if not name.startswith("_dmarc")
        else ["v=DMARC1; p=none"],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_domain_expiry",
        lambda domain: far_future,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"domain": "aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "aminbeigi.com"
    assert data["status"] == "healthy"


def test_mail_health_no_mx_records(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [],
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "aminbeigi.com"
    assert data["status"] == "unhealthy"
    assert check_by_name(data, "mx_records_found") == {
        "name": "mx_records_found",
        "passed": False,
        "detail": "No MX records found",
    }
    assert check_by_name(data, "mx_resolves") is None


def test_mail_health_null_mx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [(0, "")],
    )

    def _should_not_be_called(host: str) -> str | None:
        raise AssertionError("_resolve_ip_for_mx_host must not be called for null MX")

    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_ip_for_mx_host",
        _should_not_be_called,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert check_by_name(data, "mx_records_found")["passed"] is True
    not_null = check_by_name(data, "not_null_mx")
    assert not_null["passed"] is False
    assert "RFC 7505" in not_null["detail"]
    assert check_by_name(data, "mx_not_ip_literal") is None
    assert check_by_name(data, "mx_not_cname") is None
    assert check_by_name(data, "mx_resolves") is None
    assert check_by_name(data, "multiple_mx_records") is None


def test_mail_health_mx_is_ip_literal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [(10, "1.2.3.4")],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_cname",
        lambda host: None,
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_txt",
        lambda name: [],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_domain_expiry",
        lambda domain: None,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    ip_check = check_by_name(data, "mx_not_ip_literal")
    assert ip_check["passed"] is False
    assert "RFC 5321" in ip_check["detail"]
    assert check_by_name(data, "mx_not_cname") is None


def test_mail_health_mx_is_cname(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [(10, "mx.example.com")],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_cname",
        lambda host: "target.example.net",
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_txt",
        lambda name: [],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_domain_expiry",
        lambda domain: None,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    cname_check = check_by_name(data, "mx_not_cname")
    assert cname_check["passed"] is False
    assert "RFC 5321" in cname_check["detail"]
    assert "target.example.net" in cname_check["detail"]


def test_mail_health_mx_does_not_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [(10, "mx.example.com")],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_ip_for_mx_host",
        lambda host: None,
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_cname",
        lambda host: None,
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_txt",
        lambda name: [],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_domain_expiry",
        lambda domain: None,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    mx_resolves = check_by_name(data, "mx_resolves")
    assert mx_resolves["passed"] is False
    assert "did not resolve" in mx_resolves["detail"]


def test_mail_health_single_mx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [(10, "mx.example.com")],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_ip_for_mx_host",
        lambda host: "10.0.0.1",
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_cname",
        lambda host: None,
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_txt",
        lambda name: ["v=spf1 include:example.com ~all"]
        if not name.startswith("_dmarc")
        else ["v=DMARC1; p=none"],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_domain_expiry",
        lambda domain: None,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    multi_mx = check_by_name(data, "multiple_mx_records")
    assert multi_mx["passed"] is False
    assert "no failover" in multi_mx["detail"]


def test_mail_health_missing_spf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [(10, "mx1.example.com"), (20, "mx2.example.com")],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_ip_for_mx_host",
        lambda host: "10.0.0.1",
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_cname",
        lambda host: None,
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_txt",
        lambda name: ["v=DMARC1; p=none"] if name.startswith("_dmarc") else [],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_domain_expiry",
        lambda domain: None,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    spf = check_by_name(data, "spf_record_present")
    assert spf["passed"] is False
    assert "v=spf1" in spf["detail"]


def test_mail_health_missing_dmarc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [(10, "mx1.example.com"), (20, "mx2.example.com")],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_ip_for_mx_host",
        lambda host: "10.0.0.1",
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_cname",
        lambda host: None,
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_txt",
        lambda name: ["v=spf1 include:example.com ~all"]
        if not name.startswith("_dmarc")
        else [],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_domain_expiry",
        lambda domain: None,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    dmarc = check_by_name(data, "dmarc_record_present")
    assert dmarc["passed"] is False
    assert "_dmarc" in dmarc["detail"]


def test_mail_health_domain_expiring_soon(monkeypatch: pytest.MonkeyPatch) -> None:
    soon = datetime.now(tz=UTC) + timedelta(days=10)
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [(10, "mx1.example.com"), (20, "mx2.example.com")],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_ip_for_mx_host",
        lambda host: "10.0.0.1",
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_cname",
        lambda host: None,
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_txt",
        lambda name: ["v=spf1 include:example.com ~all"]
        if not name.startswith("_dmarc")
        else ["v=DMARC1; p=none"],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_domain_expiry",
        lambda domain: soon,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    expiry_check = check_by_name(data, "domain_not_expiring_soon")
    assert expiry_check["passed"] is False
    assert "days" in expiry_check["detail"]


def test_mail_health_domain_expiry_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [(10, "mx1.example.com"), (20, "mx2.example.com")],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_ip_for_mx_host",
        lambda host: "10.0.0.1",
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_cname",
        lambda host: None,
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_txt",
        lambda name: ["v=spf1 include:example.com ~all"]
        if not name.startswith("_dmarc")
        else ["v=DMARC1; p=none"],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_domain_expiry",
        lambda domain: None,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert check_by_name(data, "domain_not_expiring_soon") is None


def test_mail_health_all_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    far_future = datetime.now(tz=UTC) + timedelta(days=365)
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_mx",
        lambda domain: [(10, "mx1.example.com"), (20, "mx2.example.com")],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_ip_for_mx_host",
        lambda host: "10.0.0.1",
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_cname",
        lambda host: None,
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_txt",
        lambda name: ["v=spf1 include:example.com ~all"]
        if not name.startswith("_dmarc")
        else ["v=DMARC1; p=none"],
    )
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_domain_expiry",
        lambda domain: far_future,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "aminbeigi.com"
    assert data["status"] == "healthy"
    expected_checks = {
        "mx_records_found",
        "not_null_mx",
        "mx_not_ip_literal",
        "mx_not_cname",
        "mx_resolves",
        "multiple_mx_records",
        "spf_record_present",
        "dmarc_record_present",
        "domain_not_expiring_soon",
    }
    actual_checks = {c["name"] for c in data["checks"]}
    assert actual_checks == expected_checks
    for check in data["checks"]:
        assert check["passed"] is True, f"Expected {check['name']} to pass"
