import pytest
from fastapi.testclient import TestClient

from mailpulse.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_email_health_missing_email(client: TestClient) -> None:
    response = client.get("/v1/mail-health")
    assert response.status_code == 422


def test_email_health_invalid_not_an_email(client: TestClient) -> None:
    response = client.get("/v1/mail-health", params={"email": "not-an-email"})
    assert response.status_code == 422


def test_email_health_invalid_empty(client: TestClient) -> None:
    response = client.get("/v1/mail-health", params={"email": ""})
    assert response.status_code == 422


def test_email_health_invalid_no_domain_dot(client: TestClient) -> None:
    response = client.get("/v1/mail-health", params={"email": "a@b"})
    assert response.status_code == 422


def test_email_health_invalid_a_at(client: TestClient) -> None:
    response = client.get("/v1/mail-health", params={"email": "a@"})
    assert response.status_code == 422


def test_email_health_no_mx_records(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve_mx(domain: str) -> list[tuple[int, str]]:
        assert domain == "aminbeigi.com"
        return []

    monkeypatch.setattr("mailpulse.services.email_health._resolve_mx", fake_resolve_mx)
    client = TestClient(create_app())
    response = client.get("/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "domain": "aminbeigi.com",
        "healthy": False,
        "status": "unhealthy",
        "reason": "No MX records found",
        "checks": {
            "mx_records_found": False,
            "mx_resolves": False,
            "smtp_reachable": False,
            "smtp_handshake_ok": False,
        },
    }


def test_email_health_mx_does_not_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve_mx(domain: str) -> list[tuple[int, str]]:
        assert domain == "aminbeigi.com"
        return [(10, "mx.example.com")]

    def fake_resolve_ip_for_mx_host(host: str) -> str | None:
        assert host == "mx.example.com"
        return None

    monkeypatch.setattr("mailpulse.services.email_health._resolve_mx", fake_resolve_mx)
    monkeypatch.setattr(
        "mailpulse.services.email_health._resolve_ip_for_mx_host",
        fake_resolve_ip_for_mx_host,
    )
    client = TestClient(create_app())
    response = client.get("/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "domain": "aminbeigi.com",
        "healthy": False,
        "status": "unhealthy",
        "reason": "Highest-priority MX did not resolve",
        "checks": {
            "mx_records_found": True,
            "mx_resolves": False,
            "smtp_reachable": False,
            "smtp_handshake_ok": False,
        },
    }


def test_email_health_smtp_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve_mx(domain: str) -> list[tuple[int, str]]:
        return [(10, "mx.example.com")]

    def fake_resolve_ip_for_mx_host(host: str) -> str | None:
        return "10.0.0.1"

    def fake_probe_smtp_socket(address: str) -> bool:
        assert address == "10.0.0.1"
        return False

    monkeypatch.setattr("mailpulse.services.email_health._resolve_mx", fake_resolve_mx)
    monkeypatch.setattr(
        "mailpulse.services.email_health._resolve_ip_for_mx_host",
        fake_resolve_ip_for_mx_host,
    )
    monkeypatch.setattr(
        "mailpulse.services.email_health._probe_smtp_socket",
        fake_probe_smtp_socket,
    )
    client = TestClient(create_app())
    response = client.get("/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "domain": "aminbeigi.com",
        "healthy": False,
        "status": "unhealthy",
        "reason": "SMTP unreachable on port 25",
        "checks": {
            "mx_records_found": True,
            "mx_resolves": True,
            "smtp_reachable": False,
            "smtp_handshake_ok": False,
        },
    }


def test_email_health_ehlo_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve_mx(domain: str) -> list[tuple[int, str]]:
        return [(10, "mx.example.com")]

    def fake_resolve_ip_for_mx_host(host: str) -> str | None:
        return "10.0.0.1"

    def fake_probe_smtp_socket(address: str) -> bool:
        return True

    def fake_smtp_ehlo_ok(address: str) -> bool:
        return False

    monkeypatch.setattr("mailpulse.services.email_health._resolve_mx", fake_resolve_mx)
    monkeypatch.setattr(
        "mailpulse.services.email_health._resolve_ip_for_mx_host",
        fake_resolve_ip_for_mx_host,
    )
    monkeypatch.setattr(
        "mailpulse.services.email_health._probe_smtp_socket",
        fake_probe_smtp_socket,
    )
    monkeypatch.setattr("mailpulse.services.email_health._smtp_ehlo_ok", fake_smtp_ehlo_ok)
    client = TestClient(create_app())
    response = client.get("/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "domain": "aminbeigi.com",
        "healthy": False,
        "status": "unhealthy",
        "reason": "SMTP did not respond to EHLO",
        "checks": {
            "mx_records_found": True,
            "mx_resolves": True,
            "smtp_reachable": True,
            "smtp_handshake_ok": False,
        },
    }


def test_email_health_all_checks_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve_mx(domain: str) -> list[tuple[int, str]]:
        return [(10, "mx.example.com")]

    def fake_resolve_ip_for_mx_host(host: str) -> str | None:
        return "10.0.0.1"

    def fake_probe_smtp_socket(address: str) -> bool:
        return True

    def fake_smtp_ehlo_ok(address: str) -> bool:
        return True

    monkeypatch.setattr("mailpulse.services.email_health._resolve_mx", fake_resolve_mx)
    monkeypatch.setattr(
        "mailpulse.services.email_health._resolve_ip_for_mx_host",
        fake_resolve_ip_for_mx_host,
    )
    monkeypatch.setattr(
        "mailpulse.services.email_health._probe_smtp_socket",
        fake_probe_smtp_socket,
    )
    monkeypatch.setattr("mailpulse.services.email_health._smtp_ehlo_ok", fake_smtp_ehlo_ok)
    client = TestClient(create_app())
    response = client.get("/v1/mail-health", params={"email": "me@aminbeigi.com"})
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "domain": "aminbeigi.com",
        "healthy": True,
        "status": "healthy",
        "reason": None,
        "checks": {
            "mx_records_found": True,
            "mx_resolves": True,
            "smtp_reachable": True,
            "smtp_handshake_ok": True,
        },
    }
