"""Shared test fixtures. Forces the app onto an in-memory SQLite DB (set
before any app module is imported) so tests never need a real Postgres.
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, get_db
from app.main import app


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    client.post("/auth/signup", json={"email": "patient@example.com", "password": "password123"})
    resp = client.post("/auth/login", json={"email": "patient@example.com", "password": "password123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def seeded_test(client, auth_headers):
    """Create a centre + a test inside it, return the test dict (id, price, ...)."""
    centre = client.post(
        "/centres/", json={"name": "City Diagnostics", "location": "Pune"}, headers=auth_headers
    ).json()
    test = client.post(
        f"/centres/{centre['id']}/tests", json={"name": "Blood Panel", "price": "499.00"}, headers=auth_headers
    ).json()
    return test
