import pytest
from fastapi.testclient import TestClient

from mailpulse.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_mail_health_missing_email(client: TestClient) -> None:
    response = client.get("/api/v1/mail-health")
    assert response.status_code == 422


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


def test_mail_health_no_mx_records(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve_mx(domain: str) -> list[tuple[int, str]]:
        assert domain == "aminbeigi.com"
        return []

    monkeypatch.setattr("mailpulse.services.mail_health._resolve_mx", fake_resolve_mx)
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
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
        },
    }


def test_mail_health_mx_does_not_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve_mx(domain: str) -> list[tuple[int, str]]:
        assert domain == "aminbeigi.com"
        return [(10, "mx.example.com")]

    def fake_resolve_ip_for_mx_host(host: str) -> str | None:
        assert host == "mx.example.com"
        return None

    monkeypatch.setattr("mailpulse.services.mail_health._resolve_mx", fake_resolve_mx)
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_ip_for_mx_host",
        fake_resolve_ip_for_mx_host,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
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
        },
    }


def test_mail_health_all_checks_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve_mx(domain: str) -> list[tuple[int, str]]:
        return [(10, "mx.example.com")]

    def fake_resolve_ip_for_mx_host(host: str) -> str | None:
        return "10.0.0.1"

    monkeypatch.setattr("mailpulse.services.mail_health._resolve_mx", fake_resolve_mx)
    monkeypatch.setattr(
        "mailpulse.services.mail_health._resolve_ip_for_mx_host",
        fake_resolve_ip_for_mx_host,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/mail-health", params={"email": "me@aminbeigi.com"})
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
        },
    }
