from datetime import datetime, timedelta, timezone

FUTURE = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
PAST = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()


def test_create_booking(client, auth_headers, seeded_test):
    resp = client.post(
        "/bookings/",
        json={"test_id": seeded_test["id"], "appointment_time": FUTURE},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["amount"] == "499.00"


def test_booking_amount_is_server_set_not_client_supplied(client, auth_headers, seeded_test):
    # amount isn't even accepted in the request body; server derives it from the test price.
    resp = client.post(
        "/bookings/",
        json={"test_id": seeded_test["id"], "appointment_time": FUTURE, "amount": "1.00"},
        headers=auth_headers,
    )
    assert resp.json()["amount"] == "499.00"


def test_create_booking_rejects_past_appointment(client, auth_headers, seeded_test):
    resp = client.post(
        "/bookings/", json={"test_id": seeded_test["id"], "appointment_time": PAST}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_create_booking_invalid_test_id_404(client, auth_headers):
    resp = client.post(
        "/bookings/", json={"test_id": "nope", "appointment_time": FUTURE}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_create_booking_requires_auth(client, seeded_test):
    resp = client.post("/bookings/", json={"test_id": seeded_test["id"], "appointment_time": FUTURE})
    assert resp.status_code in (401, 403)


def test_user_cannot_see_others_booking(client, auth_headers, seeded_test):
    booking = client.post(
        "/bookings/", json={"test_id": seeded_test["id"], "appointment_time": FUTURE}, headers=auth_headers
    ).json()

    client.post("/auth/signup", json={"email": "other@example.com", "password": "password123"})
    other_token = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "password123"}
    ).json()["access_token"]

    resp = client.get(f"/bookings/{booking['id']}", headers={"Authorization": f"Bearer {other_token}"})
    assert resp.status_code == 403


def test_get_nonexistent_booking_404(client, auth_headers):
    resp = client.get("/bookings/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404


def test_cancel_booking(client, auth_headers, seeded_test):
    booking = client.post(
        "/bookings/", json={"test_id": seeded_test["id"], "appointment_time": FUTURE}, headers=auth_headers
    ).json()
    resp = client.patch(f"/bookings/{booking['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_cancel_already_cancelled_booking_rejected(client, auth_headers, seeded_test):
    booking = client.post(
        "/bookings/", json={"test_id": seeded_test["id"], "appointment_time": FUTURE}, headers=auth_headers
    ).json()
    client.patch(f"/bookings/{booking['id']}/cancel", headers=auth_headers)
    resp = client.patch(f"/bookings/{booking['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 400


def test_list_my_bookings_only_shows_own(client, auth_headers, seeded_test):
    client.post(
        "/bookings/", json={"test_id": seeded_test["id"], "appointment_time": FUTURE}, headers=auth_headers
    )
    client.post("/auth/signup", json={"email": "other2@example.com", "password": "password123"})
    other_token = client.post(
        "/auth/login", json={"email": "other2@example.com", "password": "password123"}
    ).json()["access_token"]
    client.post(
        "/bookings/",
        json={"test_id": seeded_test["id"], "appointment_time": FUTURE},
        headers={"Authorization": f"Bearer {other_token}"},
    )

    resp = client.get("/bookings/", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
