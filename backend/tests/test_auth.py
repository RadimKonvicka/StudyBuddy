"""Testy registrace, přihlášení a ochrany endpointů."""
from tests.conftest import register


def test_register_returns_token_and_user(client):
    r = client.post("/api/auth/register", json={"email": "Ana@Example.com", "password": "tajneheslo1", "display_name": " Ana "})
    assert r.status_code == 201
    data = r.json()
    assert data["access_token"]
    assert data["user"]["email"] == "ana@example.com"  # e-mail se ukládá malými písmeny
    assert data["user"]["display_name"] == "Ana"
    assert "password_hash" not in data["user"]


def test_duplicate_email_rejected(client):
    register(client)
    r = client.post("/api/auth/register", json={"email": "ANA@example.com", "password": "jineheslo22", "display_name": "X"})
    assert r.status_code == 409


def test_short_password_has_czech_message(client):
    r = client.post("/api/auth/register", json={"email": "a@example.com", "password": "123", "display_name": "A"})
    assert r.status_code == 422
    assert "Heslo" in r.json()["detail"]


def test_login_ok_and_wrong_password(client):
    register(client)
    ok = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "tajneheslo1"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "spatne-heslo"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "nikdo@example.com", "password": "cokoliv123"})
    assert unknown.status_code == 401
    assert bad.json()["detail"] == unknown.json()["detail"]  # neprozradí, zda e-mail existuje


def test_password_is_hashed(client, db_session_factory):
    from app.models import User

    register(client)
    with db_session_factory() as db:
        user = db.query(User).one()
        assert user.password_hash != "tajneheslo1"
        assert user.password_hash.startswith("$argon2")


def test_me_requires_valid_token(client, auth_headers):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer nesmysl"}).status_code == 401
    r = client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200 and r.json()["display_name"] == "Ana"


def test_login_rate_limit(client):
    register(client)
    for _ in range(8):
        client.post("/api/auth/login", json={"email": "ana@example.com", "password": "spatne-heslo"})
    r = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "tajneheslo1"})
    assert r.status_code == 429
