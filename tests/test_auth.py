def test_signup_returns_token(client):
    resp = client.post("/auth/signup", json={"email": "a@example.com", "password": "password123"})
    assert resp.status_code == 201
    assert "access_token" in resp.json()


def test_signup_duplicate_email_rejected(client):
    client.post("/auth/signup", json={"email": "dup@example.com", "password": "password123"})
    resp = client.post("/auth/signup", json={"email": "dup@example.com", "password": "password123"})
    assert resp.status_code == 409


def test_signup_short_password_rejected(client):
    resp = client.post("/auth/signup", json={"email": "b@example.com", "password": "short"})
    assert resp.status_code == 422


def test_signup_long_password_rejected(client):
    resp = client.post("/auth/signup", json={"email": "b2@example.com", "password": "a" * 73})
    assert resp.status_code == 422


def test_signup_rejected_password_not_echoed_in_response(client):
    """A validation failure must never leak the raw password back to the caller."""
    resp = client.post("/auth/signup", json={"email": "b3@example.com", "password": "xyzpwd1"})
    assert "xyzpwd1" not in resp.text
    assert '"input":"***"' in resp.text


def test_login_success(client):
    client.post("/auth/signup", json={"email": "c@example.com", "password": "password123"})
    resp = client.post("/auth/login", json={"email": "c@example.com", "password": "password123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password_rejected(client):
    client.post("/auth/signup", json={"email": "d@example.com", "password": "password123"})
    resp = client.post("/auth/login", json={"email": "d@example.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_unknown_email_rejected(client):
    resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert resp.status_code == 401


def test_protected_endpoint_requires_token(client):
    resp = client.get("/bookings/")
    assert resp.status_code in (401, 403)


def test_protected_endpoint_rejects_invalid_token(client):
    resp = client.get("/bookings/", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
