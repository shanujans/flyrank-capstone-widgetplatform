import os

# Force test-friendly settings BEFORE the app/config module is imported
# anywhere, so every test runs against an isolated in-memory DB and
# deterministic (mocked) geo providers.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["MOCK_GEO"] = "true"
os.environ["RATE_LIMIT_PER_IP_PER_MINUTE"] = "3"
os.environ["RATE_LIMIT_PER_WIDGET_PER_MINUTE"] = "50"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app import rate_limit as rate_limit_module

# A single shared in-memory SQLite connection for the whole test session,
# kept alive via StaticPool (a normal in-memory DB dies with each connection).
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    rate_limit_module.limiter.reset()
    yield
    rate_limit_module.limiter.reset()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    """Registers a fresh tenant and returns ready-to-use Authorization headers."""
    email = "owner@example.com"
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    resp = client.post("/auth/login", data={"username": email, "password": "supersecret123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def widget(client, auth_headers):
    """Creates one widget with a required 'email' field and returns its JSON."""
    payload = {
        "type": "signup_form",
        "title": "Join our newsletter",
        "description": "Weekly bakery updates",
        "button_text": "Sign up",
        "fields": [
            {"name": "email", "label": "Email", "type": "email", "required": True},
            {"name": "name", "label": "Name", "type": "text", "required": False},
        ],
    }
    resp = client.post("/widgets", json=payload, headers=auth_headers)
    return resp.json()
