"""Společné nastavení testů – každý test dostane čistou databázi v paměti."""
import os

# Nastavit PŘED importem aplikace, aby se nevytvářel soubor studybuddy.db a nevolalo skutečné AI.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["GEMINI_API_KEY"] = ""
os.environ["ENVIRONMENT"] = "test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import database  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import auth as auth_router  # noqa: E402


@pytest.fixture
def db_session_factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    # Kód běžící mimo požadavek (úlohy na pozadí) používá database.SessionLocal → přesměrujeme ho.
    monkeypatch.setattr(database, "SessionLocal", factory)
    yield factory
    engine.dispose()


@pytest.fixture
def client(db_session_factory):
    def override():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    auth_router._FAILED.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register(client, email="ana@example.com", password="tajneheslo1", name="Ana"):
    r = client.post("/api/auth/register", json={"email": email, "password": password, "display_name": name})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth_headers(client):
    return register(client)
